import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parent))
from reach_h2.evaluate import (FIELDS, MAX_CHARS, MAX_EXPANSION_URL_BYTES, clean_value, expansion_url, h1_url,
                               holdout_ids, infobox_fields, load, reference_select, replay_expand, search_query,
                               subject_terms, unit_text, words)
from dwindy import reach

ROOT = Path(__file__).parent/'reach_h2'
FROZEN = {'reach': '16b2f1a129038b4552b7b3a17b0cc3de3337b070e54efa5e1780409afe025eda',
          'reach_v2': '9e963207efb08074aa275d0c0d50f7a2bae98c5e60d51c65de29d4fc8d24dc08'}
MANIFESTS = ('FREEZE.json', 'FREEZE_CAPTURE.json', 'FREEZE_LABELS.json')
SEAL_B = '461b6ee8a4d99ad2d7f8b61a7abc0de92976cd67e591122a1df7e8dd77ff778a'


def page(title, wikitext='', extract='', rank=0):
    return dict(title=title, url='https://en.wikipedia.org/wiki/' + title.replace(' ', '_'), rank=rank,
                extract=extract, wikitext=wikitext)


def infobox(**fields):
    return '{{Infobox x\n' + ''.join(f'| {k} = {v}\n' for k, v in fields.items()) + '}}\nLead.'


