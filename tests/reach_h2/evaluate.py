"""Reach H2 evaluation: reference request shapes, infobox parser, field and sentence selection,
packet assembly and evaluators (README.md).

Self-contained on purpose: word lists are copied verbatim, so later runtime edits cannot change
this specification. The runtime implementation must reproduce reference_select() exactly for the
values chosen on development. Nothing here contacts a provider or calls a model; capture.py is the
only file in this directory that uses the network.
"""
from fractions import Fraction
import html
import json
from pathlib import Path
import re
import statistics
import urllib.parse

ROOT = Path(__file__).parent

# ---- Copied verbatim (frozen M6 tokenizer and stopwords, v1 minimizer words, v2 sentence rules) --
STOPWORDS = frozenset("a an the is are was were be been being to of in on at for from with and or not by as it its this that these those what which who where when why how can could would should may must do does did i we you they their our your me my under than then only".split())
NOT_A_SUBJECT = frozenset("latest newest newer recent recently current currently now today right week".split()) | frozenset(
    "about on regarding any anything something info information update updates please tell".split())
EDITOR_MARK = re.compile(r"\[(?:update|citation needed|clarification needed|\d+|[a-z])\]", re.IGNORECASE)
BOUNDARY = re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9"“(])')
CLOSERS = '"”’)'
PREDICATES = ("latest", "current", "currently", "most recent", "newest", "as of", "incumbent")
API_URL = "https://en.wikipedia.org/w/api.php"
RESULT_URL_PREFIX = "https://en.wikipedia.org/wiki/"

# ---- H2 rules (approved; not tunable) ---------------------------------------------------------
# Relation verbs: lowercase forms are the question's relation, capitalized forms are part of a name.
RELATION_VERBS = frozenset({"win", "won"})
MAX_UNITS, MAX_PER_ARTICLE, MAX_CHARS = 3, 2, 600       # Hard packet limits, as in H1.
MAX_PER_FIELD_NAME = 1                                   # One value per relation (the best-ranked).
SEARCH_LIMIT = 3
MAX_EXTRACT_CHARS = 12000                                # Intro text considered per article.
MAX_WIKITEXT_CHARS = 60000                               # Larger section-0 wikitext: no fields.
MAX_RAW_VALUE_CHARS = 1000                               # Larger raw field value: unsupported.
MAX_VALUE_CHARS = 200                                    # Larger cleaned value: unsupported.
MAX_EXPANSION_URL_BYTES = 1024
MAX_EXPANSION_BODY_BYTES = 1024
MAX_EXPANSIONS = 1                                       # Per turn; never retried.
FIELDS = ("incumbent", "holder", "key_people", "latest_release_version")
LIST_TEMPLATES = frozenset({"ubl", "unbulleted list", "unbulleted_list", "plainlist", "plain list",
                            "hlist", "flatlist", "nowrap"})

# ---- The only tunable values (development only) ------------------------------------------------
GRID = dict(sentence_coverage=(Fraction(1, 2), Fraction(3, 5), Fraction(2, 3), Fraction(3, 4), Fraction(1)),
            order=("fields_first", "interleave"))
DEFAULTS = dict(sentence_coverage=Fraction(2, 3), order="fields_first")

GATES = dict(answer_recall_min=0.8, abstention_min=0.75, caps=1.0, attribution=1.0, selection_p95_ms=10.0,
             tokens_median_max=200, tokens_max=300, requests_per_turn_max=2, network_seconds_max=5.0)
MIN_AVAILABLE_HOLDOUT = 12


# ---- Text ---------------------------------------------------------------------------------------
def words(text):
    return [t.casefold() for t in re.findall(r"[^\W_]+", text or "", re.UNICODE)]


def light_stem(token):
    """Plural stripping only: -ies -> -y, -(s|x|z)es -> -(s|x|z), -s -> '' (never -ss, -us, -is,
    and never for words of four letters or fewer, so "news" never becomes "new")."""
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 3 and token.endswith("es") and token[-3] in "sxz":
        return token[:-2]
    if len(token) > 4 and token.endswith("s") and not token.endswith(("ss", "us", "is")):
        return token[:-1]
    return token


