"""Run the full Document Zero pipeline over real news.db rows.

The extractor is a deterministic stub, not a model: it quotes the source verbatim.
That is deliberate — it exercises quote verification, the refusal gates, the
cascade, placement, ranking and edition assembly on real text, with zero API cost
and zero nondeterminism.
"""
import json, sys, re, collections, sqlite3, pathlib, tempfile
sys.path.insert(0, "/mnt/d/Newsdesk")
from ledger.store import Ledger
from ledger.ingest import normalise
from ledger.beats import load_beats, load_beat_meta
from ledger.sweep import plan_sweep, run_sweep
from ledger import subjects
from ledger.agent import BeatAgent
from ledger.editor import run_editor
from ledger.compile import compile_db
from ledger.verify import Pass, Verdict
from ledger.recirculation import analyse_cluster, Verdict as RV
import yaml

SCRATCH = "/tmp/claude-1000/-mnt-d-Newsdesk/43c08b3d-c307-4435-9eef-eed29502aef4/scratchpad"
rows = json.load(open(f"{SCRATCH}/real_articles.json"))
BEATS = load_beats("/mnt/d/Newsdesk/config/beats.yaml")
BEAT_IDS = [b.id for b in BEATS]
POLICY = yaml.safe_load(open("/mnt/d/Newsdesk/config/policy.yaml"))
NOW = "2026-08-14T10:00:00Z"

from ledger.ceilings import ceiling_for
SHA_TYPE = {}   # sha -> source_type; the stub needs it to respect the ceiling

root = pathlib.Path(tempfile.mkdtemp()) / "data"
ing = Ledger(root, writer="ingest")

def day_of(ts):
    m = re.match(r"(\d{4}-\d{2}-\d{2})", ts or ""); return m.group(1) if m else "1970-01-01"

srcs = []
for r in rows:
    s = normalise(r, BEATS, now=NOW)
    try:
        ing.put_source(day_of(r.get("published_at")), s); srcs.append(s)
        SHA_TYPE[s["sha256"]] = s["source_type"]
    except FileExistsError:
        pass

def _trim(text, n):
    """Never cut mid-word — a truncated quote reads as a fabricated one."""
    t = text.strip()
    if len(t) <= n: return t
    cut = t[:n]
    return cut[:cut.rfind(" ")] if " " in cut else cut

def stub_extractor(prompt):
    """A deterministic stand-in for a model. It is NOT the system's judgment:
    a real extractor writes an atomic claim and tiers it on the evidence. This
    one restates the headline, so treat every record it produces as plumbing."""
    blocks = re.findall(r'<untrusted_source ref="([a-f0-9]{64})">\n(.*?)\n</untrusted_source>',
                        prompt, re.S)
    out = []
    for ref, body in blocks[:3]:
        line = next((l.strip() for l in body.splitlines() if len(l.strip()) > 40), None)
        if not line: continue
        st = SHA_TYPE.get(ref, "misc")
        cap = ceiling_for(st)
        # A headline restatement establishes only that it was published.
        conf = round(min(cap, cap * 0.75), 2)
        out.append({"claim_text": f"Reported: {_trim(line, 90)}",
                    "quote": _trim(line, 60),
                    "source_sha": ref, "confidence": conf,
                    "confidence_justification":
                        f"{st} source, ceiling {cap}; a headline restatement establishes "
                        f"only that the claim was published, not that it is established",
                    "tier": "credible_allegation"})
    return json.dumps(out)

def agree(n, f): return Pass(n, f, lambda c, s: Verdict(False, "supported by the cited quote"))
def proposer(beat):
    def p(old, claims):
        return {"beat": beat, "as_of": "2026-08-14", "fields": [
            {"k": "Most recent claim", "v": claims[0]["claim_text"][:60], "since": "14 Aug",
             "claims": [claims[0]["id"]]},
            {"k": "Claims on record", "v": str(len(claims)), "since": "14 Aug",
             "claims": [c["id"] for c in claims]}]}
    return p

def factory(beat):
    return BeatAgent(ledger=Ledger(root, writer=f"beat:{beat}"), beat=beat, policy=POLICY,
                     extractor=stub_extractor, extractor_family="A",
                     passes=[agree("refute","B"), agree("lens","C")],
                     state_proposer=proposer(beat), subject_resolver=subjects.resolver(POLICY.get('roster')),
                     now=NOW, consensus_required=2)