class ReachH2FixtureTests(unittest.TestCase):
    def test_v1_and_h1_are_untouched(self):
        for name, digest in FROZEN.items():
            path = Path(__file__).parent/name/'FREEZE.json'
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest, name)

    def test_frozen_hashes_cover_every_file(self):
        # Evaluation (FREEZE.json), then captures and labels as they are taken (README.md).
        manifests = [m for m in MANIFESTS if (ROOT/m).exists()]
        self.assertIn('FREEZE.json', manifests)
        frozen = {}
        for manifest in manifests:
            entries = json.loads((ROOT/manifest).read_text(encoding='utf-8'))
            self.assertFalse(set(entries) & set(frozen), manifest)  # Each file in exactly one manifest.
            frozen.update(entries)
        present = {p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*')
                   if p.is_file() and p.name not in MANIFESTS and '__pycache__' not in p.parts}
        self.assertEqual(set(frozen), present)
        for path, digest in frozen.items():
            self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(), digest, path)

    def test_author_b_seal(self):
        self.assertEqual(hashlib.sha256((ROOT/'questions_b.jsonl').read_bytes()).hexdigest(), SEAL_B)

    def test_adversarial_parser_cases(self):
        cases = load('parser_cases.jsonl')
        self.assertGreaterEqual(len(cases), 39)
        for case in cases:
            got = {k: list(v) for k, v in infobox_fields(case['wikitext']).items()}
            self.assertEqual(got, case['expected'], case['id'])

    def test_subject_rule_cases_and_counterexamples(self):
        cases = load('subject_cases.jsonl')
        self.assertEqual({c['kind'] for c in cases}, {'relation', 'counterexample', 'limitation'})
        for case in cases:
            query, _ = reach.minimize(case['message'])  # The frozen v1 minimizer still yields the recorded query.
            self.assertEqual(query, case['query'], case['message'])
            self.assertEqual(subject_terms(query, case['message']), case['expected_subjects'], case['message'])
            searched = search_query(query, case['message'])
            self.assertEqual(searched, case['expected_search'], case['message'])
            self.assertTrue(set(words(searched)) <= set(words(query)))  # Only ever a subset of the v1 query.

    def test_request_shapes(self):
        self.assertEqual(h1_url('latest version android'),
                         reach.WikipediaBackend(transport=lambda url: None).url('latest version android'))
        self.assertIsNone(expansion_url('T', '{{x|' + 'y' * MAX_EXPANSION_URL_BYTES + '}}'))
        self.assertTrue(expansion_url('Pope', '{{Current Pope}}').startswith('https://en.wikipedia.org/w/api.php?'))

    def test_field_ranking_rejects_distractors_and_partial_coverage(self):
        pages = [page('List of spouses of prime ministers of Japan', infobox(incumbent='[[Spouse]]'), rank=0),
                 page('Prime Minister of Japan', infobox(incumbent='[[Head]]'), rank=1),
                 page('Minister of Defense (Japan)', infobox(incumbent='[[Defense]]'), rank=2)]
        units, _ = reference_select(pages, 'current prime minister japan', 'Who is the current prime minister of Japan?')
        self.assertEqual([u['value'] for u in units if u['kind'] == 'field'], ['Head'])  # One per field name, best title.
        pages = [page('Python (programming language)', infobox(latest_release_version='3.14.7'))]
        units, _ = reference_select(pages, 'latest version go programming language', 'What is the latest version of Go programming language?')
        self.assertEqual(units, [])  # Full coverage: "go" is in no title or field name.

    def test_key_people_keeps_only_matching_roles(self):
        pages = [page('Microsoft', infobox(key_people='{{ubl|[[Satya Nadella]] (chairman and [[Chief executive officer|CEO]])|[[Amy Hood]] (CFO)}}'))]
        units, _ = reference_select(pages, 'current ceo microsoft', 'Who is the current CEO of Microsoft?')
        self.assertEqual([unit_text(u) for u in units], ['Key people: Satya Nadella (chairman and CEO)'])

    def test_expansion_is_single_conditional_and_without_fallback(self):
        calls = []
        def expand(title, template):
            calls.append((title, template))
            return None
        pages = [page('Pope', infobox(incumbent='{{Current Pope}}'), rank=0),
                 page('Pope (title)', infobox(incumbent='[[Other]]'), rank=1)]
        units, requested = reference_select(pages, 'current pope', 'Who is the current pope?', expand=expand)
        self.assertEqual((units, requested, calls), ([], 1, [('Pope', '{{Current Pope}}')]))  # No fallback to another article.
        units, requested = reference_select(pages, 'current pope', 'Who is the current pope?', expand=None)
        self.assertEqual((units, requested), ([], 0))
        units, _ = reference_select(pages, 'current pope', 'Who is the current pope?',
                                    expand=lambda t, x: '[[Pope Leo&nbsp;XIV]]<span style="display:none"></span>')
        self.assertEqual([(u['value'], u['expanded']) for u in units], [('Pope Leo XIV', True)])
        unqualified = [page('Rust (programming language)', infobox(latest_release_version='{{wikidata|x}}'))]
        reference_select(unqualified, 'latest version go', 'What is the latest version of Go?', expand=expand)
        self.assertEqual(len(calls), 1)  # Never expanded for a field that did not qualify.

    def test_packet_limits_skip_rather_than_truncate(self):
        long_sentence = 'The current Widget release is ' + 'very ' * 110 + 'new.'
        extract = ('The current Widget release is 9. ' + long_sentence + ' The current Widget release is 9 today. '
                   'Currently, Widget 9 is the latest Widget.')  # The long sentence fits alone, not after the first.
        units, _ = reference_select([page('Widget', extract=extract)], 'current widget', 'What is the current Widget?')
        self.assertLessEqual(sum(len(unit_text(u)) for u in units), MAX_CHARS)
        self.assertNotIn(long_sentence, [u.get('sentence') for u in units])
        self.assertEqual([u['sentence'] for u in units],
                         ['The current Widget release is 9.', 'Currently, Widget 9 is the latest Widget.'])
        self.assertNotIn('The current Widget release is 9 today.', [u['sentence'] for u in units])  # Near-duplicate.
        self.assertEqual(reference_select([page('Widget', extract=extract)], 'latest', 'latest')[0], [])  # No subject.
        self.assertEqual(reference_select([page('Widget', extract=extract)], 'latest news', 'latest news')[0], [])  # news is not new.

    def test_replay_refuses_uncaptured_or_oversized_expansions(self):
        rec = dict(expansions=[dict(title='Pope', template='{{Current Pope}}', status=200, bytes=1025,
                                    body=dict(expandtemplates=dict(wikitext='[[A]]')))])
        self.assertIsNone(replay_expand(rec)('Pope', '{{Current Pope}}'))
        self.assertIsNone(replay_expand(rec)('Pope', '{{Other}}'))

    def test_reserve_rule(self):
        def row(i, role, order, author, available):
            return dict(id=i, split='holdout', role=role, order=order, author=author,
                        answer_present_h1=False, answer_present_h2=available)
        labels = [row(f'm{i}', 'main', i, 'a', i < 10) for i in range(36)]
        labels += [row(f'{a}r{i}', 'reserve', i, a, True) for i in (1, 2, 3) for a in 'ab']
        self.assertEqual(holdout_ids(labels)[36:], ['ar1', 'br1'])  # Declared order, only until 12.

    def test_question_files(self):
        dev = load('dev_questions.jsonl')
        self.assertEqual(len(dev), 26)
        self.assertEqual(len({q['message'] for q in dev}), 26)
        for name in ('questions_a.jsonl', 'questions_b.jsonl'):
            rows = load(name)
            self.assertEqual(sum(r['role'] == 'main' for r in rows), 18, name)
            self.assertEqual(sum(r['role'] == 'reserve' for r in rows), 6, name)
            self.assertFalse({r['message'].casefold() for r in rows} & {q['message'].casefold() for q in dev}, name)

    def test_whitelist_and_cleaner_basics(self):
        self.assertEqual(FIELDS, ('incumbent', 'holder', 'key_people', 'latest_release_version'))
        self.assertEqual(clean_value('{{#if:x|a|b}}'), ('unsupported', ''))
        self.assertEqual(clean_value('[[A|B]]'), ('ok', 'B'))


if __name__ == '__main__':
    unittest.main()