def stems(text):
    return {light_stem(t) for t in words(text)}


def has_phrase(tokens, phrase):
    target = phrase.split()
    return any(tokens[i:i + len(target)] == target for i in range(len(tokens) - len(target) + 1))


def split_sentences(text):
    return [part.strip() for part in BOUNDARY.split(EDITOR_MARK.sub("", text)) if part.strip()]


def eligible(sentence):
    first, last = sentence[:1], sentence.rstrip(CLOSERS)[-1:]
    return (len(sentence) <= MAX_CHARS and bool(first) and (first.isupper() or first.isdigit() or first in '"“(')
            and last in ".!?")


def subject_terms(query, message):
    """Distinct subject terms of the v1-minimized query, in query order, as plural-stripped stems.

    Excluded: stopwords, v1 freshness and filler words, single characters and pure digits, plus two
    general relation rules:
      1. every token inside an occurrence of a current-state phrase (PREDICATES) in the query, so
         "most" in "most recent" and "incumbent" are relations, while "most" elsewhere is not;
      2. "win" / "won" when every occurrence in the original message is lowercase; a capitalized
         occurrence is part of a name and stays a subject term.
    Terms are only ever removed, never added, so the search query stays a subset of the v1 query."""
    tokens = words(query)
    inside = set()
    for phrase in PREDICATES:
        n = len(phrase.split())
        for i in range(len(tokens) - n + 1):
            if tokens[i:i + n] == phrase.split():
                inside.update(range(i, i + n))
    raw = re.findall(r"[^\W_]+", message or "", re.UNICODE)
    relation = {w for w in RELATION_VERBS if all(t == w for t in raw if t.casefold() == w)}
    kept = [t for i, t in enumerate(tokens) if i not in inside and t not in STOPWORDS and t not in NOT_A_SUBJECT
            and len(t) > 1 and not t.isdigit() and t not in relation]
    return list(dict.fromkeys(light_stem(t) for t in kept))


def search_query(query, message):
    """The H2 search text: the raw query terms whose stems are subject terms, in query order."""
    subjects = set(subject_terms(query, message))
    tokens = words(query)
    inside = set()
    for phrase in PREDICATES:
        n = len(phrase.split())
        for i in range(len(tokens) - n + 1):
            if tokens[i:i + n] == phrase.split():
                inside.update(range(i, i + n))
    kept = [t for i, t in enumerate(tokens) if i not in inside and light_stem(t) in subjects]
    return " ".join(dict.fromkeys(kept))


# ---- Request shapes ----------------------------------------------------------------------------
def h1_url(query):
    """v1's exact single combined request (dwindy.reach.WikipediaBackend.url), for the paired capture."""
    return API_URL + "?" + urllib.parse.urlencode(dict(
        action="query", format="json", formatversion="2", generator="search", gsrsearch=query, gsrlimit=3,
        prop="extracts|info", exintro=1, explaintext=1, exsentences=5, exlimit=3, inprop="url",
        list="search", srsearch=query, srlimit=3, srprop="snippet"))


def h2_url(subject_query):
    """H2-R: one request returning full intro text and section-0 wikitext for the top 3 articles."""
    return API_URL + "?" + urllib.parse.urlencode(dict(
        action="query", format="json", formatversion="2", generator="search", gsrsearch=subject_query,
        gsrlimit=SEARCH_LIMIT, prop="extracts|revisions|info", exintro=1, explaintext=1, exlimit=SEARCH_LIMIT,
        rvprop="content", rvslots="main", rvsection=0, inprop="url"))


def expansion_url(title, template):
    """H2-X: expand one field template in its article's context. None when over the URL limit."""
    url = API_URL + "?" + urllib.parse.urlencode(dict(
        action="expandtemplates", format="json", formatversion="2", title=title, text=template, prop="wikitext"))
    return url if len(url.encode("utf-8")) <= MAX_EXPANSION_URL_BYTES else None


