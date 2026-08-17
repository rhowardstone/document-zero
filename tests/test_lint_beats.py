"""The roster is the constitution, so it gets a linter.

Every routine treats `beats.yaml` as authoritative state. A malformed entry
merged at 7pm becomes four desks finding no beats at 6am — and because `desk.md`
treated that as a normal outcome and empty runs are silent, the whole newsroom
would have stopped without anything alerting. The site would sit under
yesterday's honest date indefinitely.

That is exactly what happened when the roster was prose: Beats.md listed beats
under "Standing beats" and never named a desk, while desk.md looked for beats
"under your name". Prose cannot be checked. This can.

The lint failing blocks the merge. That is the point: it turns an editorial rule
into a mechanism, which is the difference between a rule an instance might
follow and one it cannot break.
"""
import pytest

from scripts.lint_beats import LintError, lint

OK = {
    "desks": ["justice", "foreign"],
    "beats": [
        {"slug": "nm-records", "name": "New Mexico v. DOJ", "desk": "justice",
         "tier": "standing", "opened": "2026-08-14",
         "fields": ["Federal suit", "Records sought"],
         "deadlines": [{"date": "2026-09-05", "what": "Response due",
                        "authority": "D.D.C. docket"}]},
        {"slug": "hormuz", "name": "Hormuz blockade", "desk": "foreign",
         "tier": "watch", "opened": "2026-08-16",
         "fields": ["Shipping", "Oil price"]},
    ],
}


def bad(**changes):
    import copy
    d = copy.deepcopy(OK)
    for i, patch in changes.items():
        d["beats"][int(i)].update(patch)
    return d


def test_a_valid_roster_passes():
    assert lint(OK) == []


# ── Desk ownership: the blocker this exists for ─────────────────────────────

def test_a_beat_with_no_desk_is_an_error():
    b = bad(**{"0": {"desk": None}})
    assert any("desk" in e for e in lint(b))


def test_a_beat_on_an_unknown_desk_is_an_error():
    """A typo'd desk name is invisible otherwise: that desk finds no beats and
    reports a normal quiet day."""
    b = bad(**{"0": {"desk": "justise"}})
    assert any("justise" in e for e in lint(b))


def test_every_declared_desk_must_own_at_least_one_beat():
    """A desk with nothing assigned is scheduled to run and do nothing. Either
    give it a beat or stop scheduling it."""
    d = {"desks": ["justice", "foreign", "ghost"], "beats": OK["beats"]}
    assert any("ghost" in e for e in lint(d))


# ── Beat integrity ─────────────────────────────────────────────────────────

def test_fewer_than_two_fields_fails_the_beat_test():
    b = bad(**{"0": {"fields": ["Only one"]}})
    assert any("at least 2" in e for e in lint(b))


def test_a_field_about_our_own_records_is_rejected():
    """"Most recent claim" and "Last updated" describe the ledger. A reader
    learns nothing from them, and they can never fail to change."""
    for f in ("Most recent claim", "Claims on record", "Last updated",
              "Number of sources"):
        b = bad(**{"0": {"fields": ["Federal suit", f]}})
        assert any("record" in e.lower() or "ledger" in e.lower()
                   for e in lint(b)), f


def test_duplicate_slugs_are_rejected():
    b = bad(**{"1": {"slug": "nm-records"}})
    assert any("duplicate" in e.lower() for e in lint(b))


def test_an_unknown_tier_is_rejected():
    b = bad(**{"0": {"tier": "maybe"}})
    assert any("tier" in e for e in lint(b))


def test_a_missing_name_is_rejected():
    """The slug is machine text. A reader must never be shown it."""
    b = bad(**{"0": {"name": ""}})
    assert any("name" in e for e in lint(b))


# ── Dates ──────────────────────────────────────────────────────────────────

def test_a_non_iso_date_is_rejected():
    b = bad(**{"0": {"opened": "08-14-2026"}})
    assert any("ISO" in e for e in lint(b))


def test_a_deadline_without_a_date_is_rejected():
    b = bad(**{"0": {"deadlines": [{"what": "someday"}]}})
    assert any("deadline" in e.lower() for e in lint(b))


def test_a_deadline_without_a_description_is_rejected():
    b = bad(**{"0": {"deadlines": [{"date": "2026-09-05"}]}})
    assert any("deadline" in e.lower() for e in lint(b))


# ── Shape ──────────────────────────────────────────────────────────────────

def test_an_empty_roster_is_an_error_not_a_quiet_day():
    """The single most important assertion here. An empty roster must never be
    mistaken for a newsroom with nothing to do."""
    errs = lint({"desks": ["justice"], "beats": []})
    assert errs and any("no beats" in e.lower() for e in errs)


def test_a_missing_beats_key_is_an_error():
    assert lint({"desks": ["justice"]})


def test_malformed_yaml_raises_rather_than_returning_clean():
    with pytest.raises(LintError):
        lint("not a mapping")


# ── Clock-derived fields ────────────────────────────────────────────────────

def test_an_unmarked_ticking_field_is_rejected():
    """"Days at sea" increments by definition, so the beat is due in every issue
    forever — permanently inflating the delta's threshold and destroying the
    adaptive cadence it exists for. The roster blessed this as a model field."""
    b = bad(**{"0": {"fields": ["Federal suit", "Days at sea"]}})
    assert any("clock-derived" in e for e in lint(b))


def test_a_marked_clock_field_is_allowed_but_does_not_count():
    """Keep it if a reader wants it. It just cannot be the thing that makes the
    beat due, so it does not count toward the two-field minimum."""
    b = bad(**{"0": {"fields": [{"name": "Days at sea", "clock": True},
                                "Federal suit"]}})
    assert any("non-clock" in e for e in lint(b))

    ok = bad(**{"0": {"fields": [{"name": "Days at sea", "clock": True},
                                 "Federal suit", "Records sought"]}})
    assert lint(ok) == []


def test_a_deadline_without_an_authority_is_rejected():
    """"The deadline passed with nothing filed" is unverifiable unless somebody
    knows which record to check. A search failing to find a filing is not
    evidence that none exists."""
    b = bad(**{"0": {"deadlines": [{"date": "2026-09-05", "what": "Response due"}]}})
    assert any("authority" in e for e in lint(b))
