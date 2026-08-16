"""Abbreviation-aware sentence splitting.

This exists because a naive split cost a real article on its first live run. The
gate was handed these as complete sentences:

    "…sued the Justice Department and Acting Attorney General Todd Blanche
     in the U.S."
    "The case is docketed as No. 1:26-cv-02762-AHA, is assigned to Judge Amir H."

and refused both, correctly: a fragment asserts something incomplete, and no
claim entails "sued … in the U.S." as a finished thought. The verifiers were
right. The splitter was wrong, and it refused a publishable article.

The vocabulary this project works in is exactly the vocabulary that breaks naive
splitters — U.S., D.C., No. 1:26-cv-02762, Judge Amir H. Ali, 28 C.F.R. § 16.21,
Pub. L. No. 119-38. Getting this wrong does not produce a subtle degradation; it
produces confident refusals of correct work.

The same class of bug was already fixed once in ledger/subjects.py, where a
period after "Rep." split a title away from the name it belonged to. That lesson
is centralised here so it is fixed in one place.
"""
from __future__ import annotations
import re

# A period after one of these is an abbreviation, not a sentence end.
ABBREV = frozenset("""
mr mrs ms dr prof rev hon sen rep gov gen adm col lt capt sgt att atty
jr sr st ave rd blvd dept univ assn bros inc corp co ltd llc llp plc
no nos vs v et al etc eg ie cf ca approx est fig figs ch chs sec secs
art arts para paras pp vol vols ed eds trans repr supp cir dist
pub stat cong reg regs cl amend ct cts cert dkt ecf exh ex aff decl
mem op rev ann tit subpt subch nn fn ibid id seq
jan feb mar apr jun jul aug sep sept oct nov dec
mon tue tues wed thu thurs fri sat sun
""".split())

# Sentence-ending punctuation followed by space and something that could start a
# sentence. Candidates only — _is_boundary decides.
_CANDIDATE = re.compile(r"([.!?]+)([\"'”’\)\]]*)(\s+)(?=[A-Z\"'“‘\(\[])")

# "U.S.", "D.C.", "N.M." — the WHOLE token must be a dotted acronym. Using a
# search for one letter-plus-dot matched the trailing "s." of "rates.", so every
# ordinary sentence looked like an abbreviation and nothing split at all.
_DOTTED = re.compile(r"^(?:[A-Za-z]\.){2,}$")
_INITIAL = re.compile(r"^[A-Z]$")


def _last_token(text: str) -> str:
    m = re.search(r"([\w.'’-]+)$", text)
    return m.group(1) if m else ""


def _is_boundary(before: str) -> bool:
    """Is the period at the end of `before` a real sentence end?"""
    tok = _last_token(before)
    if not tok:
        return True

    # "U.S." / "D.C." / "F.3d." — a dotted acronym is not a sentence end.
    if _DOTTED.match(tok):
        return False

    bare = tok.rstrip(".").lower()

    # A lone capital is a middle initial: "Amir H. Ali".
    if _INITIAL.match(tok.rstrip(".")):
        return False

    if bare in ABBREV:
        return False

    # NOT a rule: "a number before the period is not a boundary". That was here
    # to protect "No. 1:26-cv-02762", but "No." is already an abbreviation, and
    # the rule blocked every sentence ending in a year — "…in 2019. Prosecutors
    # then…" — which is ubiquitous in this material.
    return True


def split(text: str) -> list[str]:
    """Split prose into sentences, respecting abbreviations."""
    s = (text or "").strip()
    if not s:
        return []

    out, start = [], 0
    for m in _CANDIDATE.finditer(s):
        end = m.end(2)                      # after punctuation and any quote
        if not _is_boundary(s[:m.end(1)]):
            continue
        chunk = s[start:end].strip()
        if chunk:
            out.append(chunk)
        start = m.end(3)
    tail = s[start:].strip()
    if tail:
        out.append(tail)
    return out
