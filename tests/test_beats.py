from ledger.beats import should_open, should_close, assign_beats, Beat

def ev(day): return {"day": day}

def test_opens_on_three_events_over_five_days():
    assert should_open([ev("2026-08-01"),ev("2026-08-04"),ev("2026-08-06")], has_trigger=False, state_fields=2)

def test_does_not_open_on_three_events_in_one_day():
    assert not should_open([ev("2026-08-01")]*3, has_trigger=False, state_fields=2)

def test_opens_on_a_single_event_with_a_dated_trigger():
    assert should_open([ev("2026-08-14")], has_trigger=True, state_fields=2)

def test_does_not_open_without_two_writable_state_fields():
    assert not should_open([ev("2026-08-01"),ev("2026-08-04"),ev("2026-08-06")], has_trigger=True, state_fields=1)

def test_closes_after_thirty_quiet_days_with_no_triggers():
    assert should_close(days_since_change=30, pending_triggers=0)

def test_does_not_close_with_a_pending_trigger():
    assert not should_close(days_since_change=400, pending_triggers=1)

def test_does_not_close_before_thirty_days():
    assert not should_close(days_since_change=29, pending_triggers=0)

def test_assign_beats_scores_by_keyword_overlap():
    beats=[Beat("hormuz","Hormuz",["hormuz","blockade","strait"]),
           Beat("fed","Fed",["federal reserve","rate","fomc"])]
    got=assign_beats("Transit through the Strait of Hormuz slowed as the blockade held", beats)
    assert got[0][0]=="hormuz" and got[0][1]>0

def test_assign_beats_returns_empty_when_nothing_matches():
    assert assign_beats("a story about pigeons",[Beat("fed","Fed",["fomc"])])==[]


def test_load_beats_from_config_gives_sixteen_beats():
    from ledger.beats import load_beats
    beats = load_beats("config/beats.yaml")
    assert len(beats) == 16
    assert all(b.keywords for b in beats), "every beat needs keywords for tier-1 assignment"
    assert all(b.dossiers for b in beats), "every beat belongs to at least one dossier"
    ids = [b.id for b in beats]
    assert len(ids) == len(set(ids)), "beat ids must be unique"
