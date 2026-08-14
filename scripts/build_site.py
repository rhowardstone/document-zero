"""Build the site from the persistent ledger: day one, then day two, then render.

The order matters and is the whole point. Day one establishes the beat from news
reporting; day two re-establishes it from the filed court documents. The delta
between them is computed, not written, and it is what the site leads with.

Nothing here calls a model. Costs nothing to run.
"""
import shutil, subprocess, sys, pathlib

ROOT = pathlib.Path("/mnt/d/Newsdesk")
LEDGER = ROOT / "ledger-data"
sys.path.insert(0, str(ROOT))

if LEDGER.exists():
    shutil.rmtree(LEDGER)

import seed_nm_records                      # noqa: E402
import seed_court_record                    # noqa: E402
from ledger.store import Ledger             # noqa: E402
from ledger.diff import diff_state          # noqa: E402
from ledger.render import build, write_data_js   # noqa: E402
from ledger.publish import publish          # noqa: E402
from ledger.compile import compile_db       # noqa: E402

print("DAY 1  news reporting")
seed_nm_records.main(root=LEDGER, as_of="2026-08-13", render=False)
before = Ledger(LEDGER).get_state("nm-records")
print(f"       nm-records: {len(before['fields'])} state field(s), all news-sourced")

print("DAY 2  the filed court documents")
seed_court_record.main(root=LEDGER)
after = Ledger(LEDGER).get_state("nm-records")
delta = diff_state(before, after)
print(f"       nm-records: {len(delta.changed)} changed, {len(delta.added)} added, "
      f"{len(delta.removed)} removed, {delta.unchanged} unchanged")
for c in delta.changed:
    print(f"         ~ {c.k}\n             was {c.old}\n             now {c.new}")
for a in delta.added:
    print(f"         + {a.k} = {a.v}")

led = Ledger(LEDGER, writer="editor")
comp_state = Ledger(LEDGER).get_state("compliance")
comp_delta = diff_state(None, comp_state)

led._write_json("editions/2026-08-14.json", {
    "day": "2026-08-14",
    "wire": [
        {"id": "nm-records", "beat": "nm-records", "score": 24.6, "reason": None,
         "material_changes": delta.material_changes,
         "claims": len(Ledger(LEDGER).list_claims("nm-records")), "rejected_claims": 0,
         "changes": [{"k": c.k, "from": c.old, "to": c.new} for c in delta.changed],
         "added": [{"k": a.k, "v": a.v} for a in delta.added],
         "removed": [{"k": x.k, "v": x.v} for x in delta.removed],
         "unchanged": delta.unchanged},
        {"id": "compliance", "beat": "compliance", "score": 11.2, "reason": None,
         "material_changes": comp_delta.material_changes,
         "claims": len(Ledger(LEDGER).list_claims("compliance")), "rejected_claims": 0,
         "changes": [], "removed": [], "unchanged": 0,
         "added": [{"k": a.k, "v": a.v} for a in comp_delta.added]},
    ],
    "omissions": [], "holds": [],
    "counts": {"wire": 2, "capped_out": 0, "omissions": 0, "holds": 0,
               "refused": 0, "dropped": 0},
    "refusal_summary": {},
    # Publication stays blocked. Nothing has authorised this to go live, and a
    # build script is not the place to decide that.
    "publish": False, "publish_blocked_by": "dry_run",
})

data = build(LEDGER, str(ROOT / "config/beats.yaml"), "2026-08-14")
write_data_js(data, ROOT / "data.js")
publish(data, ROOT, base_url="https://doczero.epstein-data.com")
compile_db(LEDGER, ROOT / "newsdesk.db")

moved = [b for b in data["beats"] if b["status"] != "quiet"]
print(f"\nRENDERED  {len(data['items'])} records, {len(moved)} beat(s) not quiet, "
      f"{len(data['questions'])} question(s), {len(data['contradictions'])} contradiction(s)")
types = {}
for i in data["items"]:
    for s in i.get("sources", []):
        types[s["t"]] = types.get(s["t"], 0) + 1
print(f"          source types: {types}")
