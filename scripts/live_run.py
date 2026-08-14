"""One real cycle: real articles, real model calls, real verification cascade.

COSTS MONEY. Refuses to run unless DZ_ALLOW_PAID_CALLS=1 is set deliberately.
For a free equivalent that exercises the same pipeline with a deterministic
stub extractor, use scripts/dryrun_real.py instead.

Deliberately small — a handful of sources across two beats — because the point
is to prove the contract holds against a live model, not to process a corpus.
"""
import json, sys, re, pathlib, tempfile, time
sys.path.insert(0, "/mnt/d/Newsdesk")
from ledger.store import Ledger
from ledger.ingest import normalise
from ledger.beats import load_beats, load_beat_meta
from ledger.sweep import plan_sweep, run_sweep
from ledger import subjects
from ledger.agent import BeatAgent
from ledger.editor import run_editor
from ledger.client import Cost, AnthropicExtractor, refute_pass, lens_pass
import yaml

SCRATCH = "/tmp/claude-1000/-mnt-d-Newsdesk/43c08b3d-c307-4435-9eef-eed29502aef4/scratchpad"
BEATS = load_beats("/mnt/d/Newsdesk/config/beats.yaml")
POLICY = yaml.safe_load(open("/mnt/d/Newsdesk/config/policy.yaml"))
NOW = "2026-08-14T10:00:00Z"
cost = Cost()

rows = json.load(open(f"{SCRATCH}/real_articles.json"))
# Take a small, recent slice with real text.
picked, seen = [], set()
from ledger.beats import assign_beats
for r in sorted(rows, key=lambda x: x.get("published_at") or "", reverse=True):
    if not (r.get("snippet") or "").strip(): continue
    key = re.sub(r"[^a-z0-9 ]", "", (r.get("title") or "").lower())[:50]
    if key in seen: continue
    # Only sources tier 1 actually routes to a beat — an unrouted article never
    # reaches an agent, so feeding one here would test nothing.
    if not assign_beats(" ".join(filter(None, [r.get("title"), r.get("snippet")])), BEATS):
        continue
    seen.add(key); picked.append(r)
    if len(picked) >= 6: break

root = pathlib.Path(tempfile.mkdtemp()) / "data"
ing = Ledger(root, writer="ingest")
srcs = []
for r in picked:
    s = normalise(r, BEATS, now=NOW)
    try:
        ing.put_source("2026-08-14", s); srcs.append(s)
    except FileExistsError: pass

print(f"SOURCES  {len(srcs)} real articles")
for s in srcs:
    print(f"   {s['source_name'][:18]:18s} {s['title'][:64]}")
    print(f"   {'':18s} beats: {[b['beat'] for b in s['candidate_beats']] or '(none)'}")

plan = plan_sweep(srcs, [b.id for b in BEATS], POLICY)
print(f"\nPLAN     {len(plan.by_beat)} beat(s): {', '.join(sorted(plan.by_beat))}")
if not plan.by_beat:
    print("no beat matched; nothing to do"); sys.exit(0)

extractor = AnthropicExtractor(cost)

def proposer(beat):
    def p(old, claims):
        return {"beat": beat, "as_of": "2026-08-14", "fields": [
            {"k": "Claims on record", "v": str(len(claims)), "since": "14 Aug",
             "claims": [c["id"] for c in claims]},
            {"k": "Latest finding", "v": claims[0]["claim_text"][:70], "since": "14 Aug",
             "claims": [claims[0]["id"]]}]}
    return p

def factory(beat):
    return BeatAgent(ledger=Ledger(root, writer=f"beat:{beat}"), beat=beat, policy=POLICY,
                     extractor=extractor, extractor_family=extractor.family,
                     passes=[refute_pass(cost), lens_pass(cost)],
                     state_proposer=proposer(beat), subject_resolver=subjects.resolver(POLICY.get('roster')),
                     now=NOW, consensus_required=2)

t0 = time.time()
results = run_sweep(plan, factory, concurrency=2)
print(f"\nSWEEP    {time.time()-t0:.1f}s")
for r in sorted(results, key=lambda r: r.beat):
    status = r.error or f"{r.claims_written} written, {r.cascade_failures} failed cascade, {len(r.refused)} refused"
    print(f"   {r.beat:14s} {status}")
    if r.mean_confidence: print(f"   {'':14s} mean confidence {r.mean_confidence:.2f}")

print("\nCLAIMS THAT SURVIVED THE CASCADE")
for r in results:
    for c in Ledger(root).list_claims(r.beat):
        print(f"\n   [{c['tier']}] conf {c['confidence']} · rounds {c.get('verification_rounds')}"
              f" · verifiers {c.get('verifier_families')}")
        print(f"   claim : {c['claim_text'][:150]}")
        print(f"   quote : \"{c['quote'][:110]}\"")
        print(f"   just  : {c['confidence_justification'][:120]}")

ed = run_editor(Ledger(root, writer="editor"), results, day="2026-08-14", policy=POLICY,
                clusters={}, beat_meta=load_beat_meta("/mnt/d/Newsdesk/config/beats.yaml"))
print(f"\nEDITION  {ed.counts} publish={ed.publish} blocked_by={ed.publish_blocked_by}")
print(f"\nCOST     {cost.summary()}")
print(f"         {cost.input_tokens} input, {cost.output_tokens} output, {cost.cache_read_tokens} cache-read")
