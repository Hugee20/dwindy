"""Frozen Reach v2 (H1) evaluation: reference selection algorithm, selection metrics, notice rows.

Self-contained on purpose: word lists are copied verbatim, so later runtime edits cannot change
this specification. The runtime implementation must reproduce reference_select() exactly for the
constants chosen on development. Nothing here contacts a provider or calls a model.
"""
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).parent

# ---- Frozen text handling -------------------------------------------------------------------
# Tokenizer and stopwords copied verbatim from the frozen M6 retrieval (dwindy.retrieval).
STOPWORDS = frozenset("a an the is are was were be been being to of in on at for from with and or not by as it its this that these those what which who where when why how can could would should may must do does did i we you they their our your me my under than then only".split())
# Copied verbatim from the frozen v1 minimizer (dwindy.reach.NOT_A_SUBJECT).
NOT_A_SUBJECT = frozenset("latest newest newer recent recently current currently now today right week".split()) | frozenset(
    "about on regarding any anything something info information update updates please tell".split())
EDITOR_MARK = re.compile(r"\[(?:update|citation needed|clarification needed|\d+|[a-z])\]", re.IGNORECASE)
BOUNDARY = re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9"“(])')
CLOSERS = '"”’)'
# Current-state predicates, matched as whole-word phrases on the token sequence.
PREDICATES = ("latest", "current", "currently", "most recent", "newest", "as of", "incumbent")

# Hard limits (approved; not tunable). Characters are Python code points of sentence text only.
MAX_SENTENCES, MAX_PER_ARTICLE, MAX_CHARS = 3, 2, 600
# The only tunable constants, initial values, and the only values development tuning may choose.
DEFAULTS = dict(predicate_weight=1.0, year_weight=1.0, min_score=2.0)
GRID = dict(predicate_weight=(0, 0.5, 1, 1.5, 2), year_weight=(0, 0.5, 1, 1.5, 2),
            min_score=(1, 1.5, 2, 2.5, 3, 3.5, 4))

# Gates applied once to holdout (README.md).
GATES = dict(answer_recall_min=0.8, abstention_min=0.75, caps=1.0, attribution=1.0, selection_p95_ms=5.0)


def words(text):
    return [t.casefold() for t in re.findall(r"[^\W_]+", text or "", re.UNICODE)]


def split_sentences(text):
    """Remove editor markers, then split after . ! ? when whitespace is followed by A-Z, 0-9 or an opening mark."""
    return [part.strip() for part in BOUNDARY.split(EDITOR_MARK.sub("", text)) if part.strip()]


def eligible(sentence):
    """A complete sentence: starts with an uppercase letter, digit or opening mark; ends with . ! ? (optionally closed)."""
    first, last = sentence[:1], sentence.rstrip(CLOSERS)[-1:]
    return (len(sentence) <= MAX_CHARS and bool(first) and (first.isupper() or first.isdigit() or first in '"“(')
            and last in ".!?")


def subject_terms(query):
    """Distinct terms of the minimized query that name the subject, in query order."""
    return list(dict.fromkeys(t for t in words(query) if t not in STOPWORDS and t not in NOT_A_SUBJECT
                              and len(t) > 1 and not t.isdigit()))


def has_phrase(tokens, phrase):
    target = phrase.split()
    return any(tokens[i:i + len(target)] == target for i in range(len(tokens) - len(target) + 1))


def candidates(results):
    """(rank, index, title, url, sentence) for every sentence; exact repeats are kept once (first occurrence)."""
    seen, out = set(), []
    for rank, result in enumerate(results):
        for index, sentence in enumerate(split_sentences(result["text"])):
            key = " ".join(sentence.casefold().split())
            if key not in seen:
                seen.add(key)
                out.append(dict(rank=rank, index=index, title=result["title"], url=result["url"], sentence=sentence))
    return out


def features(sentence, subjects, year):
    tokens = words(sentence)
    present = set(tokens)
    hits = sum(term in present for term in subjects)
    predicate = int(any(has_phrase(tokens, p) for p in PREDICATES))
    recent = int(any(len(t) == 4 and t.isdigit() and year - 1 <= int(t) <= year for t in tokens))
    return hits, predicate, recent


