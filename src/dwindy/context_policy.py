"""Per-turn local-context selection: attempt liberally, supply conservatively.

No model calls, no I/O except the caller-supplied search function. The policy decides only
whether local evidence deserves model context. Lexical overlap is never treated as proof
that a passage answers the question; answerability stays with the model's instructions.
"""
from dataclasses import dataclass
import re

from .evidence import Evidence
from .retrieval import RetrievalError, STOPWORDS, query_terms, words

MODES = ("off", "on", "auto")
MAX_QUERY_BYTES = 2048

# The complete fast-path cue table (frozen cap: 60 entries, tests/context/README.md).
# Cues express only high-certainty fast paths; ambiguous requests fall through to retrieval.
# Never add a cue to repair a single evaluation case.
CUES = {
    "pleasantry": ("hello", "hi", "hey", "thanks", "thank", "good morning", "good afternoon",
                   "good evening", "bye", "goodbye", "ok", "okay"),
    "history": ("previous answer", "previous message", "you said", "i told you", "just tell you",
                "our conversation", "we talked about", "we discussed"),
    "creative_verb": ("write", "compose", "tell", "make up"),
    "creative_noun": ("poem", "haiku", "story", "joke", "song", "limerick"),
    "transform": ("translate", "summarize", "summarise", "rewrite", "rephrase", "paraphrase",
                  "proofread", "fix the grammar", "correct the grammar"),
    "system_determiner": ("this", "your"),
    "system_noun": ("system", "app", "application", "project", "program", "software", "codebase", "repo"),
    "documentation": ("the documentation", "the docs", "project documents", "project documentation",
                      "project files", "readme"),
    "shape": (r"\b[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]*[A-Za-z0-9]\b",       # snake_case / SCREAMING_CASE
              r"\b[a-z]{2,}[A-Z][a-z]+[A-Za-z0-9]*\b",                    # camelCase
              # Source-like path: dir/file.ext, or a bare file name with a non-.js source extension
              # (bare .js is too often a framework name, e.g. node.js).
              r"\b[\w.-]+(?:/[\w.-]+)+\.[A-Za-z0-9]+\b|\b\w[\w-]*\.(?:py|jsx|ts|tsx|md|txt|toml|json)\b"),
}
SHAPES = tuple(re.compile(pattern) for pattern in CUES["shape"])
GENERATED = frozenset({"project_structure", "project_metadata"})
# Evidence is worth supplying when one ordinary passage among the top three contains at
# least this fraction of the query's search terms. Tuned on the development split only.
MIN_COVERAGE = 0.5
TOP_PASSAGES = 3
# Set by the frozen real-model adoption rule (tests/context/rubric.md), not by configuration.
# When False, project-directed retrieval failures raise and the API returns the M6 503.
CONSTRAINED_FALLBACK = True


@dataclass(frozen=True)
class ContextDecision:
    mode: str
    attempted: bool
    reason: str
    query_normalized: bool = False

    def metadata(self, core_retrieval):
        """Response metadata: unchanged M6 object for on, None for off, auto object otherwise."""
        if self.mode == "on":
            return core_retrieval
        if self.mode == "off":
            return None
        status = (core_retrieval or {}).get("status") or (
            "unavailable" if self.reason in ("retrieval_unavailable", "retrieval_busy") else "not_used")
        reason = self.reason
        if status == "not_used" and reason == "relevant_match":
            reason = "budget_exhausted"  # Gated passages existed but none fit the allowance.
        result = dict(mode="auto", attempted=self.attempted, status=status, reason=reason,
                      sources=(core_retrieval or {}).get("sources", []))
        if self.query_normalized:
            result["query_normalized"] = True
        return result


def _has(sequence, phrase):
    target = phrase.split()
    return any(sequence[i:i+len(target)] == target for i in range(len(sequence)-len(target)+1))


def _without(sequence, phrases):
    remaining = list(sequence)
    for phrase in sorted(phrases, key=len, reverse=True):
        target = phrase.split()
        i = 0
        while i <= len(remaining)-len(target):
            if remaining[i:i+len(target)] == target:
                del remaining[i:i+len(target)]
            else:
                i += 1
    return remaining


def _system_phrases(message):
    tokens = words(message)
    return [f"{a} {b}" for a in CUES["system_determiner"] for b in CUES["system_noun"] if _has(tokens, f"{a} {b}")]


