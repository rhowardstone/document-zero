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
    # ex.org is not a recognised publisher, so it types conservatively.
    assert s["source_type"]=="misc"
    assert s["candidate_beats"][0]["beat"]=="hormuz"

def test_normalise_records_assignment_scores_for_later_measurement():
    s=normalise(RAW,beats=BEATS,now="2026-08-14T04:00:00Z")
    assert isinstance(s["candidate_beats"][0]["score"],float)

def test_unmatched_item_gets_no_beats_but_is_still_stored():
    s=normalise({**RAW,"title":"pigeons","snippet":"pigeons"},beats=BEATS,now="2026-08-14T04:00:00Z")
    assert s["candidate_beats"]==[] and s["sha256"]


def test_source_type_is_classified_from_the_publisher_not_assumed():
    r = {"url": "https://www.reddit.com/r/Epstein/comments/1/x", "title": "T",
         "snippet": "body", "source_name": "r/Epstein",
         "published_at": "2026-08-14T03:00:00Z"}
    assert normalise(r, BEATS, now="n")["source_type"] == "misc"

def test_a_wire_outlet_is_typed_news():
    r = {"url": "https://www.reuters.com/world/x", "title": "T", "snippet": "b",
         "source_name": "Reuters", "published_at": "2026-08-14T03:00:00Z"}
    assert normalise(r, BEATS, now="n")["source_type"] == "news"

def test_a_government_document_is_typed_documentation():
    r = {"url": "https://www.federalregister.gov/documents/1", "title": "T",
         "snippet": "b", "source_name": "Federal Register",
         "published_at": "2026-08-14T03:00:00Z"}
    assert normalise(r, BEATS, now="n")["source_type"] == "documentation"

def test_an_explicit_source_type_still_wins():
    r = {"url": "https://www.reuters.com/x", "title": "T", "snippet": "b",
         "source_name": "Reuters", "published_at": "2026-08-14T03:00:00Z"}
    assert normalise(r, BEATS, now="n", source_type="techreport")["source_type"] == "techreport"


def test_the_hash_covers_the_body_not_just_the_metadata():
    """Regression: hashing url+title+snippet is link provenance. Two different
    bodies with identical metadata collided, and an edited page was undetectable."""
    a = dict(RAW, full_text="the original body")
    b = dict(RAW, full_text="a materially different body")
    assert content_sha(a) != content_sha(b)

def test_the_body_is_retained_so_a_quote_stays_checkable():
    s = normalise(dict(RAW, full_text="the full article body"), BEATS, now="n")
    assert s["full_text"] == "the full article body"
    assert s["retrieved_at"] == "n"