def parse_h2(body):
    """[{title, url, rank, extract, wikitext}] in provider order. Malformed parts fail closed."""
    if not isinstance(body, dict) or not isinstance(body.get("query"), dict):
        return []
    pages = body["query"].get("pages")
    if not isinstance(pages, list):
        return []
    ordered = sorted((p for p in pages if isinstance(p, dict) and isinstance(p.get("index"), int)),
                     key=lambda p: p["index"])
    out, seen = [], set()
    for page in ordered:
        title, url = page.get("title"), page.get("fullurl")
        if not isinstance(title, str) or not isinstance(url, str) or not url.startswith(RESULT_URL_PREFIX) or title in seen:
            continue
        seen.add(title)
        extract = page.get("extract") if isinstance(page.get("extract"), str) else ""
        wikitext = ""
        revisions = page.get("revisions")
        if isinstance(revisions, list) and revisions and isinstance(revisions[0], dict):
            main = (revisions[0].get("slots") or {}).get("main") if isinstance(revisions[0].get("slots"), dict) else None
            if isinstance(main, dict) and isinstance(main.get("content"), str):
                wikitext = main["content"]
        out.append(dict(title=title, url=url, rank=len(out), extract=" ".join(extract[:MAX_EXTRACT_CHARS].split()),
                        wikitext=wikitext))
    return out[:SEARCH_LIMIT]


def parse_expansion(body):
    """The expanded wikitext, or None (fail closed)."""
    if not isinstance(body, dict) or not isinstance(body.get("expandtemplates"), dict):
        return None
    text = body["expandtemplates"].get("wikitext")
    return text if isinstance(text, str) else None


# ---- Infobox parser (narrow; fails closed) -----------------------------------------------------
COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
REF_PAIR = re.compile(r"<ref(?:\s[^<>]*)?(?<!/)>.*?</ref\s*>", re.DOTALL | re.IGNORECASE)
REF_SELF = re.compile(r"<ref(?:\s[^<>]*)?/>", re.IGNORECASE)
BREAK = re.compile(r"<br\s*/?>", re.IGNORECASE)
SMALL = re.compile(r"</?small\s*>", re.IGNORECASE)
EMPTY_SPAN = re.compile(r"<span(?:\s[^<>]*)?>\s*</span>", re.IGNORECASE)
LINK = re.compile(r"\[\[([^\[\]|]*)(?:\|([^\[\]]*))?\]\]")
FILE_LINK = re.compile(r"\[\[\s*(?:file|image|category)\s*:", re.IGNORECASE)
EXTERNAL = re.compile(r"\[(?:https?:)?//[^\s\]]+\s+([^\]]+)\]")
BARE_EXTERNAL = re.compile(r"\[(?:https?:)?//[^\]]*\]")
LEFTOVER = ("{{", "}}", "[[", "]]", "|", "<", ">", "{|")


def _split_top(body):
    """Split on '|' outside nested templates and links. None when brackets do not balance."""
    parts, start, braces, links, i = [], 0, 0, 0, 0
    while i < len(body):
        two = body[i:i + 2]
        if two == "{{":
            braces, i = braces + 1, i + 2
        elif two == "}}":
            braces, i = braces - 1, i + 2
        elif two == "[[":
            links, i = links + 1, i + 2
        elif two == "]]":
            links, i = links - 1, i + 2
        else:
            if body[i] == "|" and braces == 0 and links == 0:
                parts.append(body[start:i])
                start = i + 1
            i += 1
        if braces < 0 or links < 0:
            return None
    if braces or links:
        return None
    parts.append(body[start:])
    return parts


def find_infobox(wikitext):
    """The inner text of the first top-level {{Infobox ...}} template, or None."""
    if not isinstance(wikitext, str) or len(wikitext) > MAX_WIKITEXT_CHARS:
        return None
    text = COMMENT.sub("", wikitext)
    if "<!--" in text:
        return None  # Unterminated comment.
    depth, start, i = 0, None, 0
    while i < len(text):
        two = text[i:i + 2]
        if two == "{{":
            if depth == 0:
                start = i
            depth, i = depth + 1, i + 2
            continue
        if two == "}}":
            depth, i = depth - 1, i + 2
            if depth < 0:
                return None
            if depth == 0:
                inner = text[start + 2:i - 2]
                if inner.split("|", 1)[0].strip().casefold().startswith("infobox"):
                    # Template-parameter and table syntax would break '|' splitting: fail closed.
                    return None if "{{{" in inner or "{|" in inner else inner
            continue
        i += 1
    return None


