from ledger.diff import diff_state, StateDelta

OLD = {"beat": "hormuz", "as_of": "2026-08-13", "fields": [
    {"k": "Blockade", "v": "In force", "since": "early Aug"},
    {"k": "Transit", "v": "Reduced", "since": "10 Aug"},
    {"k": "Ceasefire", "v": "Holding", "since": "7 Apr"}]}
NEW = {"beat": "hormuz", "as_of": "2026-08-14", "fields": [
    {"k": "Blockade", "v": "In force", "since": "early Aug"},
    {"k": "Transit", "v": "Near standstill", "since": "14 Aug"},
    {"k": "Attacks (24h)", "v": "2", "since": "14 Aug"}]}

def test_detects_a_changed_field():
    d = diff_state(OLD, NEW)
    assert [(c.k, c.old, c.new) for c in d.changed] == [("Transit", "Reduced", "Near standstill")]

def test_detects_an_added_field():
    assert [a.k for a in diff_state(OLD, NEW).added] == ["Attacks (24h)"]

def test_detects_a_removed_field():
    assert [r.k for r in diff_state(OLD, NEW).removed] == ["Ceasefire"]

def test_counts_unchanged():
    assert diff_state(OLD, NEW).unchanged == 1

def test_identical_states_produce_an_empty_delta():
    d = diff_state(OLD, OLD)
    assert d.is_empty and not d.changed and not d.added and not d.removed

def test_a_beat_with_no_prior_state_is_all_added():
    d = diff_state(None, NEW)
    assert len(d.added) == 3 and not d.changed and not d.is_empty

def test_delta_knows_its_beat_and_dates():
    d = diff_state(OLD, NEW)
    assert d.beat == "hormuz" and d.from_date == "2026-08-13" and d.to_date == "2026-08-14"

def test_material_change_count_excludes_since_only_edits():
    old = {"beat": "b", "as_of": "1", "fields": [{"k": "x", "v": "same", "since": "Jan"},
                                                 {"k": "y", "v": "1", "since": "Jan"}]}
    new = {"beat": "b", "as_of": "2", "fields": [{"k": "x", "v": "same", "since": "Feb"},
                                                 {"k": "y", "v": "1", "since": "Jan"}]}
    assert diff_state(old, new).is_empty, "a 'since' touch with no value change is not a change"
