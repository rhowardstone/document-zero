"""The Agent API must serve the thing the newspaper actually publishes.

The API was built when this system was a claim graph, and it still described
only claims, beats and sources. After the front page became articles, an agent
reading `api/index.json` on a day with ten published articles saw:

    counts: {"beats": 12, "records": 284, "sources": 95, "queries": 12}

No articles key, no articles endpoint. A machine consumer following the site's
own documentation would conclude the newsroom published nothing that day, while
a human looking at the front page saw ten stories. The site has an "Agent API"
tab in its navigation and an llms.txt telling agents what is available; both
were describing an earlier version of the product.

The articles endpoint carries the paragraph text WITH its claim ids, because
the citation is the part that makes the article checkable. An article served
without them is just prose from an anonymous source.
"""
import json


def _data(articles):
    return {
        "edition": {"date": "2026-08-16", "publish": True, "counts": {}},
        "articles": articles, "beats": [], "items": [], "questions": [],
        "triggers": [], "contradictions": [], "unpublishable": [],
        "dossiers": [], "types": [], "archive": [],
    }


ART = {
    "beat": "nm-records", "beat_name": "New Mexico v. the Justice Department",
    "day": "2026-08-16",
    "headline": "New Mexico sues Justice Department for unredacted records",
    "standfirst": "The complaint names the Acting Attorney General.",
    "dateline": "WASHINGTON", "published_at": "2026-08-16T23:13:04Z",
    "word_count": 764, "verified_by": ["entail-1", "entail-2"],
    "paragraphs": [{"text": "New Mexico has sued the Justice Department.",
                    "claims": ["nm-1", "nm-2"]}],
    "changed": [], "publishers": 10, "claims": 28,
}


def published(tmp_path, articles=(ART,)):
    from ledger.publish import publish
    publish(_data(list(articles)), tmp_path, base_url="https://example.test")
    return tmp_path


def read(tmp_path, rel):
    return json.loads((tmp_path / rel).read_text(encoding="utf-8"))


def test_the_days_articles_are_served(tmp_path):
    out = read(published(tmp_path), "api/articles.json")
    assert len(out["articles"]) == 1
    assert out["articles"][0]["headline"].startswith("New Mexico sues")


def test_an_article_carries_its_citations(tmp_path):
    """Prose without claim ids cannot be checked by the reader it is for."""
    a = read(published(tmp_path), "api/articles.json")["articles"][0]
    assert a["paragraphs"][0]["claims"] == ["nm-1", "nm-2"]


def test_an_article_says_who_verified_it(tmp_path):
    a = read(published(tmp_path), "api/articles.json")["articles"][0]
    assert a["verified_by"] == ["entail-1", "entail-2"]


def test_the_index_counts_and_links_the_articles(tmp_path):
    idx = read(published(tmp_path), "api/index.json")
    assert idx["counts"]["articles"] == 1
    assert idx["endpoints"]["articles"].endswith("articles.json")


def test_a_day_with_no_articles_says_so_rather_than_omitting_the_key(tmp_path):
    """An absent key reads as "this API does not do articles". A zero reads as
    "nothing survived today", which is the true and much more useful thing."""
    idx = read(published(tmp_path, articles=()), "api/index.json")
    assert idx["counts"]["articles"] == 0
    assert read(tmp_path, "api/articles.json")["articles"] == []


def test_llms_txt_points_agents_at_the_articles(tmp_path):
    txt = (published(tmp_path) / "llms.txt").read_text(encoding="utf-8")
    assert "articles.json" in txt
