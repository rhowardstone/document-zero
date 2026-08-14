from ledger.ingest import normalise, content_sha
from ledger.beats import Beat

BEATS=[Beat("hormuz","Hormuz",["hormuz","blockade","strait"])]
RAW={"url":"https://ex.org/a?utm_source=x","title":"Hormuz transit slows",
     "snippet":"The blockade held as transit through the Strait slowed.",
     "source_name":"Example Wire","published_at":"2026-08-14T03:00:00Z"}

def test_sha_is_stable_and_ignores_tracking_params():
    a=content_sha({**RAW,"url":"https://ex.org/a?utm_source=x"})
    b=content_sha({**RAW,"url":"https://ex.org/a?utm_source=y"})
    assert a==b and len(a)==64

def test_sha_changes_when_content_changes():
    assert content_sha(RAW)!=content_sha({**RAW,"title":"different"})

def test_normalise_produces_a_valid_source_with_first_seen():
    s=normalise(RAW,beats=BEATS,now="2026-08-14T04:00:00Z")
    assert s["first_seen"]=="2026-08-14T04:00:00Z"
    assert s["source_type"]=="news"
    assert s["candidate_beats"][0]["beat"]=="hormuz"

def test_normalise_records_assignment_scores_for_later_measurement():
    s=normalise(RAW,beats=BEATS,now="2026-08-14T04:00:00Z")
    assert isinstance(s["candidate_beats"][0]["score"],float)

def test_unmatched_item_gets_no_beats_but_is_still_stored():
    s=normalise({**RAW,"title":"pigeons","snippet":"pigeons"},beats=BEATS,now="2026-08-14T04:00:00Z")
    assert s["candidate_beats"]==[] and s["sha256"]