def reference_select(results, query, year, predicate_weight=DEFAULTS["predicate_weight"],
                     year_weight=DEFAULTS["year_weight"], min_score=DEFAULTS["min_score"]):
    """The frozen H1 algorithm. results: v1-parsed [{title, url, text}] in provider order.
    year: the server-local year at decision time (replay uses the snapshot's capture year)."""
    subjects = subject_terms(query)
    if not subjects:
        return []
    ranked = []
    for c in candidates(results):
        if not eligible(c["sentence"]):
            continue
        hits, predicate, recent = features(c["sentence"], subjects, year)
        score = hits + predicate_weight * predicate + year_weight * recent
        if hits >= 1 and score >= min_score:
            ranked.append((-score, -predicate, -recent, c["rank"], c["index"], c))
    ranked.sort(key=lambda item: item[:5])
    chosen, per_article, total = [], {}, 0
    for *_, c in ranked:
        if len(chosen) == MAX_SENTENCES:
            break
        if per_article.get(c["url"], 0) == MAX_PER_ARTICLE or total + len(c["sentence"]) > MAX_CHARS:
            continue  # Never truncate: a sentence that does not fit is skipped, and the next is tried.
        chosen.append(dict(title=c["title"], url=c["url"], sentence=c["sentence"]))
        per_article[c["url"]] = per_article.get(c["url"], 0) + 1
        total += len(c["sentence"])
    return chosen  # Rank order: strongest first.


def load(name):
    return [json.loads(line) for line in (ROOT/name).read_text(encoding="utf-8").splitlines()]


def evaluate_selection(select_fn, split=None):
    """select_fn(case) -> [{title, url, sentence}]. Cases come from labels.jsonl."""
    rows = []
    for case in load("labels.jsonl"):
        if split and case["split"] != split:
            continue
        supplied = list(select_fn(case))
        pairs = {(s["title"], s["sentence"]) for s in supplied}
        gold = {(g["title"], g["sentence"]) for g in case["gold"]}
        texts = {(r["title"], r["url"]): set(split_sentences(r["text"])) for r in case["results"]}
        per = {}
        for s in supplied:
            per[s["url"]] = per.get(s["url"], 0) + 1
        rows.append(dict(id=case["id"], split=case["split"], answer_present=case["answer_present"],
            found=bool(pairs & gold), abstained=not supplied,
            caps_ok=len(supplied) <= MAX_SENTENCES and max(per.values(), default=0) <= MAX_PER_ARTICLE
                    and sum(len(s["sentence"]) for s in supplied) <= MAX_CHARS,
            attributed=all(s["sentence"] in texts.get((s["title"], s["url"]), set()) for s in supplied),
            distractors=len(pairs & {(d["title"], d["sentence"]) for d in case["distractors"]}),
            chars=sum(len(s["sentence"]) for s in supplied), supplied=supplied))

    def summarize(group):
        answerable = [r for r in group if r["answer_present"]]
        unanswerable = [r for r in group if not r["answer_present"]]
        return dict(cases=len(group), answerable=len(answerable),
            answer_recall=sum(r["found"] for r in answerable) / len(answerable) if answerable else None,
            abstention=sum(r["abstained"] for r in unanswerable) / len(unanswerable) if unanswerable else None,
            caps=sum(r["caps_ok"] for r in group) / len(group) if group else None,
            attribution=sum(r["attributed"] for r in group) / len(group) if group else None,
            distractors_supplied=sum(r["distractors"] for r in group),
            max_chars=max((r["chars"] for r in group), default=0))
    return dict(overall=summarize(rows), splits={k: summarize([r for r in rows if r["split"] == k])
                for k in sorted({r["split"] for r in rows})}, cases=rows)


def selection_gates(holdout_summary):
    return dict(answer_recall=holdout_summary["answer_recall"] >= GATES["answer_recall_min"],
                abstention=holdout_summary["abstention"] >= GATES["abstention_min"],
                caps=holdout_summary["caps"] == 1.0, attribution=holdout_summary["attribution"] == 1.0)


def evaluate_notice(run_fn):
    """run_fn(row) -> {notice: bool, network_calls: int}."""
    rows = []
    for row in load("notice.jsonl"):
        observed = dict(run_fn(row))
        ok = observed.get("notice") == row["expected"]["notice"] and observed.get("network_calls", 0) == 0
        rows.append(dict(id=row["id"], correct=ok, observed=observed))
    return dict(correct=sum(r["correct"] for r in rows), cases=len(rows), rows=rows)


def reach_adopted(*args, **kwargs):
    """Reach v2 adoption uses the frozen v1 rule unchanged (tests/reach/evaluate.py)."""
    sys.path.insert(0, str(ROOT.parent))
    from reach.evaluate import reach_adopted as v1_rule
    return v1_rule(*args, **kwargs)