def infobox_params(wikitext):
    """{normalized name: [raw values]} for the first top-level infobox; None when absent or malformed."""
    inner = find_infobox(wikitext)
    if inner is None:
        return None
    parts = _split_top(inner)
    if parts is None:
        return None
    params = {}
    for part in parts[1:]:
        name, sep, value = part.partition("=")
        if not sep or any(mark in name for mark in ("{{", "[[", "<")):
            continue  # Positional or unusual parameter.
        key = "_".join(name.split()).casefold()
        params.setdefault(key, []).append(value)
    return params


def _list_items(inner):
    """Items of a list template's inner text (name|item|item or plainlist '* item' lines)."""
    parts = _split_top(inner)
    if parts is None:
        return None
    items = []
    for part in parts[1:]:
        if re.match(r"^\s*[A-Za-z_][\w ]*=", part):
            continue  # Named parameter such as class= or style=.
        lines = [line.strip()[1:] if line.strip().startswith("*") else line for line in part.split("\n")]
        items.extend(line.strip() for line in lines if line.strip())
    return items


def _innermost_template(text):
    """(start, end) of a template containing no other template, or None."""
    starts, i = [], 0
    while i < len(text):
        two = text[i:i + 2]
        if two == "{{":
            starts.append(i)
            i += 2
            continue
        if two == "}}" and starts:
            return starts[-1], i + 2
        i += 1
    return None


def clean_value(raw):
    """(status, text). status: ok, unresolved (text is the template to expand), empty, unsupported."""
    if len(raw) > MAX_RAW_VALUE_CHARS:
        return "unsupported", ""
    value = COMMENT.sub("", raw)
    if "<!--" in value:
        return "unsupported", ""
    value = REF_SELF.sub(" ", REF_PAIR.sub(" ", value))
    if re.search(r"<\s*/?\s*ref\b", value, re.IGNORECASE):
        return "unsupported", ""
    value = EMPTY_SPAN.sub("", SMALL.sub("", BREAK.sub(" ; ", value))).strip()
    if "{|" in value or "{{{" in value:
        return "unsupported", ""
    if value.startswith("{{") and value.endswith("}}"):
        parts = _split_top(value[2:-2])
        whole = parts is not None and _innermost_template(value) is not None and _matching_close(value) == len(value)
        if whole:
            name = parts[0].strip().casefold()
            if name.startswith("#"):
                return "unsupported", ""  # Parser functions are never expanded.
            if name not in LIST_TEMPLATES:
                return "unresolved", value
    while "{{" in value:
        span = _innermost_template(value)
        if span is None:
            return "unsupported", ""
        start, end = span
        inner = value[start + 2:end - 2]
        if inner.split("|", 1)[0].strip().casefold() not in LIST_TEMPLATES:
            return "unsupported", ""
        items = _list_items(inner)
        if items is None:
            return "unsupported", ""
        value = value[:start] + " ; ".join(items) + value[end:]
    value = value.replace("\n", " ; ")  # A line break inside a value separates entries.
    if FILE_LINK.search(value):
        return "unsupported", ""
    value = LINK.sub(lambda m: m.group(2) if m.group(2) is not None else m.group(1), value)
    value = EXTERNAL.sub(lambda m: m.group(1), value)
    if BARE_EXTERNAL.search(value):
        return "unsupported", ""
    value = html.unescape(value.replace("'''", "").replace("''", ""))
    if any(mark in value for mark in LEFTOVER):
        return "unsupported", ""
    items = [" ".join(item.split()) for item in value.split(";")]
    text = " ; ".join(item for item in items if item)
    if not text:
        return "empty", ""
    if len(text) > MAX_VALUE_CHARS:
        return "unsupported", ""
    return "ok", text


def _matching_close(text):
    """Index just after the '}}' closing the template that opens at text[0], or None."""
    depth, i = 0, 0
    while i < len(text):
        two = text[i:i + 2]
        if two == "{{":
            depth, i = depth + 1, i + 2
            continue
        if two == "}}":
            depth, i = depth - 1, i + 2
            if depth == 0:
                return i
            continue
        i += 1
    return None


