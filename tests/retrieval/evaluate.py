"""Frozen model-free evaluator: search(query) -> ordered passage mappings.

Required mapping fields: document_id, start, end, text. Offsets are Unicode
codepoints in LF-normalized source text. Score only top three returned passages.
"""
from collections import defaultdict
import json
from pathlib import Path

ROOT = Path(__file__).parent


def evaluate(search, split=None):
    records = []
    for line in (ROOT / "queries.jsonl").read_text(encoding="utf-8").splitlines():
        case = json.loads(line)
        if split is not None and case["split"] != split:
            continue
        matches = list(search(case["query"]))[:3]
        ranks = [rank for rank, match in enumerate(matches, 1) if any(
            match["document_id"] == gold["document_id"] and match["start"] <= gold["start"]
            and match["end"] >= gold["end"] for gold in case["gold"])]
        first = min(ranks, default=0)
        records.append(dict(id=case["id"], category=case["category"], split=case["split"],
            answerable=bool(case["gold"]), negative_kind=case["negative_kind"],
            hit1=int(first == 1), hit3=int(first > 0), rr3=1/first if first else 0,
            returned=len(matches), duplicates=len(matches)-len({m["text"] for m in matches}),
            documents=[m["document_id"] for m in matches]))
    def aggregate(group):
        positive = [r for r in group if r["answerable"]]
        negatives = [r for r in group if not r["answerable"]]
        return dict(cases=len(group), answerable=len(positive),
            **{metric: sum(r[metric] for r in positive)/len(positive) if positive else None
               for metric in ("hit1", "hit3", "rr3")},
            negative_nonempty=sum(r["returned"] > 0 for r in negatives),
            duplicate_slots=sum(r["duplicates"] for r in group))
    return dict(overall=aggregate(records),
                categories={key: aggregate([r for r in records if r["category"] == key])
                            for key in sorted({r["category"] for r in records})},
                splits={key: aggregate([r for r in records if r["split"] == key])
                        for key in sorted({r["split"] for r in records})}, cases=records)
