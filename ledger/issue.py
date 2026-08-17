"""The delta issue as a written document.

The first digest rendered field transitions straight onto the page:

    Death toll                    at least 7 (new)
    White River at Indianapolis   Crested early Sun, receding (new)

That is the backend as the frontend — the same mistake this project already made
with the state diff, made again because "pure projection, no model" sounded like
a virtue. It is a virtue for the API and a defect for a reader. So the
transitions are the BRIEF, and the issue is written from them.

The form follows the Sleuthsletter, which does this well:

  standfirst    what window this covers, and a link to the issue it follows
  top           the two or three developments that matter, each a bold lede
                sentence followed by real prose
  beat          per-beat sections, dense with dates and figures
  thread        what is only visible ACROSS beats — the same fight worked from
                three angles, a name recurring in two unrelated dockets
  correction    the record corrected, as a named part of the issue rather than
                a quiet edit

Because it is written, it goes through the SAME entailment gate as an article,
which is what `paragraphs` and `as_dict()` exist for. That matters most for the
thread blocks: "the same fight from three angles" is a claim about the world,
and cross-beat synthesis is exactly where an unsupported inference would enter.
Nothing about being a digest exempts a sentence from being supported.

No model here — this module validates. The writing belongs to the agent.
"""
from __future__ import annotations
from dataclasses import dataclass, field

# A digest is longer than a single story and shorter than a magazine piece. The
# real Sleuthsletter issues run about 2,000-2,500 words across a dozen subjects.
MIN_WORDS, MAX_WORDS = 400, 2600

KINDS = ("top", "beat", "thread", "correction")


class IssueError(ValueError):
    """The issue is not publishable as written."""


@dataclass(frozen=True)
class Issue:
    day: str
    standfirst: str
    blocks: tuple
    written_by: str
    previous: str | None = None
    quiet: int = 0
    lapsed: tuple = ()
    verified_by: tuple = ()
    published_at: str = ""
    word_count: int = 0

    @property
    def paragraphs(self) -> list:
        """The issue as checkable units, for ledger/entail.py.

        Lede and body are joined so the gate sees the lede sentence too. The
        lede carries the strongest claim in the block; excluding it would leave
        the most consequential sentence in the issue unverified.
        """
        out = []
        for b in self.blocks:
            text = " ".join(x for x in (b.get("lede"), b.get("text")) if x).strip()
            out.append({"text": text, "claims": list(b.get("claims") or [])})
        return out

    def as_dict(self) -> dict:
        return {
            "day": self.day, "previous": self.previous,
            "standfirst": self.standfirst,
            "blocks": [dict(b) for b in self.blocks],
            "quiet": self.quiet, "lapsed": [dict(t) for t in self.lapsed],
            "written_by": self.written_by,
            "verified_by": list(self.verified_by),
            "published_at": self.published_at, "word_count": self.word_count,
        }


def validate(obj) -> Issue:
    """Turn a candidate issue into an Issue, or refuse it with a reason."""
    if isinstance(obj, Issue):
        obj = obj.as_dict()
    if not isinstance(obj, dict):
        raise IssueError(f"issue is {type(obj).__name__}, not an object")

    day = str(obj.get("day") or "")
    if len(day) != 10:
        raise IssueError(f"day {day!r} is not an ISO date")

    standfirst = " ".join(str(obj.get("standfirst") or "").split())
    if not standfirst:
        raise IssueError("no standfirst: an issue must say what window it covers")

    raw = list(obj.get("blocks") or [])
    if not raw:
        raise IssueError("no blocks: there is no issue here")

    blocks, words = [], 0
    for i, b in enumerate(raw):
        kind = str((b or {}).get("kind") or "top")
        if kind not in KINDS:
            raise IssueError(f"block {i}: unknown kind {kind!r}")
        lede = " ".join(str(b.get("lede") or "").split())
        text = " ".join(str(b.get("text") or "").split())
        if not (lede or text):
            raise IssueError(f"block {i} is empty")
        claims = [str(c) for c in (b.get("claims") or []) if str(c).strip()]
        if not claims:
            # Same rule as an article paragraph: uncited prose cannot be checked,
            # and unchecked prose is the one thing this system will not publish.
            raise IssueError(f"block {i} cites no claims")
        heading = " ".join(str(b.get("heading") or "").split()) or None
        if kind == "beat" and not heading:
            raise IssueError(f"block {i}: a beat section needs a heading naming "
                             "the beat, or the reader cannot check it")
        blocks.append({"kind": kind, "heading": heading, "lede": lede,
                       "text": text, "claims": claims,
                       "beat": (b.get("beat") or None)})
        words += len((lede + " " + text).split())

    if words < MIN_WORDS:
        raise IssueError(f"{words} words: below {MIN_WORDS} there was no issue "
                         "worth sending")
    if words > MAX_WORDS:
        raise IssueError(f"{words} words: above {MAX_WORDS} the writer is padding")

    prev = obj.get("previous")
    return Issue(
        day=day, standfirst=standfirst, blocks=tuple(blocks),
        written_by=str(obj.get("written_by") or ""),
        previous=(str(prev) if prev else None),
        quiet=int(obj.get("quiet") or 0),
        lapsed=tuple(dict(t) for t in (obj.get("lapsed") or ())),
        verified_by=tuple(str(v) for v in (obj.get("verified_by") or ())),
        published_at=str(obj.get("published_at") or ""),
        word_count=words,
    )


def cleared(iss: Issue, verifier_names) -> Issue:
    """The same issue, with the verifiers that cleared it on the record."""
    d = iss.as_dict()
    d["verified_by"] = [str(n) for n in (verifier_names or ())]
    return validate(d)
