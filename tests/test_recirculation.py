from ledger.recirculation import analyse_cluster, Verdict

def src(name, published, first_seen):
    return {"source_name": name, "published_at": published, "first_seen": first_seen}

def test_single_day_burst_is_fresh():
    r = analyse_cluster([src("AP","2026-08-14T09:00:00Z","2026-08-14T10:00:00Z"),
                         src("CNN","2026-08-14T11:00:00Z","2026-08-14T11:30:00Z")], today="2026-08-14")
    assert r.verdict is Verdict.FRESH

def test_many_outlets_one_day_after_the_original_is_recirculation():
    s = [src("AP","2026-08-13T14:00:00Z","2026-08-13T14:30:00Z")]
    s += [src(f"outlet{i}","2026-08-14T08:00:00Z","2026-08-14T08:00:00Z") for i in range(8)]
    r = analyse_cluster(s, today="2026-08-14")
    assert r.verdict is Verdict.RECIRCULATION
    assert r.origin_date == "2026-08-13"
    assert r.followers == 8

def test_year_old_origin_is_a_date_conflict_hold():
    r = analyse_cluster([src("WJLA","2025-08-14T12:00:00Z","2026-08-14T06:00:00Z"),
                         src("Fox","2025-08-15T12:00:00Z","2026-08-14T06:05:00Z")], today="2026-08-14")
    assert r.verdict is Verdict.DATE_CONFLICT
    assert r.gap_days >= 300

def test_empty_cluster_is_fresh():
    assert analyse_cluster([], today="2026-08-14").verdict is Verdict.FRESH

def test_unparseable_dates_do_not_crash_and_yield_hold():
    r = analyse_cluster([src("X","not-a-date","2026-08-14T06:00:00Z")], today="2026-08-14")
    assert r.verdict in (Verdict.FRESH, Verdict.DATE_CONFLICT)
