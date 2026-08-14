"""Render the ledger into the shape the site reads.

The published page is a VIEW over verified subgraphs, never a separate artifact
that could drift from them. Everything here is a projection: if a fact is not in
the ledger it cannot appear on the page, and correcting the ledger re-renders
the page. No model, no cost.

Beat identity and editorial weighting come from config; state, history and claims
come from the ledger; the day's lanes come from the edition the editor wrote.
"""
from __future__ import annotations
import json
from pathlib import Path

from . import paths as P
from .beats import load_beats

STATUS_MOVED = "moved"
STATUS_QUIET = "quiet"


def _read(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def build(ledger_root, beats_config: str, day: str) -> dict:
    """Project the ledger into the site's data object."""
    root = Path(ledger_root)
    beats = load_beats(beats_config)
    edition = _read(root / P.edition_path(day)) or {}

    # Which beats the edition touched, and how it placed them.
    placed = {}
    for lane in ("wire", "omissions", "holds"):
        for rec in edition.get(lane, []):
            placed[rec.get("beat")] = (lane, rec)

    dossiers, types = {}, {}
    out_beats, out_items = [], []

    for b in beats:
        state = _read(root / P.beat_state_path(b.id))
        history = []
        hp = root / P.beat_history_path(b.id)
        if hp.exists():
            history = [json.loads(l) for l in hp.read_text(encoding="utf-8").splitlines()
                       if l.strip()]

        claims = []
        cdir = root / f"{P.CLAIMS}/{b.id}"
        if cdir.exists():
            claims = [c for c in (_read(f) for f in sorted(cdir.glob("*.json"))) if c]

        lane, rec = placed.get(b.id, (None, {}))
        # Lane placement wins over emptiness. A beat whose agent failed has no
        # state, but it is NOT quiet — rendering it as quiet would make an
        # unexplained absence indistinguishable from a genuinely still day,
        # which is the exact failure the hold lane exists to prevent.
        status = {"wire": STATUS_MOVED,
                  "omissions": "recirculating",
                  "holds": "unresolved"}.get(lane, STATUS_QUIET)

        for d in b.dossiers:
            dossiers.setdefault(d, {"id": d, "name": d.replace("-", " ").title()})
        for t in b.types:
            types.setdefault(t, {"id": t, "name": t.replace("-", " ").title()})

        # Claims become records on the page. A claim's tier and confidence ride
        # with it — the page cannot present it more strongly than the ledger does.
        for c in claims:
            out_items.append({
                "id": c["id"], "kind": "wire", "beats": [b.id],
                "stamp": {"documented_fact": "documented",
                          "credible_allegation": "open",
                          "question": "open"}.get(c.get("tier"), "open"),
                "title": c.get("claim_text", ""),
                "deck": c.get("confidence_justification", ""),
                "body": [f'Quoted from the source: &ldquo;{c.get("quote","")}&rdquo;'],
                "derived": f"tier {c.get('tier')}, confidence {c.get('confidence')}, "
                           f"survived {c.get('verification_rounds', '?')} verification "
                           f"round(s) on {', '.join(c.get('verifier_families') or []) or 'n/a'}",
                "sources": [{"n": c.get("source_url") or "source",
                             "u": c.get("source_url") or "#",
                             "t": c.get("source_type", "misc"),
                             "c": str(c.get("confidence", ""))}],
                "questions": [],
            })

        out_beats.append({
            "id": b.id, "name": b.name,
            "dossiers": list(b.dossiers), "types": list(b.types),
            "status": status,
            "opened": (history[-1]["d"] if history else "—"),
            "lastChange": (history[0]["d"] if history else "—"),
            "events": len(claims),
            "summary": f"{len(claims)} claim(s) on record.",
            "state": [{"k": f.get("k"), "v": f.get("v"), "since": f.get("since"),
                       "flag": f.get("flag")} for f in (state or {}).get("fields", [])],
            "history": [{"d": h.get("d"), "c": h.get("c"), "s": h.get("s")}
                        for h in reversed(history)],
            "unknown": _unknowns(rec, claims),
            "items": [c["id"] for c in claims], "questions": [], "triggers": [],
        })

    counts = edition.get("counts", {})
    return {
        "edition": {"n": "001", "date": day, "updated": "—", "next": "—"},
        "dossiers": list(dossiers.values()),
        "types": list(types.values()),
        "beats": out_beats,
        "items": out_items,
        "questions": [],
        "triggers": [],
        "contradictions": [],
        "archive": [{"d": day, "n": "001",
                     "items": counts.get("wire", 0),
                     "note": "Published" if edition.get("publish") else
                             f"Not published ({edition.get('publish_blocked_by')})"}],
    }


def _unknowns(rec, claims) -> list:
    """What the page must admit it does not know. Never omitted."""
    out = []
    if rec.get("reason"):
        out.append(f"Held: {rec['reason']}")
    n = rec.get("rejected_claims") or 0
    if n:
        out.append(f"{n} extracted claim(s) failed validation and were discarded.")
    if not claims:
        out.append("No claim has survived verification on this beat.")
    return out


def write_data_js(data: dict, path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("/* generated from the ledger — do not edit by hand */\n"
                 "window.DZ = " + json.dumps(data, indent=1, ensure_ascii=False) + ";\n",
                 encoding="utf-8")
    return p
