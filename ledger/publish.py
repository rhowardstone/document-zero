"""Publish the agent-facing surface: llms.txt and a static JSON API.

A page is for a person; this is for a machine. The distinction matters because
the two want different things: a reader wants the day's change, an agent wants
to ask questions the site never anticipated — every claim above a confidence,
every beat that has not moved in a month, every source cited by more than one
beat. So the API exposes the ledger's shape, not a curated view of it, and says
plainly what each field means and what it does NOT mean.

Static JSON on purpose: no query endpoint to rate-limit, no database to expose,
cacheable, and it survives the origin going down.
"""
from __future__ import annotations
import html
import json
from pathlib import Path

from .queries import build_queries, query_index

API = "api"


def _clean(obj):
    """Kept as a no-op guard for legacy input.

    The projection no longer escapes, so JSON gets the text as it is and this
    has nothing to undo. It stays because an older ledger, or a hand-written
    fixture, may still carry entities, and serving "defendant&#39;s death" to a
    consumer that renders no markup is a bug either way.
    """
    if isinstance(obj, str):
        return html.unescape(obj)
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean(v) for v in obj]
    return obj


def _w(root: Path, rel: str, obj) -> str:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(_clean(obj), indent=1, ensure_ascii=False), encoding="utf-8")
    return rel


def publish(data: dict, out_root, base_url: str = "") -> list:
    """Write the JSON API from the rendered data object. Returns paths written."""
    root = Path(out_root)
    written = []

    beats = data.get("beats", [])
    items = data.get("items", [])
    by_beat = {}
    for it in items:
        for b in it.get("beats", []):
            by_beat.setdefault(b, []).append(it)

    written.append(_w(root, f"{API}/beats.json", {
        "count": len(beats),
        "beats": [{k: b[k] for k in ("id", "name", "status", "dossiers", "types",
                                     "events", "lastChange")} for b in beats],
    }))

    for b in beats:
        written.append(_w(root, f"{API}/beat/{b['id']}.json", {
            "beat": b,
            "records": by_beat.get(b["id"], []),
        }))

    written.append(_w(root, f"{API}/records.json", {
        "count": len(items),
        "records": items,
    }))

    # Every source cited anywhere, with which beats and records cite it. This is
    # the join an agent most often wants and the site itself never shows.
    sources = {}
    for it in items:
        for s in it.get("sources", []):
            e = sources.setdefault(s["u"], {"url": s["u"], "publisher": s["n"],
                                            "source_type": s["t"], "records": [],
                                            "beats": set()})
            e["records"].append(it["id"])
            e["beats"].update(it.get("beats", []))
    for e in sources.values():
        e["beats"] = sorted(e["beats"])
    written.append(_w(root, f"{API}/sources.json", {
        "count": len(sources),
        "sources": sorted(sources.values(), key=lambda e: -len(e["records"])),
    }))

    # Precomputed query views. See ledger/queries.py for why an index is not a
    # query surface.
    queries = build_queries(data)
    for name, view in queries.items():
        written.append(_w(root, f"{API}/query/{name}.json", view))
    written.append(_w(root, f"{API}/query/index.json",
                      query_index(queries, base_url.rstrip("/") + "/" if base_url else "")))

    written.append(_w(root, f"{API}/edition/{data['edition']['date']}.json", data))
    written.append(_w(root, f"{API}/index.json", {
        "generated_from": "the ledger",
        "edition": data.get("edition"),
        "endpoints": {
            "beats": f"{API}/beats.json",
            "beat": f"{API}/beat/{{beat_id}}.json",
            "records": f"{API}/records.json",
            "sources": f"{API}/sources.json",
            "edition": f"{API}/edition/{{YYYY-MM-DD}}.json",
            "schema": f"{API}/schema.json",
            "queries": f"{API}/query/index.json",
            "query": f"{API}/query/{{name}}.json",
        },
        "counts": {"beats": len(beats), "records": len(items), "sources": len(sources),
                   "queries": len(queries)},
    }))
    written.append(_w(root, f"{API}/schema.json", SCHEMA))
    (root / "llms.txt").write_text(_clean(llms_txt(data, base_url)), encoding="utf-8")
    written.append("llms.txt")
    return written


SCHEMA = {
    "record": {
        "id": "stable identifier",
        "title": "the claim, as an assertion",
        "stamp": "documented | open | hold — the evidentiary tier, NOT an importance rating",
        "beats": "every beat this claim informs; a claim can inform several",
        "corroboration": "count of DISTINCT PUBLISHERS, not of links. Three links "
                         "from one aggregator counts as one.",
        "sources": [{"n": "publisher host", "u": "url", "t": "source type",
                     "c": "confidence, capped by source type"}],
        "derived": "how the claim reached the page, including verification rounds",
    },
    "beat": {
        "status": "moved | recirculating | unresolved | quiet",
        "state": "the beat's current condition as fields; this is what a diff runs over",
        "history": "every revision, newest first",
        "unknown": "what this beat does NOT establish. Never omitted.",
    },
    "confidence_ceilings": {
        "article": 1.0, "inproceedings": 0.95, "book": 0.9, "preprint": 0.85,
        "documentation": 0.85, "techreport": 0.8, "repo": 0.8, "blog": 0.7,
        "news": 0.6, "misc": 0.5,
    },
}


