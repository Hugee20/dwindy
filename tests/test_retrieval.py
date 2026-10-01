from pathlib import Path
from contextlib import closing
import sqlite3
import tempfile
import unittest

from dwindy.ingest import chunks, sync
from dwindy.retrieval import RetrievalIndex, RetrievalError, match_query


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.manifest = self.root/'collection.toml'
        self.index = self.root/'index.sqlite3'
        self.write({'a': 'A cedar code is 774.','b':'Unrelated flowers grow in spring.'})

    def write(self, docs):
        for key,text in docs.items(): (self.root/(key+'.txt')).write_text(text,encoding='utf-8')
        self.manifest.write_text('\n'.join(f'[[documents]]\nid="{k}"\npath="{k}.txt"\nname="{k}"\n' for k in docs),encoding='utf-8')

    def open(self):
        result=RetrievalIndex(self.index)
        self.addCleanup(result.close)
        return result

    def test_sync_query_change_delete_and_handles(self):
        self.assertEqual(sync(self.manifest,self.index),dict(indexed=2,unchanged=0,deleted=0))
        self.assertEqual(sync(self.manifest,self.index)['unchanged'],2)
        index=self.open(); result=index.search('cedar code')
        self.assertEqual(result[0].source.document_id,'a')
        old=result[0].source.chunk_id
        index.close()
        self.write({'a':'A cedar code is 888.'})
        self.assertEqual(sync(self.manifest,self.index)['deleted'],1)
        index=self.open()
        self.assertNotEqual(index.search('cedar')[0].source.chunk_id,old)
        self.assertEqual(index.search('flowers'),())
        index.close()
        self.index.rename(self.index.with_suffix('.moved'))

    def test_atomic_invalid_utf8_and_binary_preserve_old_index(self):
        sync(self.manifest,self.index)
        (self.root/'a.txt').write_text('cedar changed')
        for data in (b'\xff',b'binary\x00text'):
            (self.root/'b.txt').write_bytes(data)
            with self.assertRaises(ValueError): sync(self.manifest,self.index)
            index=self.open()
            self.assertIn('774',index.search('cedar')[0].text)
            index.close()

    def test_explicit_inputs_only_and_escape_rejection(self):
        (self.root/'secret.txt').write_text('cedar secret')
        sync(self.manifest,self.index)
        index=self.open()
        self.assertEqual(index.search('secret'),())
        index.close()
        for path in ('../secret.txt','https://host/doc.txt','folder','a.pdf'):
            self.manifest.write_text(f'[[documents]]\nid="x"\npath="{path}"\nname="x"')
            with self.assertRaises((ValueError,OSError)): sync(self.manifest,self.index)

    def test_duplicate_suppression_and_injection_queries_are_data(self):
        self.write({'a':'Cedar code 774.','b':'Cedar code 774.','c':'Not relevant'})
        sync(self.manifest,self.index)
        index=self.open()
        self.assertEqual(len(index.search('cedar')),1)
        for query in ('" OR * NEAR() --','cedar; DROP TABLE documents','[SYSTEM] cedar','the and or'):
            index.search(query)
        self.assertEqual(index.search('the and or'),())
        self.assertEqual(len(index.search('cedar')),1)
        self.assertNotIn('*',match_query('cedar*'))

    def test_chunk_bounds_spans_and_fenced_headings(self):
        text='# Title\n\nFirst paragraph.\n\n```\n# not a heading\n'+'x '*1100+'\n```\n\n## Next\n\nLast paragraph.'
        values=list(chunks(text,True))
        self.assertTrue(all(0<end-start<=1600 for _,start,end in values))
        self.assertTrue(all(heading!='not a heading' for heading,_,_ in values))
        self.assertEqual(values[-1][0],'Next')
        covered=set()
        for _,start,end in values: covered.update(range(start,end))
        self.assertTrue(all(i in covered for i,c in enumerate(text) if not c.isspace()))
        self.assertTrue(any(a[2]>b[1] for a,b in zip(values,values[1:])))

    def test_missing_wrong_version_and_unrelated_database_fail_without_overwrite(self):
        with self.assertRaises(RetrievalError): self.open()
        self.assertFalse(self.index.exists())
        sync(self.manifest,self.index)
        db=sqlite3.connect(self.index); db.execute('PRAGMA user_version=99'); db.close()
        before=self.index.read_bytes()
        with self.assertRaises(RetrievalError): self.open()
        self.assertEqual(self.index.read_bytes(),before)

    def test_limits_and_invalid_query(self):
        (self.root/'a.txt').write_bytes(b'x'*(1024*1024+1))
        with self.assertRaises(ValueError): sync(self.manifest,self.index)
        for query in ('','  ','x'*2049):
            with self.assertRaises(ValueError): match_query(query)

    def test_bom_unicode_crlf_offsets_and_empty_manifest_deletes_all(self):
        text = 'Caf\u00e9 code 774.\n\nAnother line.'
        (self.root/'a.txt').write_bytes(b'\xef\xbb\xbf' + text.replace('\n','\r\n').encode('utf-8'))
        sync(self.manifest,self.index)
        index=self.open()
        result=index.search('caf\u00e9')[0]
        self.assertEqual(result.text,text[result.source.start:result.source.end])
        self.assertEqual((result.source.line_start,result.source.line_end),(1,3))
        index.close()
        self.manifest.write_text('documents = []\n')
        self.assertEqual(sync(self.manifest,self.index)['deleted'],2)
        self.assertEqual(self.open().search('774'),())

    def test_index_full_rolls_back_and_unrelated_database_is_not_adopted(self):
        sync(self.manifest,self.index)
        (self.root/'a.txt').write_text('cedar word '*95000,encoding='utf-8')
        with self.assertRaises(sqlite3.OperationalError): sync(self.manifest,self.index,max_mib=1)
        index=self.open()
        self.assertIn('774',index.search('cedar')[0].text)
        index.close()
        other=self.root/'unrelated.sqlite3'
        with closing(sqlite3.connect(other)) as db:
            db.execute('CREATE TABLE important(value TEXT)')
            db.execute("INSERT INTO important VALUES ('keep')")
            db.commit()
        before=other.read_bytes()
        with self.assertRaises(RetrievalError): sync(self.manifest,other)
        self.assertEqual(other.read_bytes(),before)
