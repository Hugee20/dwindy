from contextlib import closing
import builtins
import io
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

try:
    import pathspec  # noqa: F401  Optional dwindy[project] dependency.
except ImportError:
    pathspec = None

from project_support import apply_lifecycle, load, materialize, write_config
from dwindy.evidence import evidence_question
from dwindy.ingest import sync as manifest_sync
from dwindy.retrieval import RetrievalIndex

if pathspec is not None:
    from dwindy import project
    from dwindy.project import source_chunks, synchronize
    sys.path.insert(0, str(Path(__file__).parent))
    from project.evaluate import evaluate


def index_text(path):
    """Everything persisted, lowercased, including FTS shadow tables and free pages."""
    return Path(path).read_bytes().lower()


@unittest.skipIf(pathspec is None, 'requires the optional dwindy[project] dependency')
class ProjectAwarenessTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.config = materialize(self.root)
        self.index = self.root/'index.sqlite3'
        self.discovery = load('discovery.json')

    def open(self):
        result = RetrievalIndex(self.index)
        self.addCleanup(result.close)
        return result

    def recorded_sync(self, **kwargs):
        """Synchronize while recording every file opened beneath the host root."""
        opened, host = [], os.path.normcase(str(self.root/'host'))
        def wrap(original):
            def recorder(path, *args, **kw):
                text = os.path.normcase(os.path.abspath(os.fspath(path))) if isinstance(path, (str, os.PathLike)) else ''
                if text.startswith(host + os.sep):
                    opened.append(Path(os.path.relpath(text, host)).as_posix())
                return original(path, *args, **kw)
            return recorder
        with patch('os.open', wrap(os.open)), patch('io.open', wrap(io.open)), patch('builtins.open', wrap(builtins.open)):
            report = synchronize(self.config, **kwargs)
        return report, {path.casefold() for path in opened}

    def test_discovery_precision_recall_and_no_excluded_reads(self):
        report, opened = self.recorded_sync()
        self.assertEqual(sorted(report['selected']), sorted(self.discovery['selected']))
        allowed = {p.casefold() for p in self.discovery['selected'] + self.discovery['metadata_inputs'] + self.discovery['policy_inputs']}
        self.assertEqual(opened, allowed)
        for excluded in self.discovery['excluded']:
            self.assertNotIn(excluded.casefold(), opened)
        stored = index_text(self.index)
        for token in (b'canary', b'fictional', b'execute', b'excluded', os.fsencode(str(self.root)).lower()):
            self.assertNotIn(token, stored)

    def test_overview_metadata_and_dwindy_md_are_data(self):
        (self.root/'outside-secret.txt').write_text('OUTSIDE_SECRET_CANARY', encoding='utf-8')
        synchronize(self.config)
        index = self.open()
        overview = index.connection.execute("SELECT c.id FROM chunks c JOIN documents d ON d.id=c.document_id WHERE d.source_path='@project/overview'").fetchall()
        text = '\n'.join(index.connection.execute('SELECT body FROM chunks_fts WHERE rowid=?', row).fetchone()[0] for row in overview)
        for required in self.discovery['overview_required']:
            self.assertIn(required, text)
        for hidden in ('ignored/', 'secrets/', 'node_modules/', 'dist/', 'drafts', 'internal', 'unselected'):
            self.assertNotIn(hidden, text)
        metadata = index.search('lantern worker version')[0]
        self.assertEqual(metadata.source.source_type, 'project_metadata')
        self.assertIn('not proof of active components', metadata.text)
        passage = index.search('TANGERINE')[0]
        self.assertEqual((passage.source.source_path, passage.source.source_type), ('DWINDY.md', 'project_documentation'))
        self.assertEqual(passage.source.project_id, 'lantern')
        prompt = evidence_question('What does the project file say?', [passage])
        self.assertTrue(prompt.startswith('Project snapshot observations are limited to selected files.'))
        self.assertIn('Untrusted local passages:', prompt)
        self.assertNotIn(b'outside_secret', index_text(self.index))

    def test_frozen_benchmark_gates(self):
        synchronize(self.config)
        index = self.open()
        result = evaluate(lambda query: [p.mapping() for p in index.search(query)])
        overall = result['overall']
        self.assertGreaterEqual(overall['hit3'], .85)
        self.assertGreaterEqual(overall['mrr3'], .70)
        self.assertEqual(overall['duplicate_slots'], 0)
        for case in result['cases']:
            if case['id'] in ('unavailable_3', 'unavailable_4'):
                self.assertEqual(case['returned'], 0, case['id'])
        texts = {p.source.source_path: p for q in ('reserve_equipment', 'recordReturn assetTag') for p in index.search(q)}
        files = load('files.json')
        for passage in texts.values():
            if not passage.source.source_path.startswith('@'):
                original = files[passage.source.source_path].replace('\r\n', '\n')
                self.assertEqual(original[passage.source.start:passage.source.end], passage.text)

    def test_lifecycle_update_delete_and_unchanged_chunk_ids(self):
        first = synchronize(self.config)
        index = RetrievalIndex(self.index)
        loans = [row[0] for row in index.connection.execute("SELECT chunk_key FROM chunks c JOIN documents d ON d.id=c.document_id WHERE d.source_path='src/loans.py' ORDER BY ordinal")]
        index.close()
        apply_lifecycle(self.root)
        dry = synchronize(self.config, dry_run=True)
        self.assertNotIn('write', dry)
        with closing(RetrievalIndex(self.index)) as unchanged:
            self.assertEqual(unchanged.project_snapshot['snapshot_id'], first['snapshot_id'])
        second = synchronize(self.config)
        self.assertNotEqual(second['snapshot_id'], first['snapshot_id'])
        self.assertEqual((second['added'], second['deleted']), (dry['added'], dry['deleted']))
        self.assertIn('docs/new.md', second['selected'])
        self.assertNotIn('docs/nested/README.md', second['selected'])
        self.assertNotIn('docs/tasks/reservations.md', second['selected'])
        index = self.open()
        self.assertIn('nine days', index.search('loan duration')[0].text)
        self.assertEqual(index.search('silver register')[0].source.source_path, 'docs/new.md')
        self.assertEqual(index.search('cobalt ledger'), ())
        self.assertNotIn('docs/tasks/reservations.md', [p.source.source_path for p in index.search('reserve microscope')])
        self.assertEqual([row[0] for row in index.connection.execute("SELECT chunk_key FROM chunks c JOIN documents d ON d.id=c.document_id WHERE d.source_path='src/loans.py' ORDER BY ordinal")], loans)
        self.assertEqual(index.project_snapshot['snapshot_id'], second['snapshot_id'])

    def test_failed_sync_preserves_snapshot_a(self):
        first = synchronize(self.config)
        before = self.index.read_bytes()
        apply_lifecycle(self.root)
        (self.root/'host/docs/bad.md').write_bytes(b'binary\x00text')
        with self.assertRaises(ValueError): synchronize(self.config)
        (self.root/'host/docs/bad.md').unlink()
        original = project.write_documents
        def changed_during_write(*args, precommit, **kwargs):
            def touch_then_check():
                (self.root/'host/docs/policy.md').write_text('# Workshop policy\n\nTen days.\n', encoding='utf-8')
                precommit()
            return original(*args, precommit=touch_then_check, **kwargs)
        with patch.object(project, 'write_documents', changed_during_write):
            with self.assertRaisesRegex(ValueError, 'changed'): synchronize(self.config)
        self.assertEqual(self.index.read_bytes(), before)
        index = self.open()
        self.assertEqual(index.project_snapshot['snapshot_id'], first['snapshot_id'])
        self.assertIn('eight days', index.search('loan duration')[0].text)

    def test_dry_run_creates_nothing(self):
        report = synchronize(self.config, dry_run=True)
        self.assertTrue(report['dry_run'])
        self.assertEqual(report['added'], 12)
        self.assertFalse(self.index.exists())

    def test_hard_exclusions_override_selection_negation_and_manifests(self):
        (self.root/'host/secrets/tool.py').write_text('x = 1\n', encoding='utf-8')
        (self.root/'host/src/settings.local.json').write_text('{}', encoding='utf-8')
        for selection in (dict(source_files=['secrets/tool.py']), dict(config_files=['src/settings.local.json']),
                          dict(source_files=['src/../secrets/tool.py']), dict(source_files=['C:/x.py']),
                          dict(source_files=['src/unselected.txt']), dict(source_files=['ignored/notes.md'])):
            write_config(self.root, **selection)
            with self.assertRaises(ValueError, msg=selection): synchronize(self.config)
        self.assertFalse(self.index.exists())
        (self.root/'extra.md').write_text('# Extra\n\nOrdinary amber manual text.\n', encoding='utf-8')
        for path in ('host/secrets/token.txt', 'host/docs/private.txt'):
            (self.root/'collection.toml').write_text(f'[[documents]]\nid="x"\npath="{path}"\nname="x"\n', encoding='utf-8')
            write_config(self.root, documents_manifest='collection.toml')
            with self.assertRaisesRegex(ValueError, 'bypass'): synchronize(self.config)
        (self.root/'collection.toml').write_text('[[documents]]\nid="extra"\npath="extra.md"\nname="Extra"\n', encoding='utf-8')
        synchronize(self.config)
        passage = self.open().search('amber manual')[0]
        self.assertEqual((passage.source.document_id, passage.source.source_type, passage.source.project_id), ('m_extra', 'local_text', None))

    def test_configuration_validation(self):
        for overrides in (dict(unknown=1), dict(project_id='bad id'), dict(name=''), dict(root='https://host/x'),
                          dict(root='//server/share'), dict(index_path='host/index.sqlite3'), dict(documentation_dirs='docs')):
            write_config(self.root, **overrides)
            with self.assertRaises(ValueError, msg=overrides): synchronize(self.config)
        write_config(self.root, root=None)
        with self.assertRaises(ValueError): synchronize(self.config)

    def test_index_ownership_is_never_repurposed(self):
        (self.root/'a.txt').write_text('cedar', encoding='utf-8')
        (self.root/'collection.toml').write_text('[[documents]]\nid="a"\npath="a.txt"\nname="a"\n', encoding='utf-8')
        manifest_sync(self.root/'collection.toml', self.index)
        before = self.index.read_bytes()
        with self.assertRaisesRegex(ValueError, 'ownership'): synchronize(self.config)
        self.assertEqual(self.index.read_bytes(), before)
        self.index.unlink()
        synchronize(self.config)
        with self.assertRaisesRegex(ValueError, 'ownership'): manifest_sync(self.root/'collection.toml', self.index)
        write_config(self.root, project_id='other')
        with self.assertRaisesRegex(ValueError, 'ownership'): synchronize(self.config)

    def test_links_junctions_and_hard_links_are_rejected(self):
        outside = self.root/'outside'
        outside.mkdir()
        (outside/'a.md').write_text('JUNCTION_CANARY', encoding='utf-8')
        os.link(self.root/'host/docs/policy.md', self.root/'policy-copy.md')
        with self.assertRaisesRegex(ValueError, 'unlinked'): synchronize(self.config)
        (self.root/'policy-copy.md').unlink()
        made = False
        if os.name == 'nt':
            made = subprocess.run(['cmd', '/c', 'mklink', '/J', str(self.root/'host/docs/linked'), str(outside)],
                                  capture_output=True).returncode == 0
        else:
            os.symlink(outside, self.root/'host/docs/linked', target_is_directory=True)
            made = True
        if made:
            with self.assertRaisesRegex(ValueError, 'Links and reparse points'): synchronize(self.config)
            self.assertFalse(self.index.exists())
            write_config(self.root, exclude=['docs/internal/**', 'docs/linked'])
            synchronize(self.config)
            self.assertNotIn(b'junction_canary', index_text(self.index))
            os.rmdir(self.root/'host/docs/linked')
        try:
            os.symlink(outside/'a.md', self.root/'host/docs/link.md')
        except OSError:
            return  # Unprivileged Windows accounts cannot create symbolic links.
        with self.assertRaisesRegex(ValueError, 'Links and reparse points'): synchronize(self.config)

    def test_source_chunks_follow_declarations_without_analysis(self):
        text = 'import os\n\n@cached\ndef first():\n    return 1\n\nclass Second:\n    pass\n\nexport async function third() {}\n'
        spans = list(source_chunks(text))
        starts = [text[start:end].split('\n', 1)[0] for _, start, end in spans]
        self.assertEqual(starts, ['import os', '@cached', 'class Second:', 'export async function third() {}'])
        for _, start, end in spans:
            self.assertEqual(text[start:end], text[start:end].strip())
        (self.root/'host/src/unselected.py').write_text('x = 1\n' + 'y' * 1001 + '\n', encoding='utf-8')
        write_config(self.root, source_files=['src/unselected.py'])
        with self.assertRaisesRegex(ValueError, 'minified'): synchronize(self.config)
        (self.root/'host/src/unselected.py').write_text('# @generated\nx = 1\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Generated'): synchronize(self.config)
        # Prose is exempt from both code checks: long paragraphs and editing advice are normal.
        write_config(self.root)
        (self.root/'host/docs/long.md').write_text('Do not edit the ledger by hand.\n\n' + 'walnut ' * 400 + '\n', encoding='utf-8')
        self.assertIn('docs/long.md', synchronize(self.config)['selected'])
        self.assertTrue(self.open().search('walnut'))

    def test_pathspec_is_only_required_for_projects(self):
        code = ('import sys; sys.modules["pathspec"]=None; import dwindy.api, dwindy.ingest, dwindy.retrieval, dwindy.core;'
                'from dwindy.project_policy import Policy\n'
                'try: Policy(".")\n'
                'except ValueError as e: print(e)')
        result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, cwd=self.root,
                                env=dict(os.environ, PYTHONPATH=str(Path(__file__).parents[1]/'src')))
        self.assertIn('dwindy[project]', result.stdout, result.stderr)

    def test_cli_dry_run_and_failure_message(self):
        with patch('sys.stdout', new_callable=io.StringIO) as out:
            self.assertEqual(project.main(['sync', '--config', str(self.config), '--dry-run']), 0)
        self.assertIn('"dry_run": true', out.getvalue())
        write_config(self.root, unknown=1)
        with patch('sys.stderr', new_callable=io.StringIO) as err:
            self.assertEqual(project.main(['sync', '--config', str(self.config)]), 1)
        self.assertIn('Project sync failed', err.getvalue())


if __name__ == '__main__':
    unittest.main()
