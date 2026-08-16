"""The entailment gate: prose may not assert what its claims do not support.

Three properties are enforced rather than prompted, and each has a test here:

  - Verifiers see the sentence and the CITED CLAIMS ONLY.
  - One unentailed sentence refuses the WHOLE article, not the sentence.
  - A verifier that errors or is unsure counts as a refusal.
"""
import pytest

from ledger.article import validate
from ledger.entail import Refused, Verdict, check, sentences

CLAIMS = [
    {"id": "c1", "claim_text": "The Federal Reserve held rates unchanged in August 2026."},
    {"id": "c2", "claim_text": "Two governors dissented from the August decision."},
]


def article(text, claims=("c1", "c2")):
    return validate({
        "beat": "fed", "day": "2026-08-16",
        "headline": "Fed holds rates as September nears",
        "standfirst": "Two governors dissent", "dateline": "WASHINGTON",
        "published_at": "2026-08-16T14:02:00Z", "written_by": "t",
        "paragraphs": [{"text": text + " filler" * 400, "claims": list(claims)}]})


def yes(_s, _c):
    return Verdict(True, "supported")


def no(_s, _c):
    return Verdict(False, "nothing supports this")


def test_sentences_are_split_for_checking():
    s = sentences("The Fed held rates. Two governors dissented! Did they? Yes.")
    assert len(s) == 4


def test_an_article_every_sentence_of_which_is_entailed_passes():
    r = check(article("The Fed held rates."), CLAIMS, verifiers=[yes, yes])
    assert r.passed is True and r.refusals == []


def test_one_unentailed_sentence_refuses_the_whole_article():
    """Refusing the article rather than editing the sentence is deliberate: an
    article patched to survive a check is an article optimised against it."""
    def first_fails(s, _c):
        return Verdict(False, "unsupported") if "inevitable" in s else Verdict(True, "ok")

    r = check(article("The Fed held rates. A cut is now inevitable."),
              CLAIMS, verifiers=[first_fails, yes])
    assert r.passed is False
    assert any("inevitable" in x.sentence for x in r.refusals)


def test_either_verifier_can_refuse():
    """Consensus is not required to refuse. One is enough, in either position."""
    assert check(article("The Fed held rates."), CLAIMS,
                 verifiers=[yes, no]).passed is False
    assert check(article("The Fed held rates."), CLAIMS,
                 verifiers=[no, yes]).passed is False


def test_a_verifier_that_errors_counts_as_refusal():
    """Uncertainty resolves to not-entailed."""
    def boom(_s, _c):
        raise RuntimeError("timeout")

    r = check(article("The Fed held rates."), CLAIMS, verifiers=[boom, yes])
    assert r.passed is False
    assert "RuntimeError" in r.refusals[0].reason


def test_verifiers_receive_only_the_sentence_and_the_cited_claims():
    """Asymmetry of information is the point: a verifier shown the writer's
    justification adopts it, and one shown uncited sources will reach for them."""
    seen = []

    def spy(s, c):
        seen.append((s, c))
        return Verdict(True, "ok")

    a = article("The Fed held rates.")
    check(a, CLAIMS + [{"id": "c9", "claim_text": "unrelated"}], verifiers=[spy, yes])
    assert seen
    for _sentence, claims in seen:
        assert {c["id"] for c in claims} == {"c1", "c2"}, "uncited claims leaked in"


def test_refused_articles_raise_when_asked_to_publish():
    r = check(article("The Fed held rates."), CLAIMS, verifiers=[no, no])
    with pytest.raises(Refused):
        r.require_pass()


def test_a_passing_result_publishes_without_raising():
    check(article("The Fed held rates."), CLAIMS, verifiers=[yes]).require_pass()


def test_every_sentence_is_checked_not_just_the_first():
    seen = []

    def spy(s, _c):
        seen.append(s)
        return Verdict(True, "ok")

    check(article("One thing happened. Two things happened. Three things happened."),
          CLAIMS, verifiers=[spy])
    assert len(seen) >= 3


def test_a_claim_cited_but_absent_from_the_ledger_is_simply_not_passed_on():
    """A dangling citation must not crash the gate; the verifier sees less
    evidence, which can only make it refuse."""
    a = article("The Fed held rates.", claims=("c1", "does-not-exist"))
    seen = []

    def spy(_s, c):
        seen.append({x["id"] for x in c})
        return Verdict(True, "ok")

    check(a, CLAIMS, verifiers=[spy])
    assert seen and all(ids == {"c1"} for ids in seen)
