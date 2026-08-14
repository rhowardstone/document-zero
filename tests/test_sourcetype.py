import pytest
from ledger.sourcetype import classify, host_of
from ledger.ceilings import ceiling_for

@pytest.mark.parametrize("url,expected", [
    ("https://www.justice.gov/opa/pr/x", "documentation"),
    ("https://www.federalregister.gov/documents/1", "documentation"),
    ("https://www.courtlistener.com/docket/1", "documentation"),
    ("https://crsreports.congress.gov/product/pdf/R/R45281", "techreport"),
    ("https://www.reuters.com/world/x", "news"),
    ("https://www.nbcnews.com/politics/x", "news"),
    ("https://someone.substack.com/p/x", "blog"),
    ("https://www.reddit.com/r/Epstein/comments/1", "misc"),
    ("https://x.com/someone/status/1", "misc"),
    ("https://news.google.com/rss/articles/abc", "misc"),
    ("https://entirely-unknown-outlet.example/story", "misc"),
    ("", "misc"),
])
def test_classification_by_publisher(url, expected):
    assert classify(url) == expected

def test_a_reddit_post_never_carries_news_weight():
    """The bug this module exists to fix: a Reddit comment was typed `news`,
    giving it the same 0.6 ceiling as a wire report."""
    t = classify("https://www.reddit.com/r/Epstein/comments/1vicwl5/x", "r/Epstein")
    assert t == "misc"
    assert ceiling_for(t) < ceiling_for("news")

def test_a_subreddit_source_name_is_ugc_whatever_the_url_says():
    assert classify("https://www.reuters.com/x", "r/Epstein") == "misc"

def test_aggregators_do_not_launder_an_unknown_publisher():
    assert classify("https://example.com/x", "Bing News") == "misc"
    assert classify("https://example.com/x", "Yahoo") == "misc"

def test_www_is_stripped_before_matching():
    assert host_of("https://www.reuters.com/a") == "reuters.com"
    assert classify("https://www.reuters.com/a") == "news"

def test_a_subdomain_of_a_known_newsroom_still_matches():
    assert classify("https://edition.cnn.com/2026/x") == "news"

def test_unknown_defaults_conservative_not_generous():
    """An unrecognised publisher has not earned a higher ceiling."""
    assert ceiling_for(classify("https://who-knows.example/x")) == 0.5

def test_a_malformed_url_does_not_raise():
    assert classify("http://[::1") == "misc"
