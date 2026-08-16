"""Ingest the national wire, without deciding in advance what the news is.

The previous ingestion took a hand-written list of 22 beats with keyword lists
and pulled articles matching them. That is backwards twice over:

  - It could only ever find stories someone had already thought of. A story that
    did not match one of 22 guesses was invisible, and 20 of the 22 sat empty
    while the corpus was 96% one subject, because the queries said so.
  - It made the taxonomy permanent. The design says a beat OPENS when enough
    happens and CLOSES after it goes quiet. A YAML file cannot open or close.

So this module pulls broad national coverage and applies no topical filter at
all. What the news is about is decided afterwards, by clustering what actually
arrived (see ledger/emerge.py). Keywords, if they survive anywhere, are a way to
name a cluster after the fact — never a way to find it.

Free sources, no API keys, no cost.
"""
from __future__ import annotations
import hashlib
import re
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse, parse_qs, unquote

# DIRECT publisher feeds first. Google News wraps every link in its own domain
# behind a base64 blob that does not resolve to the article, so a third of all
# fetched bodies came back empty and those stories could only ever produce
# headline-thin claims. A feed that hands over the real URL is worth more than
# one that hands over more headlines.
GOOGLE = "https://news.google.com/rss{path}?hl=en-US&gl=US&ceid=US:en"
FEEDS = [
    ("bbc-world",  "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("bbc-us",     "https://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml"),
    ("aljazeera",  "https://www.aljazeera.com/xml/rss/all.xml"),
    ("independent","https://www.independent.co.uk/news/world/rss"),
    ("latimes",    "https://www.latimes.com/rss2.0.xml"),
    ("politico",   "https://rss.politico.com/congress.xml"),
    ("politico-wh","https://rss.politico.com/politics-news.xml"),
    ("npr",        "https://feeds.npr.org/1001/rss.xml"),
    ("npr-pol",    "https://feeds.npr.org/1014/rss.xml"),
    ("npr-econ",   "https://feeds.npr.org/1017/rss.xml"),
    ("npr-world",  "https://feeds.npr.org/1004/rss.xml"),
    ("pbs",        "https://www.pbs.org/newshour/feeds/rss/headlines"),
    ("thehill",    "https://thehill.com/news/feed/"),
    ("cbs",        "https://www.cbsnews.com/latest/rss/main"),
    ("nbc",        "https://feeds.nbcnews.com/nbcnews/public/news"),
    ("guardian-us","https://www.theguardian.com/us-news/rss"),
    ("propublica", "https://www.propublica.org/feeds/propublica/main"),
    ("courthouse", "https://www.courthousenews.com/feed/"),
    # Kept last and deliberately few: these carry breadth but wrapped links.
    ("g-nation",   GOOGLE.format(path="/headlines/section/topic/NATION")),
    ("g-world",    GOOGLE.format(path="/headlines/section/topic/WORLD")),
]

UA = ("Mozilla/5.0 (compatible; DocumentZero/1.0; +https://doczero.epstein-data.com/) "
      "news aggregation for a public ledger")


@dataclass
class Article:
    url: str
    title: str
    publisher: str
    published_at: str
    summary: str = ""
    feed: str = ""
    sha256: str = field(default="")

    def __post_init__(self):
        if not self.sha256:
            # Identity is the resolved URL. Two feeds carrying one story is one
            # article; the clustering layer decides what is one STORY.
            self.sha256 = hashlib.sha256(self.url.encode("utf-8")).hexdigest()


def resolve(url: str) -> str:
    """Unwrap aggregator redirects so the publisher is visible.

    Google News wraps everything in news.google.com/rss/articles/... . Left
    unwrapped, every article's publisher is "news.google.com", every source
    classifies as an aggregator, and every confidence sits at the floor — which
    is exactly the failure the earlier corpus had with Bing.
    """
    try:
        p = urlparse(url)
    except Exception:
        return url
    if p.netloc.endswith("google.com"):
        q = parse_qs(p.query)
        for k in ("url", "q"):
            if q.get(k):
                return unquote(q[k][0])
    return url


def publisher_of(article_url: str, fallback: str = "") -> str:
    host = (urlparse(article_url).netloc or fallback).lower()
    return host[4:] if host.startswith("www.") else host


_TAG = re.compile(r"<[^>]+>")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", _TAG.sub(" ", text or "")).strip()


def fetch(feeds=None, per_feed: int = 60, pause: float = 0.4, log=None) -> list[Article]:
    """Pull the wire. Returns de-duplicated Articles, newest first."""
    import feedparser

    feeds = feeds or FEEDS
    seen: dict[str, Article] = {}
    for name, url in feeds:
        try:
            parsed = feedparser.parse(url, agent=UA)
        except Exception as e:                     # noqa: BLE001
            if log:
                log(f"  {name}: {type(e).__name__}")
            continue
        n = 0
        for e in (parsed.entries or [])[:per_feed]:
            link = resolve(getattr(e, "link", "") or "")
            if not link.startswith(("http://", "https://")):
                continue
            title = _clean(getattr(e, "title", ""))
            if len(title) < 12:
                continue
            # Google News titles carry " - Publisher"; keep the publisher, drop
            # it from the headline so clustering compares stories not bylines.
            pub = ""
            m = re.match(r"^(.*?)\s+-\s+([^-]{2,40})$", title)
            if m and name.startswith(("top", "nation", "world", "business",
                                      "technology", "science", "health")):
                title, pub = m.group(1).strip(), m.group(2).strip()
            # Google News wraps every link, but the entry carries the real
            # publisher in <source>. Without this every article is attributed to
            # news.google.com, classifies as an aggregator, and sits at the
            # bottom confidence ceiling — the exact failure the earlier corpus
            # had with Bing.
            src = getattr(e, "source", None)
            if src is not None:
                pub = (src.get("title") or pub or "").strip()
                shref = src.get("href") or ""
                if shref:
                    host = publisher_of(shref)
                else:
                    host = publisher_of(link) or pub.lower()
            else:
                host = publisher_of(link) or pub.lower()
            art = Article(
                url=link, title=title, publisher=host or pub or "unknown",
                published_at=_stamp(e), feed=name,
                summary=_clean(getattr(e, "summary", ""))[:600],
            )
            if art.sha256 not in seen:
                seen[art.sha256] = art
                n += 1
        if log:
            log(f"  {name:12s} {n:3d} new")
        time.sleep(pause)
    out = sorted(seen.values(), key=lambda a: a.published_at, reverse=True)
    return out


def _stamp(entry) -> str:
    t = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if t:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", t)
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