plan = plan_sweep(srcs, BEAT_IDS, POLICY)
print(f"INGEST   {len(srcs)} sources")
print(f"PLAN     {len(plan.by_beat)} beats with new material, {len(plan.skipped)} skipped")
for b, ss in sorted(plan.by_beat.items()):
    print(f"           {b:14s} {len(ss):3d} sources" + (f"  (+{plan.overflow[b]} carried)" if b in plan.overflow else ""))

for conc in (1, 4):
    res = run_sweep(plan, factory, concurrency=conc)
    sig = sorted((r.beat, r.claims_written, r.error) for r in res)
    if conc == 1: baseline, results = sig, res
print(f"SWEEP    concurrency 1 vs 4 -> {'IDENTICAL' if sig == baseline else 'DIVERGED'}")
print(f"         {sum(r.claims_written for r in results)} claims written, "
      f"{sum(r.cascade_failures for r in results)} failed the cascade, "
      f"{sum(len(r.refused) for r in results)} refused, "
      f"{sum(r.injection_attempts for r in results)} injection attempts logged")

# recirculation per beat, from the real cluster shapes
by_title = collections.defaultdict(list)
for r in rows:
    k = re.sub(r"[^a-z0-9 ]","",(r.get("title") or "").lower())[:60]
    if k: by_title[k].append(r)
clusters = {}
for res_ in results:
    beat_srcs = plan.by_beat.get(res_.beat, [])
    titles = {re.sub(r"[^a-z0-9 ]","",(s.get("title") or "").lower())[:60] for s in beat_srcs}
    worst = RV.FRESH
    for t in titles:
        g = by_title.get(t, [])
        if len(g) < 2: continue
        v = analyse_cluster([{"source_name": x.get("source_name"),
                              "published_at": x.get("published_at")} for x in g],
                            today="2026-08-14").verdict
        if v is RV.DATE_CONFLICT: worst = v; break
        if v is RV.RECIRCULATION: worst = v
    clusters[res_.beat] = worst

ed = run_editor(Ledger(root, writer="editor"), results, day="2026-08-14",
                policy=POLICY, clusters=clusters,
                beat_meta=load_beat_meta("/mnt/d/Newsdesk/config/beats.yaml"))
print()
print("EDITION  2026-08-14")
for k, v in ed.counts.items():
    print(f"           {k:12s} {v}")
print(f"         publish={ed.publish}  blocked_by={ed.publish_blocked_by}")
if ed.refusal_summary: print(f"         refusals: {ed.refusal_summary}")
print()
print("         wire:")
for r in ed.wire:
    print(f"           {r['beat']:14s} score {r['score']:5.2f}  {r['material_changes']} change(s)  {r['claims']} claim(s)")
for r in ed.omissions:
    print(f"           [omission] {r['beat']:12s} {r['reason']}")
for r in ed.holds:
    print(f"           [hold]     {r['beat']:12s} {r['reason'][:60]}")

db = root.parent / "newsdesk.db"
compile_db(root, db)
con = sqlite3.connect(db)
print()
print("COMPILED newsdesk.db")
for t in ("sources","source_beats","claims","beat_state","beat_history"):
    print(f"           {t:14s} {con.execute(f'select count(*) from {t}').fetchone()[0]:6d} rows")
out = pathlib.Path("/mnt/d/Newsdesk/edition-dryrun.json")
out.write_text(json.dumps(ed.to_dict(), indent=2))

# Render the ledger into the site. The page is a view over the ledger, never a
# separate artifact: nothing can appear here that is not in the record.
from ledger.render import build, write_data_js
data = build(root, "/mnt/d/Newsdesk/config/beats.yaml", "2026-08-14")
js = write_data_js(data, "/mnt/d/Newsdesk/data.js")
from ledger.publish import publish
api = publish(data, "/mnt/d/Newsdesk", base_url="https://doczero.epstein-data.com")
print(f"\nRENDERED {js}")
print(f"         llms.txt + {len(api)-1} JSON endpoints")
print(f"         {len(data['beats'])} beats, {len(data['items'])} records, "
      f"{sum(1 for b in data['beats'] if b['status'] != 'quiet')} not quiet")
for b in sorted(data["beats"], key=lambda b: -b["events"])[:6]:
    if b["events"] or b["status"] != "quiet":
        print(f"           {b['status']:14s} {b['events']:3d} claim(s)  {b['name'][:52]}")
