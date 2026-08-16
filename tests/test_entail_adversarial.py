"""The four shapes the gate must distinguish.

A gate that only ever sees well-formed input is untested, and this gate is the
only thing standing between the ledger and a machine that writes confident
fiction under a real domain name.

The verifier here is a deterministic stand-in for what a careful reader does: a
sentence is entailed only if its content words are covered by the cited claims.
It is crude, and that is the point — it makes the four cases mechanical and the
test free.
"""
import pytest

from ledger.article import validate
from ledger.entail import Verdict, check

CLAIMS = [{"id": "c1",
           "claim_text": "The Justice Department declined to search the property in 2019."}]


def strict(sentence, claims):
    """Entailed only if every content word appears in some cited claim."""
    blob = " ".join(c["claim_text"].lower() for c in claims)
    words = [w.strip(".,;:'\"") for w in sentence.lower().split()]
    missing = [w for w in words if len(w) > 4 and w not in blob]
    return Verdict(not missing, f"unsupported: {missing[:3]}" if missing else "ok")


def art(text):
    return validate({
        "beat": "nm-records", "day": "2026-08-16",
        "headline": "Department declined to search the property",
        "standfirst": "s", "dateline": "SANTA FE",
        "published_at": "2026-08-16T00:00:00Z", "written_by": "t",
        "paragraphs": [{"text": text + " property" * 420, "claims": ["c1"]}]})


def test_1_a_supported_sentence_passes():
    a = art("The Justice Department declined to search the property in 2019.")
    assert check(a, CLAIMS, verifiers=[strict]).passed is True


def test_2_a_sentence_supported_by_nothing_is_refused():
    a = art("The Justice Department declined to search the property in 2019. "
            "Investigators later recovered remains at the location.")
    r = check(a, CLAIMS, verifiers=[strict])
    assert r.passed is False
    assert any("recovered" in x.sentence for x in r.refusals)


def test_3_a_sentence_that_overstates_its_claim_is_refused():
    """The claim says 'declined'. The article says 'deliberately concealed'.

    This is the failure mode fluent prose makes easy and a field/value pair
    makes impossible, and it is the reason this gate exists at all.
    """
    a = art("The Justice Department deliberately concealed evidence in 2019.")
    r = check(a, CLAIMS, verifiers=[strict])
    assert r.passed is False


def test_4_a_true_but_uncited_sentence_is_still_refused():
    """Being true is not the standard. Being supported by the CITED claims is.

    A newsroom that publishes true-but-unsupported sentences has no way to tell
    the difference between the ones that happen to be true and the ones that do
    not, because it never checked either.
    """
    a = art("The Justice Department declined to search the property in 2019. "
            "Washington remains the capital of the United States.")
    assert check(a, CLAIMS, verifiers=[strict]).passed is False


def test_the_refusal_names_the_offending_sentence_not_just_a_count():
    """An operator reading the log has to be able to see what was wrong."""
    a = art("The Justice Department declined to search the property in 2019. "
            "Prosecutors ignored repeated warnings.")
    r = check(a, CLAIMS, verifiers=[strict])
    assert r.refusals[0].sentence.startswith("Prosecutors")
    assert "unsupported" in r.refusals[0].reason