def classify(message, project_name=None):
    """Fast-path shape of a message: 'directed', 'conversational', 'history', 'self_contained' or None."""
    tokens = words(message)
    name = words(project_name) if project_name else []
    if ((name and _has(tokens, " ".join(name))) or _system_phrases(message)
            or any(_has(tokens, cue) for cue in CUES["documentation"])
            or any(shape.search(message) for shape in SHAPES)):
        return "directed"
    if any(_has(tokens, cue) for cue in CUES["pleasantry"]):
        if not [t for t in _without(tokens, CUES["pleasantry"]) if t not in STOPWORDS]:
            return "conversational"
    if any(_has(tokens, cue) for cue in CUES["history"]):
        return "history"
    if any(_has(tokens, v) for v in CUES["creative_verb"]) and any(_has(tokens, n) for n in CUES["creative_noun"]):
        return "self_contained"
    # Transformation only when the user supplies the material after a colon or line break.
    split = re.search(r"[:\n]", message)
    if split and len(words(message[split.end():])) >= 3 and any(
            _has(words(message[:split.start()]), cue) for cue in CUES["transform"]):
        return "self_contained"
    return None


def normalized_query(message, project_name):
    """Search-query-only normalization: 'this system' etc. becomes the project name."""
    if not project_name:
        return message, False
    query, changed = message, False
    for phrase in _system_phrases(message):
        pattern = r"\b" + r"\s+".join(map(re.escape, phrase.split())) + r"\b"
        query, count = re.subn(pattern, project_name, query, flags=re.IGNORECASE)
        changed = changed or bool(count)
    return query, changed


def useful(passages, terms):
    """Whether evidence deserves context. Overlap is not answerability."""
    if not terms:
        return False
    wanted = set(terms)
    for passage in passages[:TOP_PASSAGES]:
        if passage.source.source_type in GENERATED:
            continue
        present = set(words(passage.text)) | set(words(passage.source.heading)) | set(words(passage.source.source_path))
        if len(wanted & present) / len(wanted) >= MIN_COVERAGE:
            return True
    return False


def decide(message, mode, *, search=None, project_name=None, max_tokens=768):
    """Return (ContextDecision, Evidence | None). search(query, limit) may raise RetrievalError.

    off: never retrieve. on: M6 semantics, errors propagate. auto: the policy below.
    """
    if mode not in MODES:
        raise ValueError("Retrieval mode must be off, on or auto.")
    if mode == "off":
        return ContextDecision("off", False, "off"), None
    if mode == "on":
        if search is None:
            raise RetrievalError("retrieval_disabled")
        return ContextDecision("on", True, "explicit"), Evidence(search(message, 12), max_tokens)
    if search is None:
        return ContextDecision("auto", False, "no_index"), None
    if len(message.encode("utf-8")) > MAX_QUERY_BYTES:
        return ContextDecision("auto", False, "message_too_long"), None
    try:
        shape = classify(message, project_name)
        query, normalized = normalized_query(message, project_name) if shape == "directed" else (message, False)
        terms = query_terms(query)
    except Exception:
        return ContextDecision("auto", False, "policy_error"), None
    reasons = dict(conversational="conversational", history="history_reference", self_contained="self_contained_task")
    if shape in reasons:
        return ContextDecision("auto", False, reasons[shape]), None
    if not terms and shape != "directed":
        return ContextDecision("auto", False, "no_terms"), None
    try:
        passages = tuple(search(query, 12)) if terms else ()
    except RetrievalError as exc:
        if shape == "directed":
            if not CONSTRAINED_FALLBACK:
                raise
            return ContextDecision("auto", True, exc.code, normalized), Evidence((), max_tokens, "unavailable")
        return ContextDecision("auto", True, exc.code), None
    if shape == "directed":
        # Explicitly about the project: supply what exists, or let M6 guidance say it is missing.
        return ContextDecision("auto", True, "project_directed", normalized), Evidence(passages, max_tokens)
    try:
        worth = useful(passages, terms)
    except Exception:
        return ContextDecision("auto", True, "policy_error"), None
    if not worth:
        return ContextDecision("auto", True, "weak_match" if passages else "no_candidates"), None
    return ContextDecision("auto", True, "relevant_match"), Evidence(passages, max_tokens, "plain")


def cue_count():
    return sum(len(entries) for entries in CUES.values())
