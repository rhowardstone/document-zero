"""The delta issue as a written document, not a table.

The first version of the digest rendered field transitions directly:

    Death toll                    at least 7 (new)
    White River at Indianapolis   Crested early Sun, receding (new)

That is the backend as the frontend — the same mistake this project already made
once with the state diff, repeated because "pure projection, no model" sounded
like a virtue. It is a virtue for the API and a defect for a reader. Prose needs
a writer, so the transitions are the BRIEF and the issue is written from them.

The form is taken from the Sleuthsletter, which does this well: a standfirst
naming what window the issue covers and linking the previous one, top
developments as a bold lede sentence followed by real prose, per-beat sections,
and a "connecting the threads" section for what only shows up across beats.

Because it is written, it goes through the same entailment gate as an article —
which is why Issue exposes `paragraphs` and `as_dict()`. Cross-beat synthesis is
exactly where an unsupported inference would creep in ("the same fight from three
angles" is a claim about the world), so it must be checkable sentence by
sentence like everything else.
"""
import pytest

from ledger.issue import MAX_WORDS, MIN_WORDS, IssueError, validate


def block(kind="top", lede="Blanche refused to pledge independence.",
          text=None, claims=("c1",), heading=None, words=170):
    return {"kind": kind, "lede": lede,
            "text": text if text is not None else "word " * words,
            "claims": list(claims), "heading": heading}


def issue(blocks=None, **kw):
    d = {"day": "2026-08-17", "previous": "2026-08-13",
         "standfirst": "Covering the record since the 13 August issue.",
         "blocks": blocks if blocks is not None else
                   [block(), block(kind="beat", heading="Indiana flooding"),
                    block(kind="thread")],
         "quiet": 2, "lapsed": [], "written_by": "digest-1"}
    d.update(kw)
    return d


# ── Shape ───────────────────────────────────────────────────────────────────

def test_a_well_formed_issue_validates():
    iss = validate(issue(blocks=[block(words=220), block(kind="thread", words=220)]))
    assert iss.day == "2026-08-17" and len(iss.blocks) == 2


def test_the_issue_names_the_window_it_covers():
    """"Since the last issue" is the whole premise. An issue that cannot say
    which issue it follows is not a delta, it is a snapshot."""
    assert validate(issue()).previous == "2026-08-13"


def test_the_first_ever_issue_may_have_no_predecessor():
    assert validate(issue(previous=None)).previous is None


def test_an_issue_with_no_blocks_is_refused():
    with pytest.raises(IssueError, match="no blocks"):
        validate(issue(blocks=[]))


def test_a_block_that_cites_nothing_is_refused():
    """Same rule as an article paragraph. Uncited prose cannot be checked."""
    with pytest.raises(IssueError, match="cites no claims"):
        validate(issue(blocks=[block(claims=(), words=450)]))


def test_a_block_with_no_text_is_refused():
    with pytest.raises(IssueError, match="empty"):
        validate(issue(blocks=[block(text="", lede="")]))


def test_a_beat_block_must_name_its_beat():
    """A per-beat section with no beat cannot be linked to the record it
    describes, so the reader cannot check it."""
    with pytest.raises(IssueError, match="heading"):
        validate(issue(blocks=[block(kind="beat", heading=None, words=450)]))


def test_a_missing_standfirst_is_refused():
    with pytest.raises(IssueError, match="standfirst"):
        validate(issue(standfirst=""))


# ── Length ──────────────────────────────────────────────────────────────────

def test_a_digest_far_under_the_floor_is_refused():
    """Below the floor there was no issue worth sending."""
    with pytest.raises(IssueError, match="below"):
        validate(issue(blocks=[block(text="short text here", lede="Lede.")]))


def test_a_digest_over_the_ceiling_is_refused():
    with pytest.raises(IssueError, match="padding|above"):
        validate(issue(blocks=[block(text="word " * (MAX_WORDS + 50))]))


def test_the_word_count_is_recorded():
    iss = validate(issue())
    assert iss.word_count >= MIN_WORDS


# ── Gate compatibility ──────────────────────────────────────────────────────

def test_the_issue_presents_paragraphs_for_the_entailment_gate():
    """Issue goes through the SAME gate as an article. Nothing about it being a
    digest exempts a sentence from being supported."""
    iss = validate(issue(blocks=[block(claims=("c1", "c2"), words=450)]))
    p = iss.paragraphs
    assert isinstance(p, list) and p[0]["claims"] == ["c1", "c2"]


def test_the_lede_sentence_is_checked_too():
    """The bold lede carries the strongest claim in the block. Excluding it from
    the gate would leave the most consequential sentence unverified."""
    iss = validate(issue(blocks=[block(lede="Blanche refused to pledge independence.",
                                       words=450)]))
    assert "Blanche refused to pledge independence." in iss.paragraphs[0]["text"]


def test_the_issue_round_trips_through_a_dict():
    iss = validate(issue())
    again = validate(iss.as_dict())
    assert again.as_dict() == iss.as_dict()


def test_verifiers_can_be_recorded_on_the_issue():
    from ledger.issue import cleared
    iss = cleared(validate(issue()), ["entail-1", "entail-2"])
    assert iss.verified_by == ("entail-1", "entail-2")
    assert iss.blocks == validate(issue()).blocks
