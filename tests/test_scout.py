"""Beats come from the news, not from a file.

The beat test is retained verbatim from the v1 spec §2.1 because it was
correct. What is new is that something actually runs it, on clusters the wire
produced, instead of a human typing 22 beats into YAML and wondering why 20 of
them stayed empty.
"""
import pytest

from ledger.paths import owned_prefixes, owns_path
from ledger.scout import (Proposal, beat_test, propose_from_cluster,
                          should_close, slug_for)


def prop(events=4, span_days=6, fields=("Status", "Next hearing"), trigger=None):
    return Proposal(name="Fifth Circuit v. NLRB", slug="fifth-circuit-v-nlrb",
                    events=events, span_days=span_days,
                    state_fields=list(fields), dated_trigger=trigger,
                    publishers={"apnews.com", "reuters.com"})


# ── The beat test ────────────────────────────────────────────────────────────

def test_three_events_over_five_days_with_two_fields_opens():
    ok, why = beat_test(prop())
    assert ok is True, why


def test_too_few_events_is_rejected():
    ok, why = beat_test(prop(events=2))
    assert ok is False and "event" in why


def test_a_single_days_flurry_is_an_event_not_a_beat():
    ok, why = beat_test(prop(span_days=2))
    assert ok is False and "day" in why


def test_one_dated_trigger_substitutes_for_the_event_threshold():
    """A scheduled hearing is a beat on day one: the sequence is guaranteed."""
    ok, why = beat_test(prop(events=1, span_days=0, trigger="2026-09-05"))
    assert ok is True, why


def test_fewer_than_two_changeable_fields_is_rejected_even_with_a_trigger():
    """This is the whole beat test. No changeable state, no beat — it is what
    stops a match result or a product launch becoming a tracked story."""
    ok, why = beat_test(prop(fields=("Status",), trigger="2026-09-05"))
    assert ok is False and "state field" in why


def test_the_reason_is_always_returned_so_rejections_can_be_recorded():
    """The ledger should show what was considered, not only what was covered."""
    for p in (prop(), prop(events=1), prop(fields=())):
        _ok, why = beat_test(p)
        assert why.strip()


# ── Closing ──────────────────────────────────────────────────────────────────

def test_a_beat_quiet_for_thirty_days_closes():
    assert should_close(days_since_change=31, pending_triggers=0) is True


def test_a_beat_quiet_for_exactly_thirty_days_stays_open():
    assert should_close(days_since_change=30, pending_triggers=0) is False


def test_a_quiet_beat_with_a_pending_trigger_stays_open():
    """A beat awaiting a filing deadline is not dead, it is waiting."""
    assert should_close(days_since_change=90, pending_triggers=1) is False


# ── The write partition ──────────────────────────────────────────────────────

def test_the_scout_owns_proposals_and_nothing_else():
    assert owned_prefixes("scout") == ("proposals/",)
    assert owns_path("scout", "proposals/2026-08-16.json") is True
    assert owns_path("scout", "beats/fed/state.json") is False
    assert owns_path("scout", "editions/2026-08-16.json") is False


# ── The seam to the wire ─────────────────────────────────────────────────────

class FakeArticle:
    def __init__(self, title, publisher, published_at):
        self.title, self.publisher, self.published_at = title, publisher, published_at
        self.summary, self.url, self.sha256 = "", f"https://{publisher}/x", "s"


class FakeCluster:
    def __init__(self, arts):
        self.articles = arts
        self._idf = {}

    @property
    def publishers(self):
        return {a.publisher for a in self.articles}

    @property
    def size(self):
        return len(self.articles)


def test_a_cluster_becomes_a_proposal_with_its_mechanical_facts_computed():
    """Events, span and publishers are arithmetic and cost nothing. What the
    beat's changeable FIELDS are is a judgement, so it is left empty here for
    the scout agent to fill — the proposal is not testable until it does."""
    c = FakeCluster([
        FakeArticle("Fifth Circuit hears NLRB case", "apnews.com", "2026-08-10T00:00:00Z"),
        FakeArticle("NLRB ruling appealed again", "reuters.com", "2026-08-13T00:00:00Z"),
        FakeArticle("Fifth Circuit sets date", "npr.org", "2026-08-16T00:00:00Z")])
    p = propose_from_cluster(c, name="Fifth Circuit v. NLRB")
    assert p.events == 3
    assert p.span_days == 6
    assert p.publishers == {"apnews.com", "reuters.com", "npr.org"}
    assert p.state_fields == [], "field discovery is the agent's job, not arithmetic"
    assert beat_test(p)[0] is False, "a proposal with no fields cannot open yet"


def test_a_cluster_spanning_one_day_reports_zero_span():
    c = FakeCluster([FakeArticle("a", "x.com", "2026-08-16T01:00:00Z"),
                     FakeArticle("b", "y.com", "2026-08-16T20:00:00Z")])
    assert propose_from_cluster(c, name="Same day").span_days == 0


def test_slugs_are_stable_and_do_not_collide():
    taken = set()
    a = slug_for("Fifth Circuit v. NLRB", taken); taken.add(a)
    b = slug_for("Fifth Circuit v. NLRB", taken)
    assert a == "fifth-circuit-v-nlrb" and b != a and b.startswith(a)


def test_a_proposal_carries_enough_to_record_a_rejection():
    p = propose_from_cluster(FakeCluster([
        FakeArticle("one", "x.com", "2026-08-16T00:00:00Z")]), name="One thing")
    ok, why = beat_test(p)
    rec = p.as_record(opened=ok, reason=why)
    assert rec["name"] == "One thing" and rec["opened"] is False
    assert rec["reason"] and rec["events"] == 1 and rec["publishers"] == ["x.com"]


def test_an_unmeasured_span_is_deferred_not_rejected():
    """"2 days, needs 5" is a false statement when the lookup failed. We do not
    know the span; we failed to measure it. A ledger that reports a failed
    measurement as a finding is worse than one that admits the gap."""
    ok, why = beat_test(prop(span_days=2), span_known=False)
    assert ok is False
    assert "span unknown" in why and "Deferred" in why
    assert "a single day's flurry" not in why


def test_a_measured_short_span_is_still_a_rejection():
    ok, why = beat_test(prop(span_days=2), span_known=True)
    assert ok is False and "flurry" in why


def test_an_unmeasured_span_does_not_excuse_a_beat_with_no_state():
    """The state-field test is independent of history and still governs."""
    ok, why = beat_test(prop(fields=(), span_days=2), span_known=False)
    assert ok is False and "state field" in why