def infobox_fields(wikitext):
    """{field: (status, text)} for whitelisted fields; a field named twice is 'ambiguous'."""
    params = infobox_params(wikitext)
    if params is None:
        return {}
    out = {}
    for name in FIELDS:
        values = params.get(name)
        if values is None:
            continue
        out[name] = ("ambiguous", "") if len(values) > 1 else clean_value(values[0])
    return out


def field_label(name):
    return name.replace("_", " ").capitalize()


# ---- Selection ---------------------------------------------------------------------------------
def _roles(item):
    return {light_stem(t) for part in re.findall(r"\(([^()]*)\)", item) for t in words(part)}


def field_candidates(pages, subjects):
    """Qualified fields, best first, at most one per field name (chosen before any value is resolved).

    A field qualifies when every subject term is covered by the article title, the field name or,
    for key_people, the role in parentheses of a kept item. Ranking: title precision (share of
    title terms that are subject terms) descending, then provider rank, then field order."""
    subject_set, ranked = set(subjects), []
    for page in pages:
        title_terms = {light_stem(t) for t in words(page["title"]) if t not in STOPWORDS}
        for order, (name, (status, text)) in enumerate(infobox_fields(page["wikitext"]).items()):
            if status not in ("ok", "unresolved"):
                continue
            covered = title_terms | stems(name.replace("_", " "))
            if name == "key_people":
                if status != "ok":
                    continue  # Roles must be visible to qualify.
                kept = [item for item in text.split(" ; ") if _roles(item) & subject_set]
                if not kept:
                    continue
                text = " ; ".join(kept)
                covered |= set().union(*(_roles(item) for item in kept))
            if Fraction(len(subject_set & covered), len(subject_set)) != 1:
                continue
            precision = Fraction(len(subject_set & title_terms), len(title_terms)) if title_terms else Fraction(0)
            ranked.append(((-precision, page["rank"], order), dict(
                kind="field", title=page["title"], url=page["url"], rank=page["rank"], field=name,
                label=field_label(name), status=status, value=text if status == "ok" else "",
                template=text if status == "unresolved" else None)))
    ranked.sort(key=lambda item: item[0])
    best = {}
    for _, unit in ranked:  # Ranked order is kept: dicts preserve insertion order.
        best.setdefault(unit["field"], unit)
    return list(best.values())


def sentence_candidates(pages, subjects, coverage):
    """Qualified sentences, best first: a current-state phrase in the sentence and subject coverage
    (sentence plus title) at least `coverage`. Ranking: coverage, then subject hits in the sentence,
    then provider rank, then position."""
    subject_set, ranked, seen = set(subjects), [], set()
    for page in pages:
        title_terms = stems(page["title"])
        for index, sentence in enumerate(split_sentences(page["extract"])):
            key = " ".join(sentence.casefold().split())
            if key in seen:
                continue
            seen.add(key)
            if not eligible(sentence):
                continue
            tokens = words(sentence)
            if not any(has_phrase(tokens, p) for p in PREDICATES):
                continue
            sentence_terms = {light_stem(t) for t in tokens}
            cov = Fraction(len(subject_set & (sentence_terms | title_terms)), len(subject_set))
            if cov < coverage:
                continue
            own = len(subject_set & sentence_terms)
            ranked.append(((-cov, -own, page["rank"], index), dict(
                kind="sentence", title=page["title"], url=page["url"], rank=page["rank"], coverage=cov,
                sentence=sentence)))
    ranked.sort(key=lambda item: item[0])
    return [unit for _, unit in ranked]


def _near_duplicate(a, b):
    a, b = " ".join(words(a)), " ".join(words(b))
    return a in b or b in a


def unit_text(unit):
    return f"{unit['label']}: {unit['value']}" if unit["kind"] == "field" else unit["sentence"]


