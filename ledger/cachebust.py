"""Make sure the reader gets today's paper.

Measured on the live site: index.html is served `no-cache` and Cloudflare
treats it as DYNAMIC, but data.js — which holds every headline, date and
paragraph the page displays — came back `max-age=14400`, `cf-cache-status:
EXPIRED`. Cloudflare caches by extension and applies its own four-hour browser
TTL to .js, which overrides the origin's `expires -1`.

For four hours after publication a reader could therefore load a page whose
masthead said one date and whose stories were from the day before. For a
newspaper that is a correctness bug, not a performance one, and it belongs to
the same family as everything else this project keeps catching: a component
stating something it does not actually know.

The fix lives here rather than in a Cloudflare dashboard setting because a
dashboard setting is not in the repository, is not covered by a test, and
cannot be reviewed in a diff. index.html is always fresh, so the edition's
fingerprint travels in the URL that index.html asks for: new edition, new URL,
no cache to be stale.

No model, no cost.
"""
from __future__ import annotations
import hashlib
import re

# src="data.js", src='data.js', src = "data.js?v=old" — with or without an
# existing fingerprint, since a redeploy must replace it rather than stack.
_SRC = re.compile(r"""(<script\b[^>]*\bsrc\s*=\s*)(["'])data\.js(?:\?v=[^"']*)?\2""",
                  re.IGNORECASE)


def fingerprint(data_js: str) -> str:
    """A short, stable, URL-safe digest of the edition's data."""
    return hashlib.sha256((data_js or "").encode("utf-8")).hexdigest()[:12]


def stamp(page: str, data_js: str) -> str:
    """Point the page's <script> at a URL unique to this edition's contents.

    Content-addressed rather than time-addressed on purpose: rebuilding an
    unchanged edition leaves the URL alone, so readers keep their cached copy
    and a page that did not change does not appear to have changed.

    A page whose shape we do not recognise is returned untouched. Failing a
    deploy over an unexpected script tag would be a worse outcome than serving
    the previous caching behaviour.
    """
    return _SRC.sub(
        lambda m: f"{m.group(1)}{m.group(2)}data.js?v={fingerprint(data_js)}{m.group(2)}",
        page or "", count=1)
