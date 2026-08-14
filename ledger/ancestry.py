"""Claim ancestry: does 'confirmed by three outlets' resolve to one upstream root?

Without this the system eventually ingests another outlet's error, republishes it
under its own masthead, and gets cited back — circular sourcing with an authority
laundering step in the middle.

Recirculation detection is the degenerate, time-based case of the same idea.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import re


@dataclass(frozen=True)
class Edge:
    child: str
    parent: str


@dataclass(frozen=True)
class RootReport:
    single_root: bool
    apparent_sources: int
    actual_roots: int
    roots: tuple[str, ...] = ()


def _quote_key(quote: str) -> str:
    """Normalised quote identity. Identical wording across outlets is the signal
    that they are republishing rather than independently reporting."""
    norm = re.sub(r"\s+", " ", (quote or "").lower().strip())
    norm = re.sub(r"[^a-z0-9 ]", "", norm)
    return "q:" + hashlib.sha256(norm.encode()).hexdigest()[:16]


def build_edges(claims) -> list[Edge]:
    """Link every claim to a synthetic root derived from its quote, plus any
    explicit parent the extractor recorded."""
    edges: list[Edge] = []
    for c in claims:
        if c.get("parent"):
            edges.append(Edge(c["id"], c["parent"]))
        else:
            edges.append(Edge(c["id"], _quote_key(c.get("quote", ""))))
    return edges


def root_of(claim_id: str, edges) -> str:
    parent = {e.child: e.parent for e in edges}
    seen = {claim_id}
    cur = claim_id
    while cur in parent:
        nxt = parent[cur]
        if nxt in seen:          # cycle: stop where we entered it
            break
        seen.add(nxt)
        cur = nxt
    return cur


def detect_single_root(claims) -> RootReport:
    if len(claims) < 2:
        return RootReport(False, len(claims), len(claims))
    edges = build_edges(claims)
    roots = {root_of(c["id"], edges) for c in claims}
    return RootReport(len(roots) == 1, len(claims), len(roots), tuple(sorted(roots)))