def reference_select(pages, query, message, *, sentence_coverage=DEFAULTS["sentence_coverage"],
                     order=DEFAULTS["order"], expand=None):
    """The H2 reference. pages: parse_h2() output. expand(title, template) -> wikitext or None, or
    None to disable H2-X. Returns (units, expansions_requested)."""
    subjects = subject_terms(query, message)
    if not subjects:
        return [], 0
    fields, requested = [], 0
    for unit in field_candidates(pages, subjects):
        if unit["status"] == "unresolved":
            if expand is None or requested >= MAX_EXPANSIONS:
                continue
            requested += 1
            expanded = expand(unit["title"], unit["template"])
            status, text = clean_value(expanded) if isinstance(expanded, str) else ("unsupported", "")
            if status != "ok":
                continue
            unit = dict(unit, status="ok", value=text, expanded=True)
        else:
            unit = dict(unit, expanded=False)
        unit.pop("template", None)
        fields.append(unit)
    sentences = sentence_candidates(pages, subjects, sentence_coverage)
    if order == "fields_first":
        candidates = fields + sentences
    else:
        merged = [((-Fraction(1), f["rank"], 0, i), f) for i, f in enumerate(fields)]
        merged += [((-s["coverage"], s["rank"], 1, i), s) for i, s in enumerate(sentences)]
        candidates = [unit for _, unit in sorted(merged, key=lambda item: item[0])]
    chosen, per_article, total = [], {}, 0
    for unit in candidates:
        if len(chosen) == MAX_UNITS:
            break
        text = unit_text(unit)
        if per_article.get(unit["url"], 0) == MAX_PER_ARTICLE or total + len(text) > MAX_CHARS:
            continue  # Never truncated: the next candidate is tried.
        if unit["kind"] == "sentence" and any(c["kind"] == "sentence" and _near_duplicate(c["sentence"], unit["sentence"])
                                              for c in chosen):
            continue
        chosen.append(unit)
        per_article[unit["url"]] = per_article.get(unit["url"], 0) + 1
        total += len(text)
    return [_public(u) for u in chosen], requested


def _public(unit):
    if unit["kind"] == "field":
        return dict(kind="field", title=unit["title"], url=unit["url"], field=unit["field"], label=unit["label"],
                    value=unit["value"], expanded=unit["expanded"])
    return dict(kind="sentence", title=unit["title"], url=unit["url"], sentence=unit["sentence"])


def unit_key(unit):
    if unit["kind"] == "field":
        return ("field", unit["title"], unit["field"], unit["value"])
    return ("sentence", unit["title"], unit["sentence"])


# ---- Records and replay ------------------------------------------------------------------------
def load(name):
    return [json.loads(line) for line in (ROOT/name).read_text(encoding="utf-8").splitlines() if line.strip()]


def record(split, case_id):
    return json.loads((ROOT/split/(case_id + ".json")).read_text(encoding="utf-8"))


def replay_expand(rec):
    """expand() backed by the captured expansions; refuses anything not captured or over the limit."""
    table = {(e["title"], e["template"]): e for e in rec.get("expansions", [])}

    def expand(title, template):
        entry = table.get((title, template))
        if entry is None or entry.get("status") != 200 or entry.get("bytes", 0) > MAX_EXPANSION_BODY_BYTES:
            return None
        return parse_expansion(entry.get("body"))
    return expand


def select_record(rec, *, expansion=True, **values):
    pages = parse_h2(rec["h2"].get("body") if rec["h2"].get("status") == 200 else None)
    return reference_select(pages, rec["query"] or "", rec["message"],
                            expand=replay_expand(rec) if expansion else None, **values)


# ---- Holdout composition -----------------------------------------------------------------------
def holdout_ids(labels):
    """All 36 main questions, plus reserves in declared order (a1, b1, a2, b2, ...) one at a time
    until at least MIN_AVAILABLE_HOLDOUT questions have an available answer in either capture.
    Nothing is ever removed or replaced."""
    by_id = {l["id"]: l for l in labels if l["split"] == "holdout"}
    main = [i for i, l in by_id.items() if l["role"] == "main"]
    reserves = sorted((l for l in by_id.values() if l["role"] == "reserve"), key=lambda l: (l["order"], l["author"]))
    chosen = list(main)
    available = lambda ids: sum(by_id[i]["answer_present_h1"] or by_id[i]["answer_present_h2"] for i in ids)
    for reserve in reserves:
        if available(chosen) >= MIN_AVAILABLE_HOLDOUT:
            break
        chosen.append(reserve["id"])
    return chosen


