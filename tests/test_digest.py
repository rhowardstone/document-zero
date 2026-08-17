"""The delta digest: what moved since each beat last appeared.

This is the Sleuthsletter form — "here is what changed" across every beat — but
generated rather than curated, and on an ADAPTIVE cadence rather than a clock.

Cadence is per-beat by construction. A beat appears in an issue only when its
own state has changed since the last issue it appeared in, so a fast-moving war
beat shows up in most issues and a court case awaiting a September filing shows
up when the filing lands. Nobody sets a schedule; the news sets it.

The one rule that makes a delta worth reading: it must never pad. An issue full
of "no change" entries is not a digest, it is a status page, and it trains the
reader to skip. So the digest refuses to fire on nothing, and quiet beats are
COUNTED rather than enumerated.

A lapsed deadline fires an issue on its own. A dated obligation passing without
the expected filing is a finding — the non-event is recordable — and it is the
one thing a reader could not learn by watching the wire.

No model, no cost: every value here is a field transition already on the record.
"""
import pytest

from ledger.digest import (MAX_WAIT_DAYS, MIN_DUE, compose, due_beats,
                           should_fire)

TODAY = "2026-08-17"


def beat(slug, changed_on, changes=(("Death toll", "4", "7"),)):
    return {"beat": slug, "changed_on": changed_on,
            "changes": [{"k": k, "from": f, "to": t} for k, f, t in changes]}


# ── Which beats are due ─────────────────────────────────────────────────────

def test_a_beat_that_moved_since_its_last_issue_is_due():
    b = beat("flood", "2026-08-17")
    assert [x["beat"] for x in due_beats([b], {"flood": "2026-08-14"})] == ["flood"]


def test_a_beat_that_has_not_moved_since_its_last_issue_is_not_due():
    """This is the whole cadence mechanism: no change, no appearance."""
    b = beat("court", "2026-08-14")
    assert due_beats([b], {"court": "2026-08-14"}) == []


def test_a_beat_never_digested_is_due_the_first_time_it_moves():
    b = beat("newbeat", "2026-08-17")
    assert len(due_beats([b], {})) == 1


def test_a_beat_with_no_recorded_change_is_never_due():
    """A beat can be open and monitored and simply have nothing to say."""
    assert due_beats([beat("quiet", None, changes=())], {}) == []


def test_beats_are_returned_in_a_stable_order():
    bs = [beat("zulu", TODAY), beat("alpha", TODAY)]
    assert [x["beat"] for x in due_beats(bs, {})] == ["alpha", "zulu"]


# ── When an issue fires ─────────────────────────────────────────────────────

def test_enough_movement_fires_an_issue():
    due = [beat(f"b{i}", TODAY) for i in range(MIN_DUE)]
    fires, why = should_fire(due, lapsed=[], days_since_last=1, today=TODAY)
    assert fires and "beats moved" in why


def test_a_single_beat_moving_does_not_fire_an_issue_immediately():
    """One beat moving is a story, and the front page already carries it. A
    digest of one entry is a news alert wearing a digest's clothes."""
    fires, _ = should_fire([beat("b0", TODAY)], lapsed=[],
                           days_since_last=1, today=TODAY)
    assert fires is False


def test_a_lapsed_deadline_fires_an_issue_on_its_own():
    """A dated obligation passing without the expected filing is a finding, and
    the one thing a reader cannot get by watching the wire."""
    lapsed = [{"beat": "nm-records", "sort": "2026-08-16",
               "t": "Government response due"}]
    fires, why = should_fire([], lapsed=lapsed, days_since_last=1, today=TODAY)
    assert fires and "lapsed" in why


def test_one_beat_fires_once_enough_time_has_passed():
    fires, why = should_fire([beat("b0", TODAY)], lapsed=[],
                             days_since_last=MAX_WAIT_DAYS, today=TODAY)
    assert fires and "since the last issue" in why


def test_nothing_due_never_fires_however_long_it_has_been():
    """Padding is the one thing that would destroy this format."""
    fires, why = should_fire([], lapsed=[], days_since_last=90, today=TODAY)
    assert fires is False and "nothing" in why


# ── The issue itself ────────────────────────────────────────────────────────

def test_an_entry_states_the_transition_not_just_the_new_value():
    """"Death toll: 7" is a fact. "Death toll: 4 -> 7" is the news."""
    d = compose([beat("flood", TODAY)], quiet=0, lapsed=[], day=TODAY,
                names={"flood": "Indiana record flooding"})
    e = d["entries"][0]
    assert e["name"] == "Indiana record flooding"
    assert e["changes"][0]["from"] == "4" and e["changes"][0]["to"] == "7"


def test_a_new_field_is_shown_as_new_rather_than_as_a_change_from_nothing():
    """from:"" would render as "-> 7" with a dangling arrow, or worse as a
    change from a value that never existed."""
    b = beat("flood", TODAY, changes=(("Federal aid", "", "Approved"),))
    e = compose([b], quiet=0, lapsed=[], day=TODAY, names={})["entries"][0]
    assert e["changes"][0]["new"] is True


def test_quiet_beats_are_counted_and_not_listed():
    d = compose([beat("flood", TODAY)], quiet=9, lapsed=[], day=TODAY, names={})
    assert d["quiet"] == 9 and len(d["entries"]) == 1


def test_lapsed_deadlines_are_carried_in_the_issue():
    lapsed = [{"beat": "nm-records", "sort": "2026-08-16", "t": "Response due"}]
    d = compose([], quiet=3, lapsed=lapsed, day=TODAY, names={})
    assert d["lapsed"][0]["t"] == "Response due"


def test_the_issue_records_the_day_it_covers():
    assert compose([], quiet=0, lapsed=[], day=TODAY, names={})["day"] == TODAY


def test_an_empty_issue_is_representable_but_marked_empty():
    """compose() must not decide whether to publish — should_fire does. But an
    issue with nothing in it must never look like an issue with content."""
    d = compose([], quiet=12, lapsed=[], day=TODAY, names={})
    assert d["empty"] is True


def test_an_issue_with_entries_is_not_empty():
    assert compose([beat("f", TODAY)], quiet=0, lapsed=[], day=TODAY,
                   names={})["empty"] is False


# ── Lapsed-trigger detection ────────────────────────────────────────────────

def test_a_trigger_whose_date_has_passed_is_lapsed():
    from ledger.digest import lapsed_triggers
    trigs = [{"beat": "b", "sort": "2026-08-16", "t": "due"},
             {"beat": "b", "sort": "2026-09-05", "t": "later"}]
    assert [t["t"] for t in lapsed_triggers(trigs, TODAY)] == ["due"]


def test_a_trigger_dated_today_has_not_lapsed_yet():
    from ledger.digest import lapsed_triggers
    assert lapsed_triggers([{"beat": "b", "sort": TODAY, "t": "today"}], TODAY) == []


def test_a_trigger_with_no_date_is_not_lapsed():
    from ledger.digest import lapsed_triggers
    assert lapsed_triggers([{"beat": "b", "t": "someday"}], TODAY) == []
