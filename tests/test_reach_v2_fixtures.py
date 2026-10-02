from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parent))
from reach_v2.evaluate import (DEFAULTS, GRID, MAX_CHARS, MAX_PER_ARTICLE, MAX_SENTENCES, GATES, eligible,
                               evaluate_notice, evaluate_selection, load, reference_select, selection_gates,
                               split_sentences, subject_terms)

ROOT = Path(__file__).parent/'reach_v2'
V1 = Path(__file__).parent/'reach'


class ReachV2FixtureTests(unittest.TestCase):
    def test_frozen_hashes_cover_every_file(self):
        frozen = json.loads((ROOT/'FREEZE.json').read_text(encoding='utf-8'))
        present = {p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*')
                   if p.is_file() and p.name != 'FREEZE.json' and '__pycache__' not in p.parts}
        self.assertEqual(set(frozen), present)
        for path, digest in frozen.items():
            self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(), digest, path)

    def test_v1_is_untouched(self):
        self.assertEqual(hashlib.sha256((V1/'FREEZE.json').read_bytes()).hexdigest(),
                         '16b2f1a129038b4552b7b3a17b0cc3de3337b070e54efa5e1780409afe025eda')

    def test_labels_composition_and_gold_validity(self):
        labels = load('labels.jsonl')
        self.assertEqual(Counter(l['split'] for l in labels), {'dev': 13, 'holdout': 14})
        self.assertEqual(Counter((l['split'], l['answer_present']) for l in labels),
                         {('dev', True): 7, ('dev', False): 6, ('holdout', True): 4, ('holdout', False): 10})
        holdout_ids = {p.stem for p in (ROOT/'holdout').glob('*.json')}
        self.assertEqual({l['snapshot']['id'] for l in labels if l['split'] == 'holdout'}, holdout_ids)
        for label in labels:
            self.assertEqual(bool(label['gold']), label['answer_present'], label['id'])
            texts = {r['title']: split_sentences(r['text']) for r in label['results']}
            for item in label['gold'] + label['distractors']:
                self.assertIn(item['sentence'], texts[item['title']], label['id'])
            self.assertTrue(all(r['url'].startswith('https://en.wikipedia.org/wiki/') for r in label['results']))
            self.assertTrue(subject_terms(label['query']), label['id'])
        for path in (ROOT/'holdout').glob('*.json'):
            record = json.loads(path.read_text(encoding='utf-8'))
            self.assertFalse(record['synthetic'])
            self.assertTrue(record['request_url'].startswith('https://en.wikipedia.org/w/api.php?'))

    def test_reference_algorithm_contract(self):
        self.assertEqual((MAX_SENTENCES, MAX_PER_ARTICLE, MAX_CHARS), (3, 2, 600))
        self.assertTrue(all(DEFAULTS[k] in GRID[k] for k in DEFAULTS))
        self.assertEqual(split_sentences('Python 3.14.6 is out. It works[update].'), ['Python 3.14.6 is out.', 'It works.'])
        self.assertFalse(eligible('In August 2026,'))
        self.assertEqual(subject_terms('latest version android'), ['version', 'android'])
        results = [dict(title='A', url='https://en.wikipedia.org/wiki/A', text='The latest version of Widget is 9. ' * 1
                        + 'Widget ' + 'x' * 590 + '. The current Widget release is 9 as of 2026.'),
                   dict(title='B', url='https://en.wikipedia.org/wiki/B', text='The latest Widget is 9.')]
        chosen = reference_select(results, 'latest widget', 2026)
        self.assertLessEqual(sum(len(c['sentence']) for c in chosen), 600)
        self.assertEqual(chosen[0]['sentence'], 'The current Widget release is 9 as of 2026.')  # Highest score first.
        self.assertTrue(all(len(c['sentence']) < 600 for c in chosen))  # The 597-character sentence never fits after it.
        self.assertEqual(reference_select(results, 'latest', 2026), [])  # No subject term: abstain.

    def test_evaluators_and_notice_rows(self):
        labels = {l['id']: l for l in load('labels.jsonl')}
        oracle = evaluate_selection(lambda c: [dict(title=g['title'], url=next(r['url'] for r in c['results'] if r['title'] == g['title']),
                                                    sentence=g['sentence']) for g in c['gold'][:1]])
        holdout = oracle['splits']['holdout']
        self.assertTrue(all(selection_gates(holdout).values()), holdout)
        everything = evaluate_selection(lambda c: [dict(title=r['title'], url=r['url'], sentence=split_sentences(r['text'])[0])
                                                   for r in c['results'][:3]])
        self.assertFalse(selection_gates(everything['splits']['holdout'])['abstention'])
        notice = load('notice.jsonl')
        self.assertEqual(len(notice), 8)
        self.assertEqual(sum(r['expected']['notice'] for r in notice), 4)
        self.assertEqual(evaluate_notice(lambda r: dict(notice=r['expected']['notice'], network_calls=0))['correct'], 8)
        e2e = load('e2e.jsonl')
        self.assertEqual(Counter(e['split'] for e in e2e), {'dev': 12, 'holdout': 14, 'control': 8})
        self.assertTrue(all(f"{e['split']}_{e['snapshot']['id']}" in labels for e in e2e if e['snapshot']))
        rubric = (ROOT/'rubric.md').read_text(encoding='utf-8')
        for phrase in ('unchanged', 'holdout', 'measured', 'tokenizer count', 'C1 versus C2'):
            self.assertIn(phrase, rubric)
        self.assertEqual(GATES['answer_recall_min'], 0.8)


if __name__ == '__main__':
    unittest.main()
