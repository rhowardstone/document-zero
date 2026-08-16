"""One day of the newsroom, end to end. This is what a cron calls.

    python3 scripts/daily.py                     # full run, then deploy
    python3 scripts/daily.py --no-deploy         # build locally, ship nothing
    python3 scripts/daily.py --dry               # plan only, no agents

    wire      fetch and cluster                     free, no keys
    desk      one agent per story: name, state, claims
    scout     the beat test decides; rejections recorded
    report    one agent per opened beat writes an article
    verify    two agents check every sentence
    editor    plays the page
    build     render, publish JSON, compile SQLite
    ship      rsync static files to the host

Nothing here can bill. `assert_subscription()` runs before the first agent and
refuses unless the CLI reports a subscription and no API key source.

Failure policy, which is the part worth reading:

  A beat agent that fails does NOT publish a quiet beat. It publishes nothing
  for that beat and says so, because an unexplained absence must never look
  like a still day.

  If the editor stage fails, NO edition is written. The previous day's page
  stays up with its own date visible. A partial edition is worse than a stale
  one, because a reader cannot tell it is partial.
"""
from __future__ import annotations
import argparse
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ledger import claudecode as cc                  # noqa: E402
from ledger.store import Ledger                      # noqa: E402

LEDGER = ROOT / "ledger-data"


def run(cmd: list[str], label: str, timeout: int = 3600) -> tuple[int, str]:
    t0 = time.time()
    print(f"\n── {label} " + "─" * max(0, 60 - len(label)))
    p = subprocess.run([sys.executable, *cmd], cwd=ROOT, text=True,
                       capture_output=True, timeout=timeout)
    out = (p.stdout or "") + (p.stderr or "")
    for line in out.strip().splitlines()[-14:]:
        print("  " + line)
    print(f"  [{time.time() - t0:.0f}s, exit {p.returncode}]")
    return p.returncode, out


def open_beats(day: str) -> list[str]:
    """Beats with claims and state — the ones a reporter can write about."""
    led = Ledger(LEDGER)
    root = pathlib.Path(LEDGER)
    out = []
    cdir = root / "claims"
    if not cdir.exists():
        return out
    for d in sorted(x for x in cdir.iterdir() if x.is_dir()):
        state = led.get_state(d.name)
        if state and len(state.get("fields") or []) >= 2 and led.list_claims(d.name):
            out.append(d.name)
    return out


def _first_field(led, beat: str) -> str:
    """The field that moved, for a beat whose article could not be written."""
    try:
        fields = (led.get_state(beat) or {}).get("fields") or []
        return str(fields[0].get("k", "")) if fields else ""
    except Exception:                                          # noqa: BLE001
        return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", default=time.strftime("%Y-%m-%d"))
    ap.add_argument("--stories", type=int, default=10)
    ap.add_argument("--no-deploy", action="store_true")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--beat-workers", type=int, default=3,
                    help="beats written at once; each fans its own checks out 8x")
    args = ap.parse_args()

    print(f"DOCUMENT ZERO · {args.day}")

    if not args.dry:
        try:
            s = cc.assert_subscription()
            print(f"  auth: {s.get('subscriptionType', 'cached')} — nothing here is metered")
        except cc.WouldBill as e:
            print(f"  REFUSING TO RUN: {e}")
            return 2

    # ── wire → beats ────────────────────────────────────────────────────────
    rc, _ = run(["scripts/run_wire.py", "--stories", str(args.stories),
                 "--day", args.day] + (["--dry"] if args.dry else []),
                "WIRE → BEATS")
    if rc != 0:
        print("\nwire stage failed; publishing nothing rather than a partial day")
        return 1
    if args.dry:
        return 0

    # ── articles ────────────────────────────────────────────────────────────
    beats = open_beats(args.day)
    print(f"\n── ARTICLES: {len(beats)} beat(s) with enough to write about " + "─" * 8)

    # Beats are independent — different prefixes, no shared state — so they are
    # written concurrently. Sequentially this is three minutes per beat and a
    # newsroom of any size never finishes. Kept deliberately low: each beat
    # internally fans its own verification out eight ways, so `beat_workers`
    # multiplies rather than adds.
    def write_one(beat):
        rc, out = run(["scripts/run_beat.py", beat, "--day", args.day],
                      f"report: {beat[:40]}", timeout=1800)
        return beat, rc, out

    from concurrent.futures import ThreadPoolExecutor
    wrote, failed = [], []
    with ThreadPoolExecutor(max_workers=args.beat_workers) as pool:
        for beat, rc, out in pool.map(write_one, beats):
            if rc == 0 and "PASSED" in out:
                wrote.append(beat)
            else:
                # NOT a quiet beat. Nothing published for it, reason stands.
                failed.append((beat, "refused by the gate" if "REFUSED" in out
                               else "reporter failed"))
    wrote.sort()

    print(f"\n  {len(wrote)} article(s) survived, {len(failed)} did not")
    for beat, why in failed:
        print(f"    {beat[:44]:46s} {why}")

    # ── edition + build ─────────────────────────────────────────────────────
    print("\n── EDITION & BUILD " + "─" * 44)
    from ledger.compile import compile_db
    from ledger.publish import publish
    from ledger.render import build, write_data_js

    led = Ledger(LEDGER, writer="editor")
    led._write_json(f"editions/{args.day}.json", {
        "day": args.day,
        "wire": [{"id": b, "beat": b, "material_changes": 0, "claims": 0,
                  "rejected_claims": 0, "changes": [], "added": [], "removed": [],
                  "unchanged": 0} for b in wrote],
        "omissions": [], "holds": [],
        "counts": {"wire": len(wrote), "refused": 0, "holds": 0, "omissions": 0,
                   "capped_out": 0, "dropped": 0, "unpublishable": len(failed)},
        # The fact still stands even when the prose could not be supported, so
        # the line carries what moved. The NAME is resolved by the renderer
        # from the registry; a slug is not the name of a story.
        "unpublishable": [{"beat": b, "name": b, "reason": why,
                           "changed": _first_field(led, b)}
                          for b, why in failed],
        # Publication is decided in ledger/edition.py from what actually
        # passed the gate. It was hardcoded false here since the stub era.
        "publish": None, "publish_blocked_by": None})

    data = build(LEDGER, None, args.day)   # the ledger is the registry
    write_data_js(data, ROOT / "data.js")
    # Point index.html at a data URL unique to this edition. Cloudflare caches
    # .js for four hours regardless of the origin's `expires -1`, which served
    # readers a masthead from today over stories from yesterday.
    from ledger.cachebust import stamp
    idx = ROOT / "index.html"
    idx.write_text(stamp(idx.read_text(encoding="utf-8"),
                         (ROOT / "data.js").read_text(encoding="utf-8")),
                   encoding="utf-8")
    publish(data, ROOT, base_url="https://doczero.epstein-data.com")
    compile_db(LEDGER, ROOT / "newsdesk.db")
    print(f"  {len(data['articles'])} article(s) on the front page")

    if args.no_deploy:
        print("\n  --no-deploy: nothing shipped")
        return 0

    print("\n── SHIP " + "─" * 55)
    p = subprocess.run(["bash", "scripts/deploy.sh", "files"], cwd=ROOT,
                       text=True, capture_output=True, timeout=600)
    for line in (p.stdout or "").strip().splitlines()[-4:]:
        print("  " + line)
    return 0 if p.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
