"""Refusal gates.

There is no human editor, so high-risk categories are not queued for review.
They are refused outright at extraction time. The protection is not generating
the exposure.

The principle underneath is asymmetric scrutiny: automated attention pointed up
at institutions with press offices is accountability; pointed down at private
individuals it is surveillance at scale.

Every gate defaults to REFUSAL under uncertainty.
"""
from __future__ import annotations
from dataclasses import dataclass
import re

# Statuses that make a person a legitimate subject of automated scrutiny.
PUBLIC_STATUSES = frozenset({"public_official", "public_figure", "named_party"})

WRONGDOING = (
    r"accus\w+", r"alleg\w+", r"defraud\w*", r"fraud", r"embezzl\w+", r"bribe\w*",
    r"corrupt\w*", r"assault\w*", r"abus\w+", r"harass\w+", r"stole", r"stolen",
    r"theft", r"launder\w+", r"illegal\w*", r"unlawful\w*", r"criminal\w*",
    r"convict\w+", r"indict\w+", r"charged with", r"perjur\w+", r"conspir\w+",
    r"violat\w+", r"misconduct", r"wrongdoing", r"kill\w*", r"murder\w*",
    r"stalk\w+", r"withheld", r"concealed", r"lied",
)
# Conduct that is criminal on its face, needing a filing rather than a report.
CRIMINAL = (
    r"fraud", r"embezzl\w+", r"bribe\w*", r"assault\w*", r"launder\w+",
    r"murder\w*", r"conspir\w+", r"perjur\w+", r"theft", r"stole", r"stolen",
    r"indict\w+", r"convict\w+", r"charged with",
)
IDENTIFIERS = (
    r"\blives? at\b", r"\bresides? at\b", r"\bhome address\b",
    r"\bplate (?:number|no\.?)\b", r"\b[A-Z0-9]{6,8}\b(?=\s*(?:plate|tag))",
    r"\d{1,5}\s+[A-Z][a-z]+\s+(?:Street|St\.?|Avenue|Ave\.?|Road|Rd\.?|Lane|Ln\.?|Drive|Dr\.?)\b",
    r"\bemployed (?:at|by)\b", r"\bworks at\b",
)
# A charging document, docket or official filing corroborates criminal conduct.
FILING_TYPES = frozenset({"documentation", "article", "techreport"})


@dataclass(frozen=True)
class Subject:
    name: str
    status: str = "unknown"

    @property
    def is_public(self) -> bool:
        return self.status in PUBLIC_STATUSES


@dataclass(frozen=True)
class Decision:
    allowed: bool
    gate: str | None = None
    reason: str = ""


def _any(patterns, text: str) -> bool:
    low = text.lower()
    return any(re.search(p, low) for p in patterns)


def asserts_wrongdoing(text: str) -> bool:
    return _any(WRONGDOING, text)


def asserts_criminal_conduct(text: str) -> bool:
    return _any(CRIMINAL, text)


def identifies_person(text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in IDENTIFIERS)


def refusal_check(claim: dict, subjects) -> Decision:
    """Return the first gate that fires, or an allow decision.

    Order matters: person gates run before corroboration, because a refusal to
    speak about a private individual is absolute and not curable by sourcing.
    """
    text = claim.get("claim_text", "") or ""
    non_public = [s for s in subjects if not s.is_public]

    if non_public and asserts_wrongdoing(text):
        who = ", ".join(s.name for s in non_public)
        return Decision(False, "wrongdoing_by_private_individual",
                        f"asserts wrongdoing about a person of non-public status: {who}")

    if non_public and identifies_person(text):
        who = ", ".join(s.name for s in non_public)
        return Decision(False, "identification_of_private_individual",
                        f"identifies a person of non-public status: {who}")

    if asserts_criminal_conduct(text):
        corroborated = (claim.get("source_type") in FILING_TYPES) or bool(claim.get("docket"))
        if not corroborated:
            return Decision(False, "uncorroborated_criminal_conduct",
                            "asserts criminal conduct with no charging document, docket "
                            "or official filing in the provenance")

    return Decision(True)
