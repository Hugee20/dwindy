"""Deterministic capabilities: small exact facts computed per turn. No model, I/O or eval.

A capability produces a fact for the turn's single model call; it never answers on its own,
calls a host or loops. Facts are computed while each turn is processed, so a long-running
process never reuses a stale clock reading.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, DivisionByZero, InvalidOperation, localcontext
import re

from .retrieval import words

# The complete capability cue table (frozen cap: 30 entries, tests/tools/README.md). It is a
# small closed grammar for explicit requests, not a natural-language arithmetic parser.
CUES = {
    "calculation_lead": ("what is", "what's", "whats", "calculate", "compute", "evaluate",
                         "how much is", "solve"),
    "word_operator": ("plus", "minus", "times", "multiplied by", "divided by", "of"),
    "clock": ("today", "tonight", "tomorrow", "yesterday", "what day is it", "what time is it",
              "what year is it", "the date", "current date", "current time", "date today", "right now"),
}
BOUNDS = dict(max_expression_chars=200, max_number_digits=30, max_nesting=10,
              max_abs_exponent=100, max_result_digits=100, precision_digits=28)
# Set by the frozen real-model adoption rule (tests/tools/rubric.md), not by configuration.
CALCULATOR_ADOPTED = True

NUMBER = re.compile(r"\d+(?:\.\d+)?")
LEADS = re.compile(r"(?<!\w)(?:" + "|".join(
    re.escape(cue).replace(r"\ ", r"\s+").replace("'", "['’]") for cue in CUES["calculation_lead"]) + r")(?!\w)",
    re.IGNORECASE)
WORD_OPERATORS = {"plus": "+", "minus": "-", "times": "*", "multiplied by": "*", "divided by": "/"}
SYMBOLS = {"×": "*", "÷": "/", "−": "-"}


@dataclass(frozen=True)
class Fact:
    name: str
    text: str
    metadata: dict


@dataclass(frozen=True)
class Calculation:
    outcome: str            # result | undefined | rejected | none
    expression: str = ""
    value: str | None = None


class _Reject(Exception):
    """Recognized arithmetic beyond the frozen bounds."""


class _NotArithmetic(Exception):
    pass


def _tokens(span):
    """Tokenize one candidate span completely, or fail: no partial span is ever computed."""
    text, out, i = span, [], 0
    while i < len(text):
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        number = NUMBER.match(text, i)
        if number:
            raw, end = number.group(), number.end()
            if (len(raw) > 1 and raw[0] == "0" and raw[1] != ".") or (i and (text[i-1].isalpha() or text[i-1] in "_$")):
                raise _NotArithmetic  # Leading zeros (dates, codes), or attached to a word or currency.
            if end < len(text) and (text[end].isalpha() or text[end] in "_:"):
                raise _NotArithmetic  # 1e308, 16:9, 10:30, 4B…
            out.append(("num", raw))
            i = end
            continue
        if text.startswith("**", i):
            out.append(("op", "^")); i += 2
            continue
        if ch in "+-*/^%()" or ch in SYMBOLS:
            # An unspaced hyphen between digits is a date, range, phone number or score.
            if ch == "-" and i and text[i-1].isdigit() and i+1 < len(text) and text[i+1].isdigit():
                raise _NotArithmetic
            out.append(("op", SYMBOLS.get(ch, ch))); i += 1
            continue
        word = re.match(r"[A-Za-z]+(?:\s+by\b)?", text[i:])
        phrase = " ".join(word.group().lower().split()) if word else ""
        if phrase in WORD_OPERATORS:
            out.append(("op", WORD_OPERATORS[phrase])); i += len(word.group())
            continue
        if phrase == "of" and out and out[-1] == ("op", "%"):
            out.append(("op", "*")); i += 2
            continue
        raise _NotArithmetic
    if re.search(r"\d/\d+/\d", span):
        raise _NotArithmetic  # A chained unspaced slash (10/15/2026) is a date.
    return out


class _Parser:
    """Builds a syntax tree for the whole span; nothing is evaluated here.
    expr := term (+|- term)*; term := unary (*|/ unary)*; unary := - unary | power;
    power := postfix (^ unary)?; postfix := primary %?; primary := number | ( expr )."""

    def __init__(self, tokens):
        self.tokens, self.i, self.depth, self.max_depth, self.operators = tokens, 0, 0, 0, 0

    def peek(self):
        return self.tokens[self.i] if self.i < len(self.tokens) else (None, None)

    def take(self, value):
        if self.peek() == ("op", value):
            self.i += 1
            return True
        return False

    def parse(self):
        tree = self.expr()
        if self.i != len(self.tokens) or not self.operators:
            raise _NotArithmetic
        return tree

    def binary(self, operators, operand):
        tree = operand()
        while self.peek()[0] == "op" and self.peek()[1] in operators:
            op = self.tokens[self.i][1]; self.i += 1; self.operators += 1
            tree = (op, tree, operand())
        return tree

    def expr(self):
        return self.binary(("+", "-"), self.term)

    def term(self):
        return self.binary(("*", "/"), self.unary)

    def unary(self):
        return ("neg", self.unary()) if self.take("-") else self.power()

    def power(self):
        base = self.postfix()
        if self.take("^"):
            self.operators += 1
            return ("^", base, self.unary())  # Right-associative: 9^9^9 is 9^(9^9).
        return base

    def postfix(self):
        tree = self.primary()
        if self.take("%"):
            self.operators += 1
            tree = ("%", tree)
        return tree

    def primary(self):
        kind, value = self.peek()
        if kind == "num":
            self.i += 1
            return ("num", value)
        if self.take("("):
            self.depth += 1
            self.max_depth = max(self.max_depth, self.depth)
            inner = self.expr()
            if not self.take(")"):
                raise _NotArithmetic
            self.depth -= 1
            return inner
        raise _NotArithmetic


def _value(tree):
    kind = tree[0]
    if kind == "num":
        return Decimal(tree[1])
    if kind == "neg":
        return -_value(tree[1])
    if kind == "%":
        return _value(tree[1]) / 100
    left, right = _value(tree[1]), _value(tree[2])
    if kind == "+": return left + right
    if kind == "-": return left - right
    if kind == "*": return left * right
    if kind == "/":
        if right == 0:
            raise DivisionByZero
        return left / right
    if right != right.to_integral_value() or abs(right) > BOUNDS["max_abs_exponent"]:
        raise _Reject
    if left == 0 and right <= 0:
        raise InvalidOperation  # 0^0 and 0^-n are undefined.
    if left != 0 and (abs(left).adjusted() + 1) * abs(int(right)) > BOUNDS["max_result_digits"] + 1:
        raise _Reject
    return left ** int(right)


def _format(value):
    if value != 0 and value.adjusted() >= BOUNDS["max_result_digits"]:
        raise _Reject
    text = format(value.normalize(), "f")
    return "0" if text in ("-0", "0") else text


def _evaluate(span):
    """Calculation for a complete span, or None when the span is not explicit arithmetic."""
    span = span.strip().rstrip("=").strip()
    if not span:
        return None
    try:
        tokens = _tokens(span)
        parser = _Parser(tokens)
        tree = parser.parse()
    except (_NotArithmetic, IndexError):
        return None
    if (len(span) > BOUNDS["max_expression_chars"] or parser.max_depth > BOUNDS["max_nesting"]
            or any(kind == "num" and sum(c.isdigit() for c in raw) > BOUNDS["max_number_digits"] for kind, raw in tokens)):
        return Calculation("rejected", span)
    with localcontext() as context:
        context.prec = BOUNDS["precision_digits"]
        context.traps[DivisionByZero] = context.traps[InvalidOperation] = True
        try:
            return Calculation("result", span, _format(_value(tree)))
        except (DivisionByZero, InvalidOperation):
            return Calculation("undefined", span)
        except (_Reject, OverflowError):
            return Calculation("rejected", span)


def _candidates(message):
    """Explicit requests only: a bare expression, or the text after a calculation lead."""
    stripped = message.strip()
    yield re.sub(r"[?!.]+$", "", stripped)
    for lead in LEADS.finditer(message):
        yield re.split(r"[?!,;\n]|\.(?!\d)", message[lead.end():], maxsplit=1)[0]


def calculate(message):
    for candidate in _candidates(message):
        found = _evaluate(candidate)
        if found is not None:
            return found
    return Calculation("none")


def _phrase_in(tokens, phrase):
    target = words(phrase)
    return any(tokens[i:i+len(target)] == target for i in range(len(tokens) - len(target) + 1))


def clock_applies(message):
    tokens = words(message)
    return any(_phrase_in(tokens, cue) for cue in CUES["clock"])


def self_contained(message):
    """User-supplied material for transformation or creative work is never computed on."""
    from .context_policy import classify
    return classify(message) == "self_contained"


def detect(message):
    """Model-independent view used by the frozen evaluation (calculator detected even if not adopted)."""
    if self_contained(message):
        return Calculation("none"), False
    return calculate(message), clock_applies(message)


def select(message, now=None):
    """Facts for this turn. now is read here, per turn, unless a test supplies it."""
    calculation, clock = detect(message)
    facts = []
    if clock:
        moment = (now or datetime.now()).astimezone()
        offset = moment.strftime("%z")
        text = (f"Server-local date and time: {moment:%A, %Y-%m-%d %H:%M} "
                f"(UTC{offset[:3]}:{offset[3:]}). This is the server's clock, not necessarily the user's time zone.")
        facts.append(Fact("clock", text, dict(name="clock", value=moment.isoformat(timespec="minutes"))))
    if CALCULATOR_ADOPTED and calculation.outcome in ("result", "undefined"):
        # ASCII operators keep the fact readable after the evidence framing's JSON quoting.
        shown = "".join(SYMBOLS.get(ch, ch) for ch in calculation.expression)
        text = (f"{shown} = {calculation.value}" if calculation.outcome == "result"
                else f"{shown} is mathematically undefined.")
        facts.append(Fact("calculator", text, dict(name="calculator", input=calculation.expression,
                                                     result=calculation.value if calculation.value is not None else "undefined")))
    return tuple(facts)


def cue_count():
    return sum(len(entries) for entries in CUES.values())
