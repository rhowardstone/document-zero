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
    """One bad SENTENCE kills the whole piece. Editing that sentence and
    re-checking would produce an article optimised against the check."""
    def fails_one(s, _c):
        return Verdict(False, "unsupported") if "inevitable" in s else Verdict(True, "ok")

    r = check(article("The Fed held rates. A cut is now inevitable."),
              CLAIMS, verifiers=[fails_one, fails_one])
    assert r.passed is False
    assert any("inevitable" in x.sentence for x in r.refusals)


def test_a_lone_objection_does_not_refuse():
    """Per-sentence false refusals COMPOUND. At 3% across 29 sentences only 41%
    of correct articles survive a single-verifier veto, and the measured rate
    was worse. A veto that silences most correct work does not make the system
    safe, it makes it quiet."""
    r = check(article("The Fed held rates."), CLAIMS, verifiers=[yes, no])
    assert r.passed is True
    assert r.dissents, "the outvoted objection is still recorded"


def test_agreement_refuses():
    assert check(article("The Fed held rates."), CLAIMS,
                 verifiers=[no, no]).passed is False


def test_a_dissent_is_recorded_so_drift_is_visible():
    r = check(article("The Fed held rates."), CLAIMS, verifiers=[no, yes])
    assert r.passed is True and len(r.dissents) == 1
    assert r.dissents[0].reason


def test_a_verifier_that_errors_does_not_silently_become_a_pass():
    """An error is not a vote. It means the sentence was never checked, and a
    sentence that could not be checked is refused — which is different from
    being outvoted."""
    def boom(_s, _c):
        raise RuntimeError("timeout")

    r = check(article("The Fed held rates."), CLAIMS, verifiers=[boom, yes])
    assert r.passed is False
    assert "unverified" in r.refusals[0].reason


def test_both_verifiers_erroring_refuses():
    def boom(_s, _c):
        raise RuntimeError("down")
    assert check(article("The Fed held rates."), CLAIMS,
                 verifiers=[boom, boom]).passed is False


def test_a_single_verifier_setup_still_refuses_on_its_own_verdict():
    """With one verifier the majority IS one, so it retains its veto."""
    assert check(article("x happened."), CLAIMS, verifiers=[no]).passed is False
    assert check(article("x happened."), CLAIMS, verifiers=[yes]).passed is True


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


# ── Concurrency ─────────────────────────────────────────────────────────────

def test_checks_run_concurrently():
    """34 sentences x 2 verifiers took 964s sequentially on the first live run."""
    import threading, time
    peak, live, lock = [0], [0], threading.Lock()

    def slow(_s, _c):
        with lock:
            live[0] += 1
            peak[0] = max(peak[0], live[0])
        time.sleep(0.05)
        with lock:
            live[0] -= 1
        return Verdict(True, "ok")

    a = article("One thing. Two things. Three things. Four things. Five things.")
    check(a, CLAIMS, verifiers=[slow, slow], workers=8)
    assert peak[0] > 1, "verification must not be serialised"


def test_results_are_deterministic_despite_concurrency():
    """The same article must always produce the same report, whatever order the
    checks happen to finish in."""
    import random, time

    def jittery(s, _c):
        time.sleep(random.random() * 0.01)
        return Verdict("Three" not in s, "no")

    a = article("One thing. Two things. Three things. Four things.")
    runs = [check(a, CLAIMS, verifiers=[jittery], workers=8) for _ in range(4)]
    assert all(r.passed is False for r in runs)
    assert len({tuple(x.sentence for x in r.refusals) for r in runs}) == 1


def test_the_checked_count_is_sentences_not_calls():
    seen = []
    def spy(s, _c):
        seen.append(s); return Verdict(True, "ok")
    a = article("One thing. Two things. Three things.")
    r = check(a, CLAIMS, verifiers=[spy, spy], workers=4)
    assert r.checked * 2 == len(seen)


def test_workers_of_one_still_works():
    a = article("One thing happened.")
    assert check(a, CLAIMS, verifiers=[yes], workers=1).passed is True


# ── Deleting an unsupported sentence is not rewriting it ────────────────────

# These need REAL sentences, because deletion works sentence by sentence. The
# helper above pads with unpunctuated filler, which one refusal would swallow
# whole — an artefact of the fixture rather than of the code.
PAD = " ".join(f"Supported fact number {i} was reported by the department today."
               for i in range(60))


def padded(text, claims=("c1", "c2")):
    return validate({
        "beat": "fed", "day": "2026-08-16",
        "headline": "Fed holds rates as September nears",
        "standfirst": "Two governors dissent", "dateline": "WASHINGTON",
        "published_at": "2026-08-16T14:02:00Z", "written_by": "t",
        "paragraphs": [{"text": f"{text} {PAD}", "claims": list(claims)}]})

def test_refused_sentences_can_be_deleted_and_the_rest_survives():
    """Deletion introduces no new text, so it cannot introduce anything
    unsupported. Every surviving sentence is one the verifiers already passed."""
    from ledger.entail import without
    a = padded("The Fed held rates. A cut is now inevitable.")
    r = check(a, CLAIMS, verifiers=[
        lambda s, c: Verdict("inevitable" not in s, "x"),
        lambda s, c: Verdict("inevitable" not in s, "x")])
    assert r.passed is False
    trimmed = without(a, r.refusals)
    assert "inevitable" not in " ".join(p["text"] for p in trimmed.paragraphs)
    assert "The Fed held rates." in trimmed.paragraphs[0]["text"]


def test_a_trimmed_article_still_faces_the_schema():
    """An article that falls under the floor once its unsupported sentences are
    gone had less to say than it appeared to."""
    from ledger.article import ArticleError
    from ledger.entail import without
    a = article("Everything here is unsupported.", claims=("c1",))
    r = check(a, CLAIMS, verifiers=[lambda s, c: Verdict(False, "no"),
                                    lambda s, c: Verdict(False, "no")])
    with pytest.raises(ArticleError):
        without(a, r.refusals)


def test_deletion_never_introduces_text():
    from ledger.entail import without
    a = padded("One thing happened. Two things happened. Three things happened.")
    r = check(a, CLAIMS, verifiers=[lambda s, c: Verdict("Two" not in s, "x"),
                                    lambda s, c: Verdict("Two" not in s, "x")])
    before = set(sentences(a.paragraphs[0]["text"]))
    after = set(sentences(without(a, r.refusals).paragraphs[0]["text"]))
    assert after < before, "deletion may only remove"
