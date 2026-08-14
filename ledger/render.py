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
import re
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
    out_beats = []
    # A source routed to several beats yields the same claim once per beat. On
    # the page that is one record about several beats, not several records —
    # rendering it N times was the single most disfiguring bug on the site.
    by_identity: dict = {}
    order: list = []

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

        lane, placement = placed.get(b.id, (None, {}))
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
            # Identity is the CLAIM, not the source. The same finding reaching us
            # from three outlets is one record with three sources — corroboration,
            # which is worth showing — rather than three records, which reads as
            # the page repeating itself.
            identity = _identity(c)
            if identity in by_identity:
                seen = by_identity[identity]
                if b.id not in seen["beats"]:
                    seen["beats"].append(b.id)
                src = _source_of(c)
                if src["u"] not in {s["u"] for s in seen["sources"]}:
                    seen["sources"].append(src)
                    seen["corroboration"] = _distinct_publishers(seen["sources"])
                continue
            item = {
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
                "sources": [_source_of(c)],
                "corroboration": 1,
                "questions": [],
            }
            by_identity[identity] = item
            order.append(item)

        # The omissions lane is the format's central argument: heavy coverage,
        # no underlying change. A beat placed there with no record on the page
        # makes that argument invisible, so it gets one.
        if lane == "omissions":
            order.append({
                "id": f"{b.id}:omission", "kind": "omission", "beats": [b.id],
                "who": b.name, "stamp": None,
                "title": f"{b.name}: covered again, nothing new on the record",
                "short": (f"Reported heavily today, but the underlying state of "
                          f"<b>{b.name}</b> did not change. Reason recorded: "
                          f"<b>{placement.get('reason', 'recirculation')}</b>."),
                "body": [f"The editor placed this beat in the omissions lane because "
                         f"the day's coverage restated what was already on the record. "
                         f"{len(claims)} claim(s) stand on this beat; none of them is new."],
                "derived": f"placed by the editor as {placement.get('reason','recirculation')}",
                "sources": [], "corroboration": 0, "questions": [],
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
            "unknown": _unknowns(placement, claims),
            "items": [c["id"] for c in claims], "questions": [], "triggers": [],
        })

    counts = edition.get("counts", {})
    return {
        "edition": {"n": "001", "date": day, "updated": "—", "next": "—"},
        "dossiers": list(dossiers.values()),
        "types": list(types.values()),
        "beats": out_beats,
        "items": order,
        "questions": [],
        "triggers": [],
        "contradictions": [],
        "archive": [{"d": day, "n": "001",
                     "items": counts.get("wire", 0),
                     "note": "Published" if edition.get("publish") else
                             f"Not published ({edition.get('publish_blocked_by')})"}],
    }


def _distinct_publishers(sources) -> int:
    """Corroboration counts PUBLISHERS, not URLs.

    Three different bing.com links to the same story are one aggregator, not
    three witnesses. Counting URLs would launder a single root into apparent
    independent confirmation — the precise failure claim-ancestry exists to catch,
    reappearing at the render layer if the page counts naively.
    """
    return len({s["n"] for s in sources})


def _identity(claim: dict) -> str:
    """Normalised claim text. Whitespace and casing are not distinctions."""
    return re.sub(r"\s+", " ", (claim.get("claim_text") or "").lower()).strip()


def _source_of(claim: dict) -> dict:
    url = claim.get("source_url") or "#"
    return {"n": _host(url), "u": url,
            "t": claim.get("source_type", "misc"),
            "c": str(claim.get("confidence", ""))}


def _host(url: str) -> str:
    from .sourcetype import host_of
    return host_of(url) or "source"


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
