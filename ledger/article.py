"""The Article: what a reporter produces and a reader reads.

v1's central artifact was a diff of state fields:

    Records sought   was  Unredacted Epstein investigative files
                     now  Unredacted 'Epstein Library' records, EFTA §2(a)(1)-(9)

That is a database row. It is how the system should think; it is not what a
person reads. This object is the replacement. The state delta still decides
WHAT is worth writing about — it is carried here as `changed`, shown under the
story as the reporting behind it — but the article is what publishes.

The bounds below are editorial judgements encoded as validation rather than
left to a prompt:

  - Under 400 words there was no story, and the beat should degrade to a
    one-line entry that needs no prose to support it.
  - Over 800 the reporter is padding, which in an automated newsroom means
    generating sentences that have to be checked and cannot be supported.
  - A paragraph citing no claims is prose the ledger cannot trace to evidence.
    That is the failure this entire project exists to prevent, appearing one
    level up from where v1 prevented it.

An Article is frozen. It is a published record, and editing one in place would
make the ledger's history a lie — the same reason claims are immutable.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field

MIN_WORDS, MAX_WORDS = 400, 800
MIN_HEADLINE_WORDS = 4
# A headline is not the lede. Told only "a sentence, not a fragment", the
# reporter wrote a 20-word restatement of its own first paragraph, which
# rendered as six lines of display type and made the page look broken.
MAX_HEADLINE_WORDS = 14
REQUIRED = ("beat", "day", "headline", "standfirst", "dateline",
            "published_at", "written_by")


class ArticleError(ValueError):
    """An article does not satisfy the schema and may not publish."""


@dataclass(frozen=True)
class Article:
    beat: str
    day: str
    headline: str
    standfirst: str
    dateline: str
    published_at: str
    paragraphs: tuple = ()
    changed: tuple = ()
    written_by: str = ""
    verified_by: tuple = ()
    word_count: int = 0
    cited: frozenset = field(default_factory=frozenset)

    def as_dict(self) -> dict:
        return {
            "beat": self.beat, "day": self.day, "headline": self.headline,
            "standfirst": self.standfirst, "dateline": self.dateline,
            "published_at": self.published_at,
            "paragraphs": [dict(p) for p in self.paragraphs],
            "changed": [dict(c) for c in self.changed],
            "written_by": self.written_by,
            "verified_by": list(self.verified_by),
            "word_count": self.word_count,
        }


def word_count(text: str) -> int:
    return len([w for w in re.split(r"\s+", (text or "").strip()) if w])


def validate(obj: dict) -> Article:
    """Return a frozen Article, or raise ArticleError saying why it cannot publish."""
    for f in REQUIRED:
        if not str(obj.get(f) or "").strip():
            raise ArticleError(f"missing required field: {f}")

    hw = len(str(obj["headline"]).split())
    if hw < MIN_HEADLINE_WORDS:
        raise ArticleError("headline must be a sentence, not a fragment: "
                           f"{obj['headline']!r}")
    if hw > MAX_HEADLINE_WORDS:
        raise ArticleError(
            f"headline is {hw} words: over {MAX_HEADLINE_WORDS} it is a lede, "
            "not a headline")

    paras = obj.get("paragraphs") or []
    if not paras:
        raise ArticleError("an article needs at least one paragraph")

    cited: set = set()
    total = 0
    for i, p in enumerate(paras):
        claims = p.get("claims") or []
        if not claims:
            raise ArticleError(
                f"paragraph {i} cites no claims; prose the ledger cannot trace "
                "to evidence may not publish")
        cited.update(claims)
        total += word_count(p.get("text"))

    if total < MIN_WORDS:
        raise ArticleError(
            f"{total} words: below {MIN_WORDS} there was no story, and the beat "
            "should degrade to a one-line entry")
    if total > MAX_WORDS:
        raise ArticleError(
            f"{total} words: above {MAX_WORDS} the reporter is padding")

    return Article(
        beat=str(obj["beat"]), day=str(obj["day"]),
        headline=str(obj["headline"]), standfirst=str(obj["standfirst"]),
        dateline=str(obj["dateline"]), published_at=str(obj["published_at"]),
        paragraphs=tuple(dict(p) for p in paras),
        changed=tuple(dict(c) for c in (obj.get("changed") or ())),
        written_by=str(obj["written_by"]),
        verified_by=tuple(obj.get("verified_by") or ()),
        word_count=total, cited=frozenset(cited))
