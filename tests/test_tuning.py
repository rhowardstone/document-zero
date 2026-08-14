from ledger.tuning import analyse_routing, format_report, RoutingReport
from ledger.beats import Beat

BEATS = [Beat("compliance", "DOJ compliance", ["epstein files", "transparency act"]),
         Beat("fed", "Fed", ["federal reserve", "rate hike"])]

def src(title, beats=(), name="Wire"):
    return {"title": title, "source_name": name,
            "candidate_beats": [{"beat": b, "score": 0.4} for b in beats]}

def test_counts_assigned_and_unassigned():
    r = analyse_routing([src("Epstein files released", ["compliance"]),
                         src("Something else entirely")], BEATS, min_count=1)
    assert r.total == 2 and r.assigned == 1 and r.unassigned == 1
    assert abs(r.unassigned_rate - 0.5) < 1e-9

def test_surfaces_terms_no_beat_keyword_covers():
    rows = [src("Jeffrey Epstein banking records") for _ in range(10)]
    r = analyse_routing(rows, BEATS, min_count=5)
    terms = dict(r.missing_terms)
    assert terms.get("jeffrey") == 10 and terms.get("banking") == 10

def test_words_already_inside_a_keyword_are_not_reported_as_missing():
    rows = [src("epstein files and more files") for _ in range(10)]
    r = analyse_routing(rows, BEATS, min_count=1)
    assert "epstein" not in dict(r.missing_terms), "already covered by 'epstein files'"
    assert "files" not in dict(r.missing_terms)

def test_stopwords_are_never_reported():
    rows = [src("The report of the inquiry into the matter") for _ in range(10)]
    r = analyse_routing(rows, BEATS, min_count=1)
    assert not {"the", "of", "into"} & set(dict(r.missing_terms))

def test_min_count_filters_one_off_noise():
    rows = [src("Jeffrey Epstein banking") for _ in range(3)] + [src("Zebra anomaly")]
    r = analyse_routing(rows, BEATS, min_count=3)
    assert "zebra" not in dict(r.missing_terms) and "jeffrey" in dict(r.missing_terms)

def test_overlapping_phrases_chain_into_a_cluster():
    """A cluster that holds together is the shape of a beat."""
    rows = [src("Senate Democrats say banks turned blind eye") for _ in range(10)]
    r = analyse_routing(rows, BEATS, min_count=5)
    assert r.clusters, "co-occurring phrases should chain"
    joined = " ".join(r.clusters[0])
    assert "banks turned" in joined and "turned blind" in joined

def test_an_isolated_phrase_does_not_form_a_cluster():
    rows = ([src("Jeffrey Epstein") for _ in range(10)]
            + [src("Completely unrelated wording") for _ in range(10)])
    r = analyse_routing(rows, BEATS, min_count=5)
    for c in r.clusters:
        assert len(c) > 1, "a single phrase is a keyword candidate, not a beat"

def test_identifies_outlets_dropped_wholesale():
    rows = ([src("x y z", name="r/Epstein") for _ in range(9)]
            + [src("Epstein files ruling", ["compliance"], name="Reuters")])
    r = analyse_routing(rows, BEATS, min_count=1)
    top = r.unrouted_by_source[0]
    assert top[0] == "r/Epstein" and top[1] == 9 and top[2] == 9

def test_a_perfectly_routed_corpus_reports_nothing_to_fix():
    rows = [src("Epstein files ruling", ["compliance"]) for _ in range(5)]
    r = analyse_routing(rows, BEATS, min_count=1)
    assert r.unassigned == 0 and not r.missing_terms and not r.clusters

def test_report_formats_without_crashing_on_an_empty_corpus():
    assert "0/0" in format_report(analyse_routing([], BEATS))

def test_report_names_both_repairs_distinctly():
    rows = [src("Senate Democrats say banks turned blind eye") for _ in range(10)]
    out = format_report(analyse_routing(rows, BEATS, min_count=5))
    assert "NEW BEAT" in out and "NEW KEYWORD" in out
