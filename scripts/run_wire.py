"""Wire -> clusters -> opened beats with claims. The missing middle.

    python3 scripts/run_wire.py --stories 8
    python3 scripts/run_wire.py --stories 8 --dry    # cluster only, no agents

Free: the wire and the clustering cost nothing, and every agent call runs on the
operator's Claude Code subscription, verified before anything starts.

One agent call per candidate story does the reading once: it names the story,
names the state fields the beat test needs, and extracts claims with verbatim
quotes. The beat test then decides — and a rejection is recorded with its reason,
so the ledger shows what was considered rather than only what was covered.
"""
from __future__ import annotations
import argparse
import json
import pathlib
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from ledger import claudecode as cc          # noqa: E402
from ledger import continuity, desk, emerge, fulltext, history, scout, wire  # noqa: E402
from ledger.schema import SchemaError        # noqa: E402
from ledger.sourcetype import classify       # noqa: E402
from ledger.store import Ledger              # noqa: E402

LEDGER = "/mnt/d/Newsdesk/ledger-data"

SYSTEM = (
    "You are a news desk assistant reading a cluster of wire reports. You are "
    "precise and you do not embellish. When you cannot support something with a "
    "verbatim quote, you leave it out rather than paraphrasing it into "
    "existence. When a story has no changeable state you say so plainly instead "
    "of inventing fields to satisfy a schema."
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stories", type=int, default=8)
    ap.add_argument("--day", default=time.strftime("%Y-%m-%d"))
    ap.add_argument("--ledger", default=LEDGER)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    print("WIRE      fetching (free, no keys) …")
    arts = wire.fetch()
    print(f"          {len(arts)} articles from "
          f"{len({a.publisher for a in arts})} publishers")

    stories, singles = emerge.promote(emerge.cluster(arts, threshold=0.22))
    print(f"CLUSTER   {len(stories)} candidate stories, {len(singles)} singletons")

    picked = stories[:args.stories]
    for c in picked:
        print(f"          · {emerge.name(c):38s} {c.size} art · "
              f"{len(c.publishers)} pubs")
    if args.dry:
        return 0

    cc.assert_subscription()
    print("AUTH      subscription verified, nothing here is metered\n")

    led = Ledger(args.ledger)
    ing = Ledger(args.ledger, writer="ingest")

    # Fetch the actual articles. The feed carries a headline and about one
    # sentence — roughly forty words — and claims built on forty words are
    # fragments that the entailment gate then refuses. Measured on real pages:
    # 477 to 1,170 words of body text. Best effort: a page that blocks us falls
    # back to its summary, which means thinner claims, not wrong ones.
    to_fetch = [a for c in picked for a in c.articles]
    print(f"FETCHING  {len(to_fetch)} article bodies, {args.workers * 2} at a time …")
    t_fetch = time.time()
    with ThreadPoolExecutor(max_workers=args.workers * 2) as pool:
        bodies = dict(zip([a.sha256 for a in to_fetch],
                          pool.map(lambda a: fulltext.fetch(a.url), to_fetch)))
    got = [b for b in bodies.values() if b.ok]
    print(f"          {len(got)}/{len(to_fetch)} usable, "
          f"mean {sum(b.words for b in got) // max(len(got), 1)} words, "
          f"{time.time() - t_fetch:.0f}s")

    # Ingest every article of every picked cluster as a source, so claims have a
    # source_sha and the provenance join resolves.
    packs = []
    for c in picked:
        rows = []
        for a in c.articles:
            src = {"sha256": a.sha256, "url": a.url, "title": a.title,
                   "snippet": a.summary, "source_name": a.publisher,
                   "source_type": classify(a.url, a.publisher),
                   "published_at": a.published_at, "first_seen": a.published_at,
                   "candidate_beats": []}
            try:
                ing.put_source(args.day, src)
            except FileExistsError:
                pass
            body = bodies.get(a.sha256)
            if body is not None and body.ok:
                src["full_text"] = body.text
            rows.append({**src, "publisher": a.publisher, "summary": a.summary,
                         "full_text": src.get("full_text", "")})
        packs.append((emerge.name(c), c, rows))

    def read_cluster(pack):
        label, cluster, rows = pack
        try:
            reply = cc.run(desk.brief(label, rows, args.day), as_json=True,
                           allowed_tools=[], system_append=SYSTEM, timeout=420)
            return pack, desk.parse(reply, rows), None
        except Exception as e:                              # noqa: BLE001
            return pack, None, f"{type(e).__name__}: {e}"

    print(f"READING   {len(packs)} clusters, {args.workers} at a time …")
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(read_cluster, packs))
    print(f"          {time.time() - t0:.0f}s\n")

    opened, rejected, taken = [], [], set()
    editor = Ledger(args.ledger, writer="scout")

    # Signatures of every beat the ledger already holds. A story the desk names
    # differently today is still the same beat, and without this it becomes a
    # second one — six beats for three stories, compounding daily until nothing
    # has any history and persistent state is dead.
    existing_slugs = [d.name for d in (pathlib.Path(args.ledger) / "claims").iterdir()
                      if d.is_dir()] if (pathlib.Path(args.ledger) / "claims").exists() else []
    existing = continuity.signatures_for(led, existing_slugs)

    for (label, cluster, rows), out, err in results:
        if err:
            print(f"  {label[:34]:36s} FAILED  {err[:60]}")
            continue

        name = out["name"] or label

        # Does this continue a beat we already have?
        sig = continuity.signature(name, *[c["claim_text"] for c in out["claims"]])
        cont_slug, cont_score = continuity.match(sig, existing)

        prop = scout.propose_from_cluster(cluster, name=name, taken=taken)
        if cont_slug:
            prop.slug = cont_slug
            print(f"  {name[:32]:34s} CONTINUES {cont_slug[:34]} ({cont_score:.2f})")
        prop.state_fields = [f["k"] for f in out["state_fields"]]

        # How long has this actually been running? An RSS wire carries one to
        # three days, so its own span always fails the five-day test and nothing
        # could ever open. GDELT knows the real answer and is free.
        q = history.query_for(name)
        h = history.span(q)
        if h.found and h.days > prop.span_days:
            prop.span_days = h.days
        ok, why = scout.beat_test(prop, span_known=h.found)
        if h.found:
            why += f" (GDELT: {h.distinct_days} days of coverage over {h.days}d)"
        elif h.error:
            why += f" [{h.error}]"

        editor._write_json(f"proposals/{args.day}-{prop.slug}.json",
                           {**prop.as_record(ok, why),
                            "claims_found": len(out["claims"]),
                            "dropped": [{"claim": c, "why": w} for c, w in out["dropped"]],
                            "no_state_reason": out["no_state_reason"]})

        drop_note = f", {len(out['dropped'])} claim(s) dropped" if out["dropped"] else ""
        if not ok:
            deferred = "span unknown" in why
            rejected.append((name, why))
            label = "DEFERRED" if deferred else "REJECTED"
            print(f"  {name[:32]:34s} {label}  {why[:70]}{drop_note}")
            continue
        if not out["claims"]:
            rejected.append((name, "no claim survived quote verification"))
            print(f"  {name[:34]:36s} REJECTED  no claim survived quote check")
            continue

        taken.add(prop.slug)
        beat = Ledger(args.ledger, writer=f"beat:{prop.slug}")
        written = 0
        for i, c in enumerate(out["claims"]):
            try:
                beat.put_claim({
                    **c, "id": f"{prop.slug}-{args.day}-{i:02d}", "beat": prop.slug,
                    "extracted_by": "claude-code/desk",
                    "extracted_at": f"{args.day}T00:00:00Z"})
                written += 1
            except (SchemaError, FileExistsError):
                pass

        if written >= 2 and len(out["state_fields"]) >= 2:
            beat.put_state(prop.slug, {
                "beat": prop.slug, "as_of": args.day,
                "fields": [{"k": f["k"], "v": str(f.get("v", "")), "since": args.day,
                            "claims": [f"{prop.slug}-{args.day}-00"]}
                           for f in out["state_fields"]]},
                [c["claim_text"] for c in out["claims"]])
            beat.append_history(prop.slug, {
                "d": args.day, "c": f"Beat opened. {why}.",
                "s": f"{written} claim(s) from {len(cluster.publishers)} newsroom(s)"})
            opened.append((prop.slug, name, written))
            print(f"  {name[:32]:34s} OPENED    {written} claims · {why[:44]}{drop_note}")
        else:
            rejected.append((name, "too little survived to establish state"))
            print(f"  {name[:34]:36s} REJECTED  too little survived{drop_note}")

    print(f"\nOPENED    {len(opened)} beat(s)")
    print(f"REJECTED  {len(rejected)}, each recorded with its reason")
    if opened:
        print("\nNext: write articles for these beats —")
        for slug, _, _ in opened:
            print(f"  python3 scripts/run_beat.py {slug} --day {args.day}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
