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

Recall is only half the problem. A keyword that matches almost every document in
the corpus carries no information — 'epstein' in an Epstein archive is a stopword,
not a router — and a beat built on one swallows everything. So the report also
names OVER-MATCHING keywords, which is the precision half.

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

# A keyword matching more than this share of the corpus is not discriminating —
# it is describing the archive, not routing within it.
OVER_MATCH_SHARE = 0.5


@dataclass
class RoutingReport:
    total: int = 0
    assigned: int = 0
    unassigned: int = 0
    missing_terms: list = field(default_factory=list)     # [(term, count)]
    missing_phrases: list = field(default_factory=list)   # [(phrase, count)]
    unrouted_by_source: list = field(default_factory=list)  # [(source, unrouted, total)]
    clusters: list = field(default_factory=list)          # [[phrase, ...]] co-occurring
    beat_coverage: list = field(default_factory=list)     # [(beat, matched, share)]
    over_matching: list = field(default_factory=list)     # [(beat, keyword, share)]

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
    docsets = collections.defaultdict(set)   # phrase -> the headlines containing it
    for i, s in enumerate(unassigned):
        ws = _words(s.get("title"))
        for w in ws:
            if w not in known_words:
                uni[w] += 1
        for a, b in zip(ws, ws[1:]):
            ph = f"{a} {b}"
            if ph not in known_phrases:
                bi[ph] += 1
                docsets[ph].add(i)

    r.missing_terms = [(w, n) for w, n in uni.most_common() if n >= min_count]
    r.missing_phrases = [(p, n) for p, n in bi.most_common() if n >= min_count]

    by_src = collections.Counter(s.get("source_name") or "?" for s in unassigned)
    totals = collections.Counter(s.get("source_name") or "?" for s in sources)
    r.unrouted_by_source = sorted(
        ((name, n, totals[name]) for name, n in by_src.items()),
        key=lambda t: -t[1])

    r.clusters = _cluster(r.missing_phrases, docsets)
    r.beat_coverage, r.over_matching = _precision(sources, beats)
    return r


def _precision(sources, beats, share_limit: float = OVER_MATCH_SHARE):
    """Which beats swallow the corpus, and which keyword is responsible.

    Attribution matters: 'this beat is too broad' is not actionable, but
    'this one keyword in it matches 96% of everything' is a one-line fix.
    """
    total = len(sources) or 1
    texts = [" ".join(filter(None, [s.get("title"), s.get("snippet")])).lower()
             for s in sources]

    coverage, over = [], []
    for b in beats:
        hits = sum(1 for s in sources
                   if any(cb.get("beat") == b.id for cb in s.get("candidate_beats", [])))
        coverage.append((b.id, hits, hits / total))
        for kw in b.keywords:
            k = kw.lower()
            n = sum(1 for t in texts if re.search(r"\b" + re.escape(k), t))
            if n / total >= share_limit:
                over.append((b.id, kw, n / total))

    coverage.sort(key=lambda t: -t[1])
    over.sort(key=lambda t: -t[2])
    return coverage, over


CO_OCCUR_MIN = 0.5


def _cluster(phrases, docsets, threshold: float = CO_OCCUR_MIN) -> list:
    """Group phrases that appear in the SAME headlines.

    Word overlap is the wrong signal: chaining transitively on a shared word
    merges unrelated stories that happen to share a common noun, so 'banks
    turned' and 'mexico sues' collapse into one cluster because both eventually
    touch 'epstein'. Document co-occurrence does not have that failure — two
    phrases belong together when the same headlines contain both.

    A group that holds together is the shape of a beat; a lone phrase is the
    shape of a keyword. Keeping those apart is the whole point of the report.
    """
    counts = dict(phrases)
    names = [p for p, _ in phrases]
    parent = {p: p for p in names}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i, a in enumerate(names):
        da = docsets.get(a) or set()
        if not da:
            continue
        for b in names[i + 1:]:
            db = docsets.get(b) or set()
            if not db:
                continue
            inter = len(da & db)
            if inter and inter / len(da | db) >= threshold:
                union(a, b)

    groups = collections.defaultdict(list)
    for p in names:
        groups[find(p)].append(p)
    out = [sorted(g, key=lambda p: -counts[p]) for g in groups.values() if len(g) > 1]
    return sorted(out, key=lambda g: -counts[g[0]])


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
    if r.over_matching:
        L.append("\nOVER-MATCHING KEYWORDS — these route nothing, they describe the archive")
        for beat, kw, share in r.over_matching[:8]:
            L.append(f"    {share*100:5.1f}%  {beat:18s} '{kw}'")
    if r.beat_coverage:
        top = [t for t in r.beat_coverage if t[1]][:6]
        L.append("\nBEAT COVERAGE")
        for beat, n, share in top:
            flag = "  <-- swallows the corpus" if share >= OVER_MATCH_SHARE else ""
            L.append(f"    {n:6d}  {share*100:5.1f}%  {beat}{flag}")
    if r.unrouted_by_source:
        L.append("\nOUTLETS DROPPED WHOLESALE — a routing gap often has a source shape")
        for name, n, tot in r.unrouted_by_source[:6]:
            L.append(f"    {n:5d}/{tot:<5d} {name}")
    return "\n".join(L)
