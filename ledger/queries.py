"""Precomputed query views: the part of the agent surface that answers, not indexes.

llms.txt used to advertise questions like "which claims rest on a single
publisher?" and answer them with "download records.json and filter". That is an
index pretending to be a query surface. An agent that has to fetch the whole
corpus to ask one question will either not ask it or will ask it wrong.

A static site cannot run queries at request time, so the queries run at build
time and ship as answers. Each view carries three things:

  question  — what it answers, in words
  method    — how it was derived, so the answer is checkable rather than trusted
  results   — the rows

`method` is not decoration. These views are the ones most likely to be cited
without reading the underlying records, and a number whose derivation is not
stated is a number that will be repeated with a confidence it did not earn.

Several views deliberately expose the ledger's WEAKNESSES — uncorroborated
claims, beats resting on a single publisher, everything the record does not
establish. A query surface that only surfaces strengths is marketing.
"""
from __future__ import annotations
import collections


def _rec(it: dict) -> dict:
    """A record, trimmed to what a query result needs."""
    return {"id": it.get("id"), "title": it.get("title"), "stamp": it.get("stamp"),
            "beats": it.get("beats", []), "corroboration": it.get("corroboration", 0),
            "sources": [{"publisher": s.get("n"), "url": s.get("u"),
                         "source_type": s.get("t"), "confidence": s.get("c")}
                        for s in it.get("sources", [])]}


