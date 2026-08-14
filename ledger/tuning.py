"""What the unassigned pile is trying to tell us.

Tier-1 routing is keyword-based and therefore always slightly wrong. The point
of this module is that it does not have to be guessed at: every ingested source
records the beats it matched and the score, so the sources that matched nothing
are a labelled dataset of the routing's blind spots, free to query.

No model, no cost — set arithmetic and term frequency. Deliberately so: this is
the diagnostic you want to be able to run every night without thinking about it.

The output distinguishes two different repairs, because they are not the same:

  MISSING KEYWORD — a term that means the same thing an existing beat already
                    tracks. The beat's state fields would not change.
  MISSING BEAT    — a coherent cluster of co-occurring terms with its own state.
                    No existing beat could absorb it without losing coherence.

The module surfaces the evidence for both; deciding which is which is an
editorial call, and it stays with a person.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import collections
import re

STOPWORDS = frozenset("""
the a an and or of to in for on at by with from as is are was were be been being
this that these those it its his her their they them we you i he she who whom
what how why when where new says said say will would could should can may might
about after before over under into than then more most other all one two not no
but if have has had do does did just also only very such own same so
""".split())

MIN_WORD = 3
DEFAULT_MIN_COUNT = 8


@dataclass
class RoutingReport:
    total: int = 0
    assigned: int = 0
    unassigned: int = 0
    missing_terms: list = field(default_factory=list)     # [(term, count)]
    missing_phrases: list = field(default_factory=list)   # [(phrase, count)]
    unrouted_by_source: list = field(default_factory=list)  # [(source, unrouted, total)]
    clusters: list = field(default_factory=list)          # [[phrase, ...]] co-occurring

    @property
    def unassigned_rate(self) -> float:
        return self.unassigned / self.total if self.total else 0.0


def _words(text: str) -> list:
    return [w for w in re.findall(r"[a-z][a-z']{%d,}" % (MIN_WORD - 2), (text or "").lower())
            if w not in STOPWORDS]


def _known(beats):
    """Every keyword, and every word inside a multi-word keyword."""
    phrases = {k.lower() for b in beats for k in b.keywords}
    return phrases, {w for p in phrases for w in p.split()}


def analyse_routing(sources, beats, min_count: int = DEFAULT_MIN_COUNT) -> RoutingReport:
    """Report on what tier-1 routing is missing.

    `sources` are normalised source dicts — the `candidate_beats` already on them
    is the routing decision, so this reads the record rather than re-deriving it.
    """
    known_phrases, known_words = _known(beats)
    r = RoutingReport(total=len(sources))

    unassigned = []
    for s in sources:
        if s.get("candidate_beats"):
            r.assigned += 1
        else:
            r.unassigned += 1
            unassigned.append(s)

    uni, bi = collections.Counter(), collections.Counter()
    for s in unassigned:
        ws = _words(s.get("title"))
        for w in ws:
            if w not in known_words:
                uni[w] += 1
        for a, b in zip(ws, ws[1:]):
            if f"{a} {b}" not in known_phrases:
                bi[f"{a} {b}"] += 1

    r.missing_terms = [(w, n) for w, n in uni.most_common() if n >= min_count]
    r.missing_phrases = [(p, n) for p, n in bi.most_common() if n >= min_count]

    by_src = collections.Counter(s.get("source_name") or "?" for s in unassigned)
    totals = collections.Counter(s.get("source_name") or "?" for s in sources)
    r.unrouted_by_source = sorted(
        ((name, n, totals[name]) for name, n in by_src.items()),
        key=lambda t: -t[1])

    r.clusters = _cluster(r.missing_phrases)
    return r


def _cluster(phrases) -> list:
    """Chain phrases that overlap on a word — 'banks turned' + 'turned blind'.

    A chain that holds together is the shape of a beat; an isolated phrase is
    the shape of a keyword. The distinction is the whole point of the report.
    """
    remaining = {p for p, _ in phrases}
    out = []
    while remaining:
        seed = max(remaining, key=lambda p: dict(phrases)[p])
        chain, changed = {seed}, True
        remaining.discard(seed)
        while changed:
            changed = False
            words = {w for p in chain for w in p.split()}
            for p in sorted(remaining):
                if words & set(p.split()):
                    chain.add(p); remaining.discard(p); changed = True
        if len(chain) > 1:
            out.append(sorted(chain, key=lambda p: -dict(phrases)[p]))
    return out


def format_report(r: RoutingReport, top: int = 12) -> str:
    L = [f"routing: {r.assigned}/{r.total} assigned, "
         f"{r.unassigned} unassigned ({r.unassigned_rate*100:.1f}%)"]
    if r.clusters:
        L.append("\nCO-OCCURRING CLUSTERS — candidates for a NEW BEAT")
        L.append("  (a cluster with its own writable state is a beat, not a keyword)")
        for c in r.clusters[:5]:
            L.append("    " + " · ".join(c[:6]))
    if r.missing_terms:
        L.append("\nUNCOVERED TERMS — candidates for a NEW KEYWORD")
        for w, n in r.missing_terms[:top]:
            L.append(f"    {n:6d}  {w}")
    if r.unrouted_by_source:
        L.append("\nOUTLETS DROPPED WHOLESALE — a routing gap often has a source shape")
        for name, n, tot in r.unrouted_by_source[:6]:
            L.append(f"    {n:5d}/{tot:<5d} {name}")
    return "\n".join(L)
