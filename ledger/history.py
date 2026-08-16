"""How long has this story actually been running?

The beat test asks for events spanning at least five days, because a single
day's flurry is an event and not a beat. But an RSS wire only carries what is on
the front page right now — one to three days — so on a first run every candidate
fails the span test and the system can never open a beat at all. Measured: eight
well-named stories, eight rejections, all for span.

That is a cold start, not a disagreement with the rule. The rule is right; the
wire simply cannot see far enough back to apply it.

GDELT DOC 2.0 can. It indexes global coverage with timestamps, it is free, and
it needs no key. Asking it how many distinct days a story has been covered gives
the beat test the evidence it was always asking for.

Rate limited to one request per five seconds by GDELT, which is a wall-clock
cost and not a money cost.
"""
from __future__ import annotations
import json
import pathlib
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass

API = "https://api.gdeltproject.org/api/v2/doc/doc"
UA = "DocumentZero/1.0 (public-interest news ledger; contact via epstein-data.com)"
MIN_INTERVAL = 5.5          # GDELT asks for one request per 5 seconds
_last_call = [0.0]


@dataclass
class Span:
    days: int
    first: str
    last: str
    articles: int
    distinct_days: int
    # Why the lookup came back empty, when it did. A silent fallback to the
    # wire's own short window looks identical to a story that genuinely is new.
    error: str = ""

    @property
    def found(self) -> bool:
        return self.articles > 0


def _throttle():
    wait = MIN_INTERVAL - (time.time() - _last_call[0])
    if wait > 0:
        time.sleep(wait)
    _last_call[0] = time.time()


def _fetch(query: str, timespan: str, maxrecords: int) -> dict:
    # timelinevol, not artlist. artlist with a record cap returns the NEWEST N
    # articles, which on a busy story are all from today — so every span
    # measured as 0 and the cold start was never actually addressed. The
    # timeline returns daily coverage volume across the whole window, which is
    # the question the beat test is asking.
    qs = urllib.parse.urlencode({
        "query": query, "mode": "timelinevol", "format": "json",
        "timespan": timespan})
    req = urllib.request.Request(f"{API}?{qs}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def span(query: str, timespan: str = "3w", maxrecords: int = 250,
         _fetcher=None, use_cache: bool | None = None) -> Span:
    """Distinct days of coverage for `query`, over `timespan`.

    Returns an empty Span rather than raising when GDELT is unavailable or
    returns something unparseable. A lookup that fails must not open a beat, and
    must not crash the run either: the caller falls back to what the wire itself
    could see, which is the conservative direction.
    """
    fetcher = _fetcher or _fetch
    # Retry on rate limiting. GDELT allows one request every five seconds and
    # answers a burst with a 429 that is not JSON. Without a retry the parse
    # failed, the span came back empty, and the caller silently fell back to the
    # wire's own one-to-three-day window — so stories measured at twenty days by
    # hand were rejected for span in the pipeline, and nothing said why.
    # A day's answer for a given story does not change between runs, and a
    # cached hit costs neither a request nor the throttle wait. This is what
    # makes a daily cron cheap: the same beats are looked up every day.
    # Caching a test double is meaningless, so it follows the real-call path by
    # default. Tests that exercise the cache itself opt in explicitly.
    caching = (_fetcher is None) if use_cache is None else use_cache
    cached = _cache_get(query, timespan) if caching else None
    if cached is not None:
        return cached

    data, err = None, None
    for attempt in range(4):
        if _fetcher is None:
            _throttle()
        try:
            data = fetcher(query, timespan, maxrecords)
            break
        except Exception as e:                               # noqa: BLE001
            err = e
            if _fetcher is not None:
                break
            time.sleep(MIN_INTERVAL * (attempt + 1) * 1.5)
    if data is None:
        return Span(0, "", "", 0, 0, error=f"{type(err).__name__}: {err}"[:120]
                    if err else "no response")

    series = ((data or {}).get("timeline") or [{}])[0].get("data") or []
    covered = [str(p.get("date", ""))[:8] for p in series
               if float(p.get("value") or 0) > 0
               and re.fullmatch(r"\d{8}", str(p.get("date", ""))[:8])]
    if not covered:
        return Span(0, "", "", 0, 0)

    from datetime import datetime
    days = sorted(set(covered))
    d0 = datetime.strptime(days[0], "%Y%m%d").date()
    d1 = datetime.strptime(days[-1], "%Y%m%d").date()
    out = Span(days=(d1 - d0).days, first=days[0], last=days[-1],
               articles=len(series), distinct_days=len(days))
    if caching:
        _cache_put(query, timespan, out)
    return out


CACHE_DIR = pathlib.Path("/mnt/d/Newsdesk/ledger-data/.history-cache")
CACHE_TTL = 12 * 3600


def _cache_key(query: str, timespan: str) -> str:
    import hashlib
    return hashlib.sha256(f"{query}|{timespan}".encode()).hexdigest()[:20]


def _cache_get(query: str, timespan: str):
    f = CACHE_DIR / f"{_cache_key(query, timespan)}.json"
    try:
        if time.time() - f.stat().st_mtime > CACHE_TTL:
            return None
        d = json.loads(f.read_text())
        return Span(**d)
    except Exception:                                        # noqa: BLE001
        return None


def _cache_put(query: str, timespan: str, sp: Span) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        (CACHE_DIR / f"{_cache_key(query, timespan)}.json").write_text(
            json.dumps(sp.__dict__))
    except Exception:                                        # noqa: BLE001
        pass


def query_for(name: str, entities=()) -> str:
    """Build a GDELT query from a story name.

    UNQUOTED. Measured against the live API: quoted phrases matched nothing at
    all — "Zorro Ranch", "Strait of Hormuz" and "Storm Lala" each returned zero
    articles — while the same words unquoted returned full timelines. Two or
    three distinctive words is the shape that works.
    """
    # Split on hyphens: "US-Iran war" returned nothing as one token, and
    # "Iran war" returns a full timeline.
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z']+", name.replace("-", " "))
             if len(w) > 3]
    phrase = " ".join(words[:3]).strip()
    return phrase or (name.strip()[:60] or "news")
