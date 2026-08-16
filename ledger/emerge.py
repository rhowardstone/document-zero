"""Let stories emerge from the wire instead of declaring them in a file.

config/beats.yaml listed 22 beats with keyword lists. It could only ever find
stories someone had already imagined, it could not open a new one, and it could
not close a dead one — while the design says a beat opens when enough happens
and closes after it goes quiet. Twenty of the twenty-two sat permanently empty.

This module does the opposite. It takes whatever arrived on the wire and asks
what the day is actually about:

  cluster()   groups articles that are about the same event
  promote()   decides which clusters are STORIES worth tracking, and which are
              singletons that get a line rather than a page
  name()      names a cluster from its own contents, after the fact

Nothing here has a topic list. The only inputs are the articles.

No model, no cost. Clustering is lexical and deliberately conservative: it would
rather leave two related clusters apart than merge two unrelated ones, because a
wrong merge produces a story about two things and reads as nonsense.
"""
from __future__ import annotations
import collections
import re
from dataclasses import dataclass, field

# Words that carry no topical signal. A shared "says" is not a shared story.
STOP = frozenset("""
a an the and or but if then than that this these those there here of in on at by
for to from with without within into onto over under after before during since
is are was were be been being has have had do does did will would can could may
might must should not no nor as it its it's their they them he she his her him
who whom whose which what when where why how new old more most less least first
last next about against between among across amid up down out off just only also
very much many few some any all both each other another said says say told tells
report reports reported according latest update updates news live breaking watch
video photos opinion analysis explainer here's what you need know today amid
after before ahead top best worst how why what
monday tuesday wednesday thursday friday saturday sunday morning evening night
january february march april may june july august september october november
december meanwhile press news reuters associated sunday's today's yesterday
live updates watch read full story exclusive editor's picks sponsored
""".split())

_WORD = re.compile(r"[A-Za-z][A-Za-z'’-]+")
_PROPER = re.compile(r"\b([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){0,3})\b")


def tokens(text: str) -> set[str]:
    return {w.lower() for w in _WORD.findall(text or "")
            if len(w) > 2 and w.lower() not in STOP}


def entities(text: str) -> set[str]:
    """Capitalised runs — crude proper-noun extraction. Two stories about the
    same event almost always share entities even when the wording differs."""
    out = set()
    for m in _PROPER.finditer(text or ""):
        s = m.group(1)
        if s.lower() in STOP or len(s) < 4:
            continue
        out.add(s.lower())
        # Also index the last token, so "Justice Department" and "the Department
        # of Justice" have a chance of meeting.
        parts = s.split()
        if len(parts) > 1:
            out.add(parts[-1].lower())
    return out


@dataclass
class Cluster:
    articles: list = field(default_factory=list)
    _tok: set = field(default_factory=set)
    _ent: set = field(default_factory=set)
    _idf: dict = field(default_factory=dict)

    members: list = field(default_factory=list)   # per-article entity sets

    def add(self, art, tok, ent):
        self.articles.append(art)
        self.members.append(ent)
        self._tok |= tok
        self._ent |= ent

    @property
    def publishers(self) -> set:
        return {a.publisher for a in self.articles}

    @property
    def size(self) -> int:
        return len(self.articles)


def _cosine(a_ent, b_ent, idf) -> float:
    """Cosine over IDF-weighted entity sets.

    Raw overlap merges on whichever name is in every headline. Weighting by
    inverse document frequency makes a name decisive in proportion to how rare
    it is: "Trump" appears across the whole wire and so contributes almost
    nothing, while "Lindsay Clancy" or "Zorro Ranch" is nearly conclusive.
    Unweighted overlap is what put an Amazon multi-tool deal inside the
    Ukraine story.
    """
    shared = a_ent & b_ent
    if not shared:
        return 0.0
    # The dot product of two idf-weighted binary vectors is the sum of idf
    # SQUARED over the shared terms. Writing idf here instead deflated every
    # score by roughly the magnitude of the weights, so articles that were
    # unmistakably the same story scored 0.04-0.19 against a 0.34 threshold and
    # the whole wire came apart into singletons.
    num = sum(idf.get(e, 0.0) ** 2 for e in shared)
    da = sum(idf.get(e, 0.0) ** 2 for e in a_ent) ** 0.5
    db = sum(idf.get(e, 0.0) ** 2 for e in b_ent) ** 0.5
    return 0.0 if not (da and db) else num / (da * db)


