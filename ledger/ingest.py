"""Tier 1. No model. Fetch -> normalise -> content-address -> assign candidate beats.

first_seen is the field the recirculation detector runs on and is the single most
load-bearing value written at this tier.
"""
from __future__ import annotations
import hashlib
from urllib.parse import urlsplit, parse_qsl, urlencode, urlunsplit
from .beats import assign_beats

TRACKING = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
            "fbclid", "gclid", "ref", "_hsenc"}


def canonical_url(url: str) -> str:
    parts = urlsplit(url)
    q = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
         if k.lower() not in TRACKING]
    return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), urlencode(q), ""))


def content_sha(raw: dict) -> str:
    basis = "\n".join([canonical_url(raw.get("url", "")),
                       (raw.get("title") or "").strip(),
                       (raw.get("snippet") or "").strip()])
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def normalise(raw: dict, beats, now: str, source_type: str = "news") -> dict:
    text = " ".join(filter(None, [raw.get("title"), raw.get("snippet"), raw.get("full_text")]))
    return {
        "sha256": content_sha(raw),
        "url": canonical_url(raw.get("url", "")),
        "original_url": raw.get("url", ""),
        "title": raw.get("title") or "",
        "snippet": raw.get("snippet") or "",
        "source_name": raw.get("source_name") or "",
        "source_type": source_type,
        "published_at": raw.get("published_at") or now,
        "first_seen": now,
        "candidate_beats": [{"beat": b, "score": float(s)} for b, s in assign_beats(text, beats)],
    }
