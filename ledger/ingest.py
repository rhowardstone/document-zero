"""Tier 1. No model. Fetch -> normalise -> content-address -> assign candidate beats.

first_seen is the field the recirculation detector runs on and is the single most
load-bearing value written at this tier.
"""
from __future__ import annotations
import hashlib
from urllib.parse import urlsplit, parse_qsl, urlencode, urlunsplit
from .beats import assign_beats
from .sourcetype import classify

TRACKING = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
            "fbclid", "gclid", "ref", "_hsenc"}


def canonical_url(url: str) -> str:
    parts = urlsplit(url)
    q = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
         if k.lower() not in TRACKING]
    return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), urlencode(q), ""))


def content_sha(raw: dict) -> str:
    """Hash the EVIDENCE, not the link to it.

    Hashing url+title+snippet is link provenance: two different bodies with the
    same metadata collide, and a page that is later edited or deleted cannot be
    shown to have changed. The body is therefore part of the identity, and the
    body is retained (below) so a claim's quote can be re-checked against the
    exact bytes it was drawn from after the page is gone.
    """
    basis = "\n".join([canonical_url(raw.get("url", "")),
                       (raw.get("title") or "").strip(),
                       (raw.get("snippet") or "").strip(),
                       (raw.get("full_text") or "").strip()])
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def normalise(raw: dict, beats, now: str, source_type: str | None = None) -> dict:
    text = " ".join(filter(None, [raw.get("title"), raw.get("snippet"), raw.get("full_text")]))
    # Type by publisher unless the caller knows better. Getting this wrong
    # mis-sets the confidence ceiling for every claim built on the source.
    st = source_type or classify(raw.get("url", ""), raw.get("source_name", ""))
    return {
        "sha256": content_sha(raw),
        "url": canonical_url(raw.get("url", "")),
        "original_url": raw.get("url", ""),
        "title": raw.get("title") or "",
        "snippet": raw.get("snippet") or "",
        # Retained deliberately: without the body, a quote can never be
        # re-verified once the page changes, and "exact quote required" becomes
        # unenforceable the moment the web moves on.
        "full_text": raw.get("full_text") or "",
        "retrieved_at": now,
        "source_name": raw.get("source_name") or "",
        "source_type": st,
        "published_at": raw.get("published_at") or now,
        "first_seen": now,
        "candidate_beats": [{"beat": b, "score": float(s)} for b, s in assign_beats(text, beats)],
    }