def duplicate_groups(records):
    """Questions whose v1-minimized queries are identical (diagnostic only; declared before capture)."""
    groups = {}
    for rec in records:
        if rec.get("query"):
            groups.setdefault(rec["query"], []).append(rec["id"])
    return [sorted(ids) for ids in groups.values() if len(ids) > 1]


def deduplicated(ids, records):
    """ids with each duplicate group counted once (its first id). Reported beside, never instead of, the gates."""
    drop = {i for group in duplicate_groups(records) for i in group[1:]}
    return [i for i in ids if i not in drop]


# ---- Metrics -----------------------------------------------------------------------------------
def availability(labels, ids):
    """Retrieval coverage, separate from selection: is an answer in the candidate material?"""
    rows = []
    for label in (l for l in labels if l["id"] in ids):
        gold = label["gold_h2"]
        rows.append(dict(id=label["id"], h1=label["answer_present_h1"], h2=label["answer_present_h2"],
                         h2_sentence=any(g["kind"] == "sentence" for g in gold),
                         h2_field=any(g["kind"] == "field" and not g["expanded"] for g in gold),
                         h2_expansion_only=bool(gold) and all(g["kind"] == "field" and g["expanded"] for g in gold)))
    return dict(cases=len(rows), h1=sum(r["h1"] for r in rows), h2=sum(r["h2"] for r in rows),
                gained=sum(r["h2"] and not r["h1"] for r in rows), lost=sum(r["h1"] and not r["h2"] for r in rows),
                h2_by_sentence=sum(r["h2_sentence"] for r in rows), h2_by_field=sum(r["h2_field"] for r in rows),
                h2_expansion_only=sum(r["h2_expansion_only"] for r in rows), rows=rows)


def evaluate_selection(select_fn, labels, ids):
    """select_fn(label) -> (units, expansions_requested); scored against the H2 labels."""
    rows = []
    for label in (l for l in labels if l["id"] in ids):
        units, requested = select_fn(label)
        supplied = {unit_key(u) for u in units}
        gold = {unit_key(g) for g in label["gold_h2"]}
        per = {}
        for u in units:
            per[u["url"]] = per.get(u["url"], 0) + 1
        found = supplied & gold
        rows.append(dict(id=label["id"], available=label["answer_present_h2"], found=bool(found),
            found_via=sorted({k[0] for k in found}), abstained=not units,
            caps_ok=len(units) <= MAX_UNITS and max(per.values(), default=0) <= MAX_PER_ARTICLE
                    and sum(len(unit_text(u)) for u in units) <= MAX_CHARS,
            attributed=all(attributed(label, u) for u in units),
            distractors=len(supplied & {unit_key(d) for d in label["distractors_h2"]}),
            chars=sum(len(unit_text(u)) for u in units), expansions=requested, supplied=units))
    available = [r for r in rows if r["available"]]
    absent = [r for r in rows if not r["available"]]
    return dict(cases=len(rows), available=len(available),
                answer_recall=sum(r["found"] for r in available) / len(available) if available else None,
                abstention=sum(r["abstained"] for r in absent) / len(absent) if absent else None,
                false_supply=sum(not r["abstained"] for r in absent),
                caps=sum(r["caps_ok"] for r in rows) / len(rows) if rows else None,
                attribution=sum(r["attributed"] for r in rows) / len(rows) if rows else None,
                distractors_supplied=sum(r["distractors"] for r in rows),
                max_chars=max((r["chars"] for r in rows), default=0),
                expansion_requests=sum(r["expansions"] for r in rows), rows=rows)