def cluster(articles, threshold: float = 0.34, min_idf: float = 1.4) -> list[Cluster]:
    """Single-pass greedy clustering, newest first.

    Conservative on purpose: a wrong merge yields a story about two unrelated
    things, which reads as nonsense and cannot be fixed downstream. Leaving two
    related clusters apart merely produces two stories, which is recoverable.

    A merge additionally requires at least one shared entity that is rare enough
    to mean something (min_idf), so no pair is joined on a ubiquitous name alone.
    """
    import math

    docs = []
    df = collections.Counter()
    for art in articles:
        # Entities come from the HEADLINE ONLY. Many feeds are digests whose
        # <summary> lists several unrelated headlines, and pulling entities from
        # those made one article look related to every story in the digest —
        # which is how a cancer-screening piece ended up inside a murder trial.
        ent = entities(art.title)
        docs.append((art, tokens(f"{art.title} {art.summary}"), ent))
        for e in ent:
            df[e] += 1
    n = max(len(docs), 1)
    idf = {e: math.log(n / (1 + c)) for e, c in df.items()}

    clusters: list[Cluster] = []
    for art, tok, ent in docs:
        best, best_score = None, 0.0
        for c in clusters:
            shared = ent & c._ent
            if not shared or max(idf.get(e, 0.0) for e in shared) < min_idf:
                continue          # nothing rare enough in common
            # AVERAGE linkage. Single linkage chains: it merges A with B and B
            # with C even when A and C have nothing to do with each other, and a
            # long enough chain swallows the whole wire — that is how one
            # cluster came to hold Gaza, competitive corgis and a CEO's layoffs
            # under the heading "People With Depression". Averaging over the
            # members forces a new article to resemble the story as a whole.
            sims = [_cosine(ent, m, idf) for m in c.members]
            s = sum(sims) / len(sims)
            if s > best_score:
                best, best_score = c, s
        if best is not None and best_score >= threshold:
            best.add(art, tok, ent)
        else:
            c = Cluster()
            c.add(art, tok, ent)
            clusters.append(c)
    for c in clusters:
        c._idf = idf
    return sorted(clusters, key=lambda c: (-c.size, -len(c.publishers)))


def name(c: Cluster) -> str:
    """Name a cluster from its own contents, after the fact.

    The most frequent entity across the cluster's headlines, preferring longer
    multi-word names. This is a label for humans, not an identifier.
    """
    counts = collections.Counter()
    for a in c.articles:
        for e in entities(a.title):
            counts[e] += 1
    if not counts:
        return c.articles[0].title[:60]
    # Frequency alone names clusters "Families" and "Abraham Lincoln". Score by
    # how often the name appears AND how distinctive it is AND how specific,
    # so the label is the thing the story is actually about.
    def score(kv):
        ent, n = kv
        return (n / len(c.articles)) * (1 + c._idf.get(ent, 0.0)) * (1 + 0.6 * len(ent.split()))
    best = max(counts.items(), key=score)[0]
    return " ".join(w.capitalize() if w.islower() else w for w in best.split())


def promote(clusters, min_articles: int = 3, min_publishers: int = 3):
    """Split clusters into tracked stories and singletons.

    A story earns a page by being reported by at least three newsrooms. Two is
    not enough: a single outlet's own promos and follow-ups cluster with each
    other, which is how eight CBS trailers for "Sunday Morning" briefly ranked
    as a national story. Corroboration across newsrooms is the same signal the
    ledger already uses on claims.

    Returns (stories, singletons), both ordered by weight.
    """
    stories, singles = [], []
    for c in clusters:
        if c.size >= min_articles and len(c.publishers) >= min_publishers:
            stories.append(c)
        else:
            singles.append(c)
    return stories, singles


def slug(text: str, taken=()) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:48] or "story"
    base, n = s, 2
    while s in taken:
        s = f"{base}-{n}"
        n += 1
    return s
