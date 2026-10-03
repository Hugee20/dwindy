"""Evaluation-only information-result/supply-receipt concept.

Not an application API, production pipeline, semantic classifier or verifier.
Callers provide acquisition/admission observations. This module only checks known
identities, text, operational state and the actual supplied packet.
"""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Entry:
    source_id: str
    entry_id: str
    text: str
    title: str
    origin: str = 'DOCUMENT'
    similarity: float | None = None

    def __post_init__(self):
        if any(not isinstance(v,str) or not v for v in (self.source_id,self.entry_id,self.text,self.title)):
            raise ValueError('Nonempty identity/text required')
        if self.origin not in ('PROJECT','DOCUMENT','HOST','TOOL','WEB'):
            raise ValueError('Unknown origin; origin is not truth or priority')
        if self.similarity is not None and (not math.isfinite(self.similarity) or not -1<=self.similarity<=1):
            raise ValueError('Cosine must be finite; never public confidence')


@dataclass(frozen=True)
class InformationResult:
    state: str
    candidates: tuple[Entry, ...] = ()
    admitted_ids: tuple[str, ...] = ()
    error: str | None = None

    def __post_init__(self):
        if self.state not in ('found','no_match','unavailable','not_used'):
            raise ValueError('Unknown acquisition state')
        ids = [e.entry_id for e in self.candidates]
        if len(ids)>12 or len(ids)!=len(set(ids)):
            raise ValueError('Candidate bounds/identity violated')
        if len(self.admitted_ids)!=len(set(self.admitted_ids)) or not set(self.admitted_ids)<=set(ids):
            raise ValueError('Admission must reference candidate identities')
        if self.state!='found' and (self.candidates or self.admitted_ids):
            raise ValueError('Failed/bypassed/empty acquisition cannot admit')
        if self.state=='found' and not ids:
            raise ValueError('Found requires candidates')
        if (self.state=='unavailable') != bool(self.error):
            raise ValueError('Operational errors cannot be reported as no relevance match')


@dataclass(frozen=True)
class SupplyReceipt:
    state: str
    supplied: tuple[Entry, ...]
    dropped_turns: int = 0

    def __post_init__(self):
        if self.state not in ('supplied','budget_exhausted','no_match','not_used','unavailable'):
            raise ValueError('Unknown supply state')
        if len(self.supplied)>3 or len({e.entry_id for e in self.supplied})!=len(self.supplied):
            raise ValueError('Supplied packet bounds/identity violated')
        if (self.state=='supplied') != bool(self.supplied):
            raise ValueError('State must describe actual supply, not acquisition')
        if type(self.dropped_turns) is not int or self.dropped_turns<0:
            raise ValueError('Invalid trimming observation')

    def public(self):
        # Proposed source-level presentation is deliberately separate from the
        # exact internal entry receipt. No claim about the model's interpretation.
        sources, seen = [], set()
        for entry in self.supplied:
            if entry.source_id not in seen:
                sources.append(dict(source_id=entry.source_id,title=entry.title,origin=entry.origin))
                seen.add(entry.source_id)
        return dict(state=self.state,sources=sources)


def validate_receipt(result, receipt):
    admitted = tuple(e for e in result.candidates if e.entry_id in result.admitted_ids)
    supplied_ids = {e.entry_id for e in receipt.supplied}
    if receipt.supplied!=tuple(e for e in admitted if e.entry_id in supplied_ids):
        raise ValueError('Actual supply must preserve admitted identity, exact text and order')
    if receipt.state=='budget_exhausted' and not admitted:
        raise ValueError('Budget exhaustion requires admitted information')
    if result.state in ('not_used','unavailable','no_match') and receipt.state!=result.state:
        raise ValueError('Operational/acquisition state changed')
    if result.state=='found' and not admitted and receipt.state!='no_match':
        raise ValueError('Found but rejected is distinct from unavailable or supply')
    if result.state=='found' and admitted and receipt.state not in ('supplied','budget_exhausted'):
        raise ValueError('Admitted but unsupplied must record budget exhaustion')
    return True


def record_runtime_capability():
    # Known Dwindy runtime fact; not host capability discovery or action intent.
    return dict(owner='DWINDY',host_action_executor_available=False)


def embedding_view(body, heading='', name='', *, model):
    """Deterministic encoder input only; original supplied text is never replaced.

    Tokenization/truncation is a future authorized runner's job, with encoded span
    audits. No encoder/model is imported or downloaded here.
    """
    value = '\n'.join(v for v in (name,heading,body) if v)
    return ('passage: ' if model=='e5' else '')+value