def llms_txt(data: dict, base_url: str = "") -> str:
    ed = data.get("edition", {})
    beats = data.get("beats", [])
    items = data.get("items", [])
    b = base_url.rstrip("/") + "/" if base_url else ""
    moved = [x for x in beats if x["status"] != "quiet"]

    lines = [
        "# Document Zero",
        "",
        "> A daily record of what materially changed in American government and public",
        "> life, and of what was reported without changing. Every claim carries its",
        "> sources and a confidence capped by source type. Produced by AI agents and",
        "> not reviewed by a person before publication.",
        "",
        f"Edition {ed.get('n','?')} · {ed.get('date','?')} · "
        f"{len(beats)} beats, {len(moved)} not quiet, {len(items)} records.",
        "",
        "## Read this before you cite anything here",
        "",
        "- **`stamp` is an evidentiary tier, not an importance rating.** `documented`",
        "  means a primary document or on-the-record proceeding. `open` means an",
        "  identified source asserted it and it is not independently verified. Do not",
        "  restate an `open` record as established fact.",
        "- **`confidence` is capped by source type and cannot exceed the cap.** A wire",
        "  report caps at 0.6; user-generated or aggregated material caps at 0.5. A high",
        "  number does not mean 'true', it means 'as well-supported as this kind of",
        "  source permits'.",
        "- **`corroboration` counts distinct publishers, not links.** Three links from",
        "  one aggregator is one publisher. Treat 1 as uncorroborated.",
        "- **`unknown` on a beat is load-bearing.** It states what the record does not",
        "  establish. Read it before drawing a conclusion from that beat.",
        "- **Absence is not evidence of absence.** A quiet beat means no claim survived",
        "  verification, not that nothing happened.",
        "",
        "## Query surface",
        "",
        f"- [API index]({b}api/index.json): endpoints and counts",
        f"- [Schema]({b}api/schema.json): field meanings and the ceiling table",
        f"- [Beats]({b}api/beats.json): every beat with status and last change",
        f"- [Beat detail]({b}api/beat/BEAT_ID.json): state, history, unknowns, records",
        f"- [Records]({b}api/records.json): every claim with full provenance",
        f"- [Sources]({b}api/sources.json): every source, and which beats and records cite it",
        f"- [Edition]({b}api/edition/{ed.get('date','YYYY-MM-DD')}.json): the whole day",
        "",
        "## Ask a question",
        "",
        "These are answered, not indexed. Each view states the method it was derived",
        "by; check the method before citing the number.",
        "",
    ]
    for name, v in sorted(build_queries(data).items()):
        lines.append(f"- [{v['question']}]({b}api/query/{name}.json) — {v['count']} result(s)")
    lines += [
        "",
        f"Catalogue: [{b}api/query/index.json]({b}api/query/index.json)",
        "",
        "**Read these first.** They exist to expose where the record is weakest:",
        f"`uncorroborated`, `single-publisher-beats`, `unknowns`, `source-types`.",
        "A ledger that only publishes its strengths is not a ledger.",
        "",
        "## Anything else: SQL",
        "",
        f"The compiled ledger ships as [{b}newsdesk.db]({b}newsdesk.db) — one SQLite",
        "file, the same data these views run over. For questions this surface does not",
        "anticipate, query it directly:",
        "",
        "```sql",
        "-- claims whose only support is an aggregator",
        "SELECT c.id, c.claim_text, s.source_name",
        "  FROM claims c JOIN sources s ON s.sha256 = c.source_sha",
        " WHERE s.source_type = \'misc\';",
        "",
        "-- beats that have not changed in 30 days but are still open",
        "SELECT beat, MAX(d) AS last_change FROM beat_history",
        " GROUP BY beat HAVING last_change < date(\'now\', \'-30 days\');",
        "",
        "-- every claim with the source it was extracted from, and its ceiling",
        "SELECT c.tier, c.confidence, s.source_type, s.source_name, c.claim_text",
        "  FROM claims c LEFT JOIN sources s ON s.sha256 = c.source_sha",
        " ORDER BY c.confidence DESC;",
        "```",
        "",
        "## Beats",
        "",
    ]
    for x in sorted(beats, key=lambda x: (x["status"] == "quiet", x["id"])):
        lines.append(f"- [{x['name']}]({b}api/beat/{x['id']}.json): "
                     f"{x['status']}, {x['events']} claim(s), last change {x['lastChange']}")
    lines += ["", "## Provenance", "",
              "Source is git; the site is a view over it. A correction is a new record",
              "that supersedes the old one, and both stay readable. If a fact is not in",
              "the ledger it cannot appear here.", ""]
    return "\n".join(lines)