def attributed(label, unit):
    """A supplied unit must come, verbatim, from the article it names in that case's capture."""
    rec = record(label["split"], label["id"])
    pages = {p["title"]: p for p in parse_h2(rec["h2"].get("body") if rec["h2"].get("status") == 200 else None)}
    page = pages.get(unit["title"])
    if page is None or page["url"] != unit["url"]:
        return False
    if unit["kind"] == "sentence":
        return unit["sentence"] in split_sentences(page["extract"])
    status, text = infobox_fields(page["wikitext"]).get(unit["field"], ("missing", ""))
    if unit["expanded"]:
        expanded = replay_expand(rec)(unit["title"], text) if status == "unresolved" else None
        return isinstance(expanded, str) and clean_value(expanded) == ("ok", unit["value"])
    if unit["field"] == "key_people":
        return status == "ok" and all(item in text.split(" ; ") for item in unit["value"].split(" ; "))
    return (status, text) == ("ok", unit["value"])


def gain_attribution(labels, ids, selection):
    """Per case: did H2-R make the answer available, and did H2-F/S then select it?"""
    by_id = {r["id"]: r for r in selection["rows"]}
    out = []
    for label in (l for l in labels if l["id"] in ids):
        gold = label["gold_h2"]
        source = ("none" if not gold else "sentence" if any(g["kind"] == "sentence" for g in gold)
                  else "field" if any(not g["expanded"] for g in gold) else "expansion")
        out.append(dict(id=label["id"], available_h1=label["answer_present_h1"], available_h2=label["answer_present_h2"],
                        available_via=source, selected=by_id[label["id"]]["found"],
                        selected_via=by_id[label["id"]]["found_via"]))
    return out


def choose_on_development(score_fn):
    """score_fn(values) -> evaluate_selection summary on development. Predeclared tie-break:
    recall + abstention, then fewer distractors, then fewer characters supplied in total, then the
    higher sentence coverage, then fields_first."""
    best = None
    for coverage in GRID["sentence_coverage"]:
        for order in GRID["order"]:
            values = dict(sentence_coverage=coverage, order=order)
            s = score_fn(values)
            key = ((s["answer_recall"] or 0) + (s["abstention"] or 0), -s["distractors_supplied"],
                   -sum(r["chars"] for r in s["rows"]), coverage, order == "fields_first")
            if best is None or key > best[0]:
                best = (key, values, s)
    return best[1], best[2]


def selection_gates(summary, selection_p95_ms):
    return dict(answer_recall=summary["answer_recall"] is not None and summary["answer_recall"] >= GATES["answer_recall_min"],
                abstention=summary["abstention"] is not None and summary["abstention"] >= GATES["abstention_min"],
                caps=summary["caps"] == 1.0, attribution=summary["attribution"] == 1.0,
                selection_time=selection_p95_ms <= GATES["selection_p95_ms"])


def network_gates(records):
    """From the live capture: requests per turn (H2-R plus at most one expansion) and time."""
    worst = []
    for rec in records:
        h2 = rec["h2"]
        slowest_expansion = max((e["seconds"] for e in rec.get("expansions", []) if e.get("seconds") is not None), default=0)
        worst.append(h2["seconds"] + slowest_expansion)
    return dict(requests_per_turn=1 + MAX_EXPANSIONS <= GATES["requests_per_turn_max"],
                network_seconds=max(worst, default=0) <= GATES["network_seconds_max"], max_seconds=max(worst, default=0))


def token_gates(tokens):
    """tokens: real-tokenizer evidence counts for C3 turns that supplied evidence (e2e)."""
    return dict(median=statistics.median(tokens) <= GATES["tokens_median_max"] if tokens else True,
                max=max(tokens) <= GATES["tokens_max"] if tokens else True)


def expansion_ships(with_x, without_x, with_gates, without_gates):
    """Predeclared H2-X rule: ships only if H2 with X passes every gate, X adds at least one found
    holdout answer that the same configuration without X misses, and X introduces no false supply."""
    adds = any(a["found"] and not b["found"] for a, b in zip(with_x["rows"], without_x["rows"]))
    no_new_false = with_x["false_supply"] <= without_x["false_supply"]
    return all(with_gates.values()) and adds and no_new_false


def reach_adopted(*args, **kwargs):
    """The original Reach rule, unchanged (tests/reach/evaluate.py), applied to C3 versus B."""
    import sys
    sys.path.insert(0, str(ROOT.parent))
    from reach.evaluate import reach_adopted as original
    return original(*args, **kwargs)
