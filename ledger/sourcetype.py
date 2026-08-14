"""Classify a source before anything else touches it.

Source type is not decoration: it sets the confidence ceiling, so getting it
wrong silently mis-weights every claim built on it. Ingest previously typed
everything `news`, which gave an anonymous Reddit comment the same evidentiary
standing as a wire report — 0.6 either way. That is the exact failure the
ceilings exist to prevent, committed one layer below them.

Classification is by publisher, deterministic, and conservative: anything
unrecognised is `misc` (0.5), because an unknown publisher has not earned more.
"""
from __future__ import annotations
import re
from urllib.parse import urlsplit

# Primary and official material. Ceiling 0.85.
DOCUMENTATION = (
    r"\.gov$", r"\.gov\.", r"\.mil$", r"courtlistener\.com$", r"pacer\.",
    r"federalregister\.gov$", r"^congress\.gov$", r"supremecourt\.gov$",
    r"justice\.gov$", r"sec\.gov$", r"europa\.eu$", r"parliament\.uk$",
    r"judiciary\.senate\.gov$", r"oversight\.house\.gov$",
)
# Research and institutional analysis. Ceiling 0.8.
# Note the anchoring above: a bare `congress.gov` pattern would also swallow
# `crsreports.congress.gov`, typing a research product as a primary record and
# handing it a higher ceiling than it has earned.
TECHREPORT = (
    r"\.edu$", r"crsreports\.congress\.gov$", r"gao\.gov$", r"cbo\.gov$",
    r"brookings\.edu$", r"americanactionforum\.org$", r"rand\.org$",
)
# Established newsrooms with corrections policies. Ceiling 0.6.
NEWS = (
    r"reuters\.com$", r"apnews\.com$", r"nytimes\.com$", r"washingtonpost\.com$",
    r"wsj\.com$", r"bbc\.co\.uk$", r"bbc\.com$", r"theguardian\.com$",
    r"npr\.org$", r"cnn\.com$", r"nbcnews\.com$", r"cbsnews\.com$",
    r"abcnews\.go\.com$", r"foxnews\.com$", r"politico\.com$", r"axios\.com$",
    r"bloomberg\.com$", r"ft\.com$", r"usatoday\.com$", r"thehill\.com$",
    r"newsweek\.com$", r"courthousenews\.com$", r"forbes\.com$", r"time\.com$",
    r"latimes\.com$", r"independent\.co\.uk$", r"telegraph\.co\.uk$",
    r"aljazeera\.com$", r"cnbc\.com$", r"pbs\.org$", r"propublica\.org$",
)
# Individually authored, no editorial layer. Ceiling 0.7.
BLOG = (r"substack\.com$", r"medium\.com$", r"wordpress\.com$", r"blogspot\.com$",
        r"ghost\.io$")
# User-generated or aggregated. Ceiling 0.5 — no publisher stands behind it.
MISC = (r"reddit\.com$", r"x\.com$", r"twitter\.com$", r"facebook\.com$",
        r"youtube\.com$", r"tiktok\.com$", r"news\.google\.com$", r"bing\.com$",
        r"news\.yahoo\.com$", r"t\.me$", r"4chan\.", r"rumble\.com$")

# Order matters: specific before general. TECHREPORT is checked first because a
# bare `.gov$` in DOCUMENTATION would otherwise swallow research hosts like
# crsreports.congress.gov and gao.gov, typing analysis as a primary record.
_TABLE = ((TECHREPORT, "techreport"), (DOCUMENTATION, "documentation"),
          (NEWS, "news"), (BLOG, "blog"), (MISC, "misc"))

# Aggregator source_name values that mask the real publisher.
AGGREGATOR_NAMES = {"bing news", "google news", "yahoo", "yahoo news", "news break",
                    "msn", "smartnews", "flipboard"}
UGC_NAME = re.compile(r"^(r/|u/|@)", re.IGNORECASE)


def host_of(url: str) -> str:
    try:
        h = (urlsplit(url or "").hostname or "").lower()
    except ValueError:
        return ""
    return h[4:] if h.startswith("www.") else h


def classify(url: str = "", source_name: str = "") -> str:
    """Return the BibTeX-style source type. Unrecognised publishers are `misc`."""
    name = (source_name or "").strip().lower()
    # A subreddit or handle is user-generated regardless of what URL it carries.
    if UGC_NAME.match(name) or name in AGGREGATOR_NAMES:
        return "misc"

    host = host_of(url)
    if not host:
        return "misc"
    for patterns, label in _TABLE:
        if any(re.search(p, host) for p in patterns):
            return label
    return "misc"
