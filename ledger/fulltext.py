"""Fetch the article, not just the headline.

The wire gives a title and roughly one sentence of summary — about forty words
per report. Claims extracted from forty words are fragments, articles built on
fragments are refused by the entailment gate, and the whole newsroom degrades
into a headline aggregator with a verification step bolted on.

Measured on real pages: 559 and 1,238 words of body text against the ~40 the
feed carried. That is the difference between a claim reading "Trump's legal team
has contracted in size" and one that carries the date, the number and the named
parties a paragraph can be built on.

Best effort by design. A page that times out, blocks us, or yields nothing
usable falls back to the summary — thinner evidence, thinner claims, and a beat
that probably degrades to a one-line entry. That is the correct failure: less
gets said, and nothing unsupported gets said.

Free. Plain HTTP, no key, no service.
"""
from __future__ import annotations
import re
import urllib.request
from dataclasses import dataclass

UA = ("Mozilla/5.0 (compatible; DocumentZero/1.0; "
      "+https://doczero.epstein-data.com/) public-interest news ledger")

# A bare User-Agent gets 403 from a lot of publishers. Sending the headers a
# real browser sends is not a disguise — the UA above still says exactly who we
# are and how to reach us — it just stops a request being rejected for looking
# malformed. Seven of forty fetches were refused this way.
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
}
TIMEOUT = 20
MIN_PARA_WORDS = 12
MIN_BODY_WORDS = 120

# Furniture that lives in <p> tags on news sites and is not the article.
BOILERPLATE = re.compile(
    r"(?i)\b(subscribe|newsletter|sign up|sign in|log in|cookie|privacy policy|"
    r"terms of (use|service)|all rights reserved|follow us|share this|"
    r"advertisement|sponsored|your local (pbs )?station|donate|membership|"
    r"copyright \d{4}|read more:|related:|watch:|listen:|photo by|getty images|"
    r"this story (was|has been) updated|support (our|independent) journalism)\b")

_STRIP_BLOCKS = re.compile(
    r"(?is)<(script|style|nav|header|footer|aside|form|figure|figcaption|"
    r"noscript|iframe|svg)[^>]*>.*?</\1>")
_PARA = re.compile(r"(?is)<p[^>]*>(.*?)</p>")
_DIV = re.compile(r"(?is)<div[^>]*>([^<]{80,})</div>")
_TAGS = re.compile(r"(?s)<[^>]+>")


@dataclass
class Body:
    text: str
    words: int
    url: str
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.words >= MIN_BODY_WORDS


def extract(html: str) -> str:
    """Pull the article body out of a page. Deliberately crude and safe.

    Paragraph tags only: headlines, captions, nav and promo boxes rarely live in
    <p>, and a wrong extraction that swallows a navigation menu would put words
    in a claim that no journalist wrote.
    """
    html = _STRIP_BLOCKS.sub(" ", html or "")
    kept = _paragraphs(_PARA.findall(html))
    if len(" ".join(kept).split()) < MIN_BODY_WORDS:
        # Some sites lay articles out in divs. Five of forty pages yielded no
        # <p> body at all and were discarded despite having a whole article on
        # them.
        kept = _paragraphs(_DIV.findall(html)) or kept

    # Drop leading furniture: real articles open with a substantial paragraph,
    # while promo blocks that survived the filters tend to be shorter.
    while kept and len(kept[0].split()) < 20:
        kept.pop(0)
    return " ".join(kept)


def _paragraphs(raws) -> list:
    kept = []
    for raw in raws:
        t = re.sub(r"\s+", " ", _TAGS.sub(" ", raw)).strip()
        if len(t.split()) < MIN_PARA_WORDS:
            continue
        if BOILERPLATE.search(t):
            continue
        if t not in kept:
            kept.append(t)
    return kept


def fetch(url: str, _opener=None) -> Body:
    """Fetch and extract. Never raises; a failure is a thin Body with a reason."""
    try:
        if _opener is not None:
            html, final = _opener(url)
        else:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                html = r.read(3_000_000).decode("utf-8", "replace")
                final = r.geturl()
    except Exception as e:                                   # noqa: BLE001
        return Body("", 0, url, f"{type(e).__name__}: {str(e)[:90]}")

    body = extract(html)
    return Body(body, len(body.split()), final,
                "" if len(body.split()) >= MIN_BODY_WORDS
                else f"only {len(body.split())} words extracted")