def build_queries(data: dict) -> dict:
    """Return {name: view}. Pure function of the rendered data object."""
    beats = data.get("beats", [])
    items = data.get("items", [])
    wire = [i for i in items if i.get("kind") == "wire"]
    by_id = {b["id"]: b for b in beats}
    out = {}

    def view(name, question, method, results, **extra):
        out[name] = {"query": name, "question": question, "method": method,
                     "count": len(results), "results": results, **extra}

    # ── Where the record is weakest ──────────────────────────────────────────
    # Corroboration is a signal about REPORTING, not about documents. Two outlets
    # independently reporting a thing is evidence; one court filing is not
    # "uncorroborated" in the same sense, because the filing is not relaying
    # someone else's claim — it IS the record. Counting them together made the
    # view read as though 30 of 30 claims were weakly sourced when 17 of them
    # were primary documents.
    PRIMARY = {"documentation", "article", "inproceedings", "preprint",
               "techreport", "book"}

    def _kinds(i):
        return {s.get("t") for s in i.get("sources", [])}

    thin = [_rec(i) for i in wire
            if i.get("corroboration", 0) <= 1 and not (_kinds(i) & PRIMARY)]
    primary_single = [_rec(i) for i in wire
                      if i.get("corroboration", 0) <= 1 and (_kinds(i) & PRIMARY)]
    view("uncorroborated",
         "Which published claims rest on a single REPORT that nothing else confirms?",
         "records with kind=wire and corroboration == 1 whose sources are all "
         "reporting types (news, blog, misc). Corroboration counts distinct "
         "publisher hosts, not URLs. Claims resting on a single PRIMARY document "
         "are listed separately below and are not counted here: a court filing is "
         "not relaying someone else's claim, it is the record, so 'only one "
         "source' means something different about it.",
         thin,
         single_primary_document=primary_single,
         single_primary_document_count=len(primary_single))

    single = []
    for b in beats:
        recs = [i for i in wire if b["id"] in i.get("beats", [])]
        pubs = {s.get("n") for i in recs for s in i.get("sources", [])}
        if recs and len(pubs) == 1:
            single.append({"beat": b["id"], "name": b["name"], "records": len(recs),
                           "only_publisher": sorted(pubs)[0]})
    view("single-publisher-beats",
         "Which beats rest entirely on one publisher?",
         "for each beat, the set of distinct publisher hosts across its published "
         "records; beats where that set has exactly one member",
         single)

    view("unknowns",
         "What does the record explicitly NOT establish?",
         "the `unknown` array of every beat, which the renderer never omits",
         [{"beat": b["id"], "name": b["name"], "unknown": b["unknown"]}
          for b in beats if b.get("unknown")])

    view("withheld",
         "What did not publish, and why?",
         "beats the editor placed outside the wire lane, with the recorded reason. "
         "Refused items are counted but their content is not shown, because showing "
         "it would defeat the refusal.",
         [{"beat": b["id"], "name": b["name"], "status": b["status"],
           "reason": (b.get("unknown") or ["not recorded"])[0]}
          for b in beats if b.get("status") in ("unresolved", "recirculating")],
         lane_counts=(data.get("edition", {}) or {}).get("counts", {}))

    # ── Joins the site itself never shows ────────────────────────────────────
    cross = []
    seen = {}
    for i in wire:
        for s in i.get("sources", []):
            e = seen.setdefault(s.get("u"), {"url": s.get("u"), "publisher": s.get("n"),
                                             "beats": set(), "records": []})
            e["beats"].update(i.get("beats", []))
            e["records"].append(i.get("id"))
    for e in seen.values():
        if len(e["beats"]) > 1:
            cross.append({**e, "beats": sorted(e["beats"])})
    view("cross-beat-sources",
         "Which single sources inform more than one beat?",
         "sources grouped by URL across published records; those whose beat set "
         "has more than one member. A source spanning beats is either a genuine "
         "connection or a routing error, and both are worth seeing.",
         sorted(cross, key=lambda e: -len(e["beats"])))

    dist = collections.Counter(s.get("t") for i in wire for s in i.get("sources", []))
    view("source-types",
         "What kinds of source is the record actually built on?",
         "source_type of every source on every published record. The confidence "
         "ceiling follows from this distribution: a corpus of `news` and `misc` "
         "cannot produce high-confidence claims however clearly written.",
         [{"source_type": k, "sources": v} for k, v in dist.most_common()])

    # ── The timeline ─────────────────────────────────────────────────────────
    # Built because a sequence cannot be hidden the way an isolated fact can.
    # Gaps in it are findings, not absences.
    tl = []
    for b in beats:
        for h in b.get("history", []):
            tl.append({"date": h.get("d"), "beat": b["id"], "beat_name": b["name"],
                       "event": h.get("c"), "support": h.get("s")})
    tl.sort(key=lambda r: str(r.get("date") or ""))
    view("timeline",
         "Every dated event on the record, chronologically.",
         "every history row of every beat, sorted by date ascending. Sequence is "
         "the thing individual facts cannot show: a gap here, where other evidence "
         "says events occurred, is a finding rather than an absence.",
         tl)

    view("upcoming",
         "What is due next, and what does non-response mean?",
         "dated triggers sorted ascending. A passed trigger with no filing is "
         "itself recordable.",
         data.get("triggers", []))

    view("open-questions",
         "What is unresolved, and which document would resolve it?",
         "every open question with the document that would answer it and whether "
         "anyone is scheduled to produce that document",
         data.get("questions", []))

    view("contradictions",
         "Which statements on the record cannot both be true?",
         "recorded contradiction pairs with the source of each side. These are "
         "not resolved by the system; they are carried until a document resolves them.",
         data.get("contradictions", []))

    # ── Every claim, by tier ─────────────────────────────────────────────────
    for tier, label in (("documented", "documented_fact"), ("open", "credible_allegation")):
        view(f"tier-{tier}",
             f"Which published claims are stamped `{tier}`?",
             f"records with kind=wire and stamp={tier}. `{tier}` maps to the prose "
             f"tier `{label}`; the stamp governs how the claim may be restated, "
             f"not how important it is.",
             [_rec(i) for i in wire if i.get("stamp") == tier])

    return out


def query_index(queries: dict, base: str = "") -> dict:
    """A catalogue an agent can read to discover what it can ask."""
    return {
        "about": "Precomputed answers. A static site cannot query at request time, "
                 "so the queries run at build time. Each view states the method it "
                 "was derived by; check the method before citing the number.",
        "caution": "Several of these views exist to expose weakness in the record — "
                   "uncorroborated claims, beats resting on one publisher, and "
                   "everything the record does not establish. Read those first.",
        "sql": "The compiled ledger ships as newsdesk.db (SQLite). Use it for any "
               "question not answered here; it is the same data these views run over.",
        "queries": [{"query": k, "question": v["question"], "count": v["count"],
                     "url": f"{base}api/query/{k}.json"}
                    for k, v in sorted(queries.items())],
    }
