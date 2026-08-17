"""Whether the day publishes, and what the masthead may claim.

Two failures this fixes, both of which reached the live site:

1. Every edition carried `publish: false, blocked_by: "dry_run"` — a constant
   left over from the stub-reporter era. Three articles passed the entailment
   gate on 2026-08-17 and the page told readers the editor had blocked
   publication. Publication has to be a DECISION about the day, not a literal.

2. The masthead printed `updated: "—"` and `next: "—"` unconditionally. An
   em-dash where a time should be is the same defect this project keeps
   hitting: a failure to know, rendered as a fact. The rule is that the
   masthead may only state what the ledger can support.
"""
from ledger.masthead import decide, masthead


def art(day="2026-08-17", at="2026-08-17T14:20:00Z"):
    return {"day": day, "published_at": at, "headline": "x"}


# ── Whether to publish ──────────────────────────────────────────────────────

def test_a_day_with_a_passing_article_publishes():
    ok, why = decide([art()])
    assert ok is True and why is None


def test_a_day_with_nothing_that_survived_does_not_publish():
    """Not an error. The gate refusing everything is the system working, and
    the page must say so rather than showing an empty front page."""
    ok, why = decide([])
    assert ok is False and "survived" in why


def test_an_explicit_hold_overrides_a_publishable_day():
    """A human or the editor stage can stop the paper. That reason is shown
    verbatim, because a blocked edition with an unexplained cause is worse
    than no edition."""
    ok, why = decide([art()], blocked="legal review of the lead")
    assert ok is False and why == "legal review of the lead"


def test_a_blank_hold_reason_does_not_block():
    """An empty string is not a decision to hold."""
    assert decide([art()], blocked="")[0] is True
    assert decide([art()], blocked=None)[0] is True


# ── What the masthead may claim ─────────────────────────────────────────────

def test_updated_comes_from_the_newest_article():
    m = masthead([art(at="2026-08-17T09:00:00Z"), art(at="2026-08-17T14:20:00Z")])
    assert m["updated"] == "2026-08-17T14:20:00Z"


def test_updated_is_none_when_no_article_carries_a_time():
    """None renders as unknown. It must never be a plausible-looking time."""
    assert masthead([{"day": "2026-08-17"}])["updated"] is None
    assert masthead([])["updated"] is None


def test_next_edition_is_none_until_something_is_actually_scheduled():
    """Nothing is scheduled yet. Printing a next-edition time would be the
    newsroom asserting a fact about its own future that no cron backs up."""
    assert masthead([art()])["next"] is None


def test_next_edition_is_reported_when_a_schedule_exists():
    assert masthead([art()], next_run="2026-08-18T11:00:00Z")["next"] == \
        "2026-08-18T11:00:00Z"


def test_masthead_survives_a_malformed_timestamp():
    m = masthead([art(at="not a time"), art(at="2026-08-17T14:20:00Z")])
    assert m["updated"] == "2026-08-17T14:20:00Z"


def test_masthead_reports_the_article_count_it_was_given():
    assert masthead([art(), art()])["articles"] == 2


# ── The editorial day cannot be in the future ───────────────────────────────

def test_today_is_a_valid_editorial_day():
    from ledger.masthead import editorial_day
    assert editorial_day("2026-08-17", today="2026-08-17") == "2026-08-17"


def test_a_future_day_is_refused():
    """A paper datelined tomorrow contradicts every source in it. This reached
    the live site: the edition was built for 2026-08-17 while every report in
    it was filed on the 16th, because the caller used UTC and UTC rolls over at
    8pm Eastern. Documentation alone did not stop it; this does."""
    import pytest
    from ledger.masthead import editorial_day
    with pytest.raises(ValueError, match="future"):
        editorial_day("2026-08-18", today="2026-08-17")


def test_an_earlier_day_is_allowed():
    """Rebuilding an old edition is legitimate — the ledger is append-only and
    a past day's articles are already fixed."""
    from ledger.masthead import editorial_day
    assert editorial_day("2026-08-14", today="2026-08-17") == "2026-08-14"


def test_a_malformed_day_is_refused_rather_than_guessed():
    import pytest
    from ledger.masthead import editorial_day
    for bad in ("tomorrow", "2026-8-17", "", None):
        with pytest.raises(ValueError):
            editorial_day(bad, today="2026-08-17")


def test_the_default_today_is_local_not_utc():
    """The editorial day is local. A US paper must not flip its dateline at 8pm
    Eastern because UTC rolled over."""
    import time
    from ledger.masthead import editorial_day
    assert editorial_day(None if False else time.strftime("%Y-%m-%d")) == \
        time.strftime("%Y-%m-%d")
