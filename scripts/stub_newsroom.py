"""Run the whole newsroom with no model, no key, no network and no cost.

This exists so the pipeline can be watched end to end before a single agent is
scheduled, and so it stays watchable forever. Every place a Claude Code instance
will eventually sit is a deterministic stub here:

    reporter  -> assembles a paragraph from the claim texts it was given
    verifier  -> the strict word-coverage check from tests/test_entail_adversarial

The stub reporter is deliberately, obviously mechanical. It must never be
mistaken for the real thing, so it writes in a flat register and says what it
is. What it demonstrates is the SHAPE: a dated front page with a lead story, an
entailment gate that actually fires, refused articles degrading to one-line
entries, and a page that can say "nothing survived today".

Usage:
    python3 scripts/stub_newsroom.py --out /tmp/dz
    python3 scripts/stub_newsroom.py --out /tmp/dz --offline   # no wire fetch
"""
from __future__ import annotations
import argparse
import json
import re
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from ledger.article import ArticleError, validate            # noqa: E402
from ledger.entail import Verdict, check                     # noqa: E402
from ledger.frontpage import play                            # noqa: E402
from ledger.store import Ledger                              # noqa: E402

DAY = "2026-08-16"


# ── The stubs ────────────────────────────────────────────────────────────────

def _headline(text: str) -> str:
    """The first clause, capped. A stub cannot write a headline; it can at least
    stop at a natural break instead of mid-thought."""
    first = re.split(r"\s+(?:and|but|which|after|while|because)\s+|[,;:]", text, 1)[0]
    return _trim(first if len(first.split()) >= 5 else text, 78)


def _trim(text: str, n: int) -> str:
    """Never cut mid-word: a truncated headline reads as a broken system."""
    t = text.strip()
    if len(t) <= n:
        return t
    cut = t[:n]
    return (cut[:cut.rfind(" ")] if " " in cut else cut).rstrip(",;:")


def stub_reporter(beat: str, claims: list, changed: list) -> dict:
    """Stand-in for a Claude Code reporter.

    Writes flat, mechanical prose out of the claim texts. It pads to clear the
    400-word floor because the floor is a real editorial rule and the stub has
    to satisfy the same schema the real reporter will.
    """
    if not claims:
        raise ArticleError("no claims: nothing to report")

    lead = claims[0]["claim_text"].rstrip(".")

    # Build the body ONLY out of claim text, cycling through the claims until
    # the word floor is met. The first version padded with generic filler and
    # the entailment gate refused 22 of 29 sentences — correctly, because
    # nothing supported them. That is worth keeping in mind: the word floor and
    # the gate together mean a beat cannot pad its way to an article. Thin
    # evidence produces a one-line entry, which is the right outcome.
    # Each claim ONCE. The first version cycled them to reach the word floor,
    # which produced a lead story that said the same two sentences three times.
    # Cycling is padding wearing a citation: every sentence is entailed, so the
    # gate passes it, and the result is unreadable. A reporter with two claims
    # should write short and be REJECTED, so the beat degrades to a line — and
    # that is what happens now.
    # Each claim once, and only as many as fit the window. Choosing what to
    # include is the one editorial act the stub performs, and it is the same one
    # a real reporter performs — it just does it by counting instead of judging.
    # A beat with too little to say still falls short of the floor and degrades
    # to a line, which is the behaviour worth demonstrating.
    body, used, total = [], [], 0
    for c in claims:
        sentence = f"{c['claim_text'].rstrip('.')}."
        n = len(sentence.split())
        if total + n > 760:
            break
        body.append(sentence)
        used.append(c["id"])
        total += n

    # Break into paragraphs. One wall of text is not an article, and the
    # renderer needs somewhere to breathe.
    paras, chunk, chunk_ids = [], [], []
    for sentence, cid in zip(body, used):
        chunk.append(sentence)
        chunk_ids.append(cid)
        if len(chunk) >= 4:
            paras.append({"text": " ".join(chunk), "claims": sorted(set(chunk_ids))})
            chunk, chunk_ids = [], []
    if chunk:
        paras.append({"text": " ".join(chunk), "claims": sorted(set(chunk_ids))})

    return {
        "beat": beat, "day": DAY,
        # Cut at the first clause boundary, not mid-sentence: a headline that
        # trails off reads as a broken system rather than a terse one.
        "headline": _headline(lead),
        "standfirst": (changed[0]["k"] + " changed" if changed
                       else "No field changed"),
        "dateline": "STUB DESK",
        "published_at": f"{DAY}T12:00:00Z",
        "written_by": "stub-reporter (NOT a model)",
        "paragraphs": paras,
        "changed": changed,
    }


def strict_verifier(sentence: str, claims: list) -> Verdict:
    """Entailed only if the sentence's content words are covered by its claims."""
    blob = " ".join(c["claim_text"].lower() for c in claims)
    words = [w.strip(".,;:'\"()") for w in sentence.lower().split()]
    missing = [w for w in words if len(w) > 6 and w not in blob]
    return Verdict(not missing, f"unsupported: {missing[:3]}" if missing else "ok")


def lenient_verifier(_s, _c) -> Verdict:
    return Verdict(True, "stub verifier: not a real check")


# ── The run ──────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--ledger", default="/mnt/d/Newsdesk/ledger-data")
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    led = Ledger(args.ledger)
    beats = []
    root = pathlib.Path(args.ledger)
    claims_dir = root / "claims"
    if claims_dir.exists():
        beats = sorted(d.name for d in claims_dir.iterdir() if d.is_dir())

    print(f"LEDGER   {args.ledger}: {len(beats)} beat(s) with claims")

    scored, refused = [], []
    for beat in beats:
        claims = led.list_claims(beat)
        state = led.get_state(beat) or {}
        changed = [{"k": f.get("k"), "from": "", "to": f.get("v"),
                    "since": f.get("since", "")}
                   for f in (state.get("fields") or [])[:3]]
        if not claims:
            continue

        try:
            article = validate(stub_reporter(beat, claims, changed))
        except ArticleError as e:
            print(f"  {beat:14s} REJECTED at schema: {e}")
            refused.append({"beat": beat, "name": beat,
                            "changed": changed[0]["k"] if changed else "",
                            "reason": f"schema: {e}"})
            continue

        result = check(article, claims, verifiers=[strict_verifier, lenient_verifier])
        if not result.passed:
            print(f"  {beat:14s} REFUSED by the gate: "
                  f"{len(result.refusals)}/{result.checked} sentence(s) unentailed")
            refused.append({"beat": beat, "name": beat,
                            "changed": changed[0]["k"] if changed else "",
                            "reason": f"{len(result.refusals)} unentailed sentence(s)"})
            continue

        print(f"  {beat:14s} PASSED  {article.word_count} words, "
              f"{result.checked} sentence(s) checked")
        # Store it under the beat that wrote it, so the renderer can find it and
        # the write-partition rule covers it with no extra machinery.
        Ledger(args.ledger, writer=f"beat:{beat}").put_article(article)
        scored.append((article, float(len(claims))))

    page = play(scored=scored, day=DAY, refused=refused,
                counts={"unpublishable": len(refused), "holds": 0})

    (out / "edition.json").write_text(json.dumps(page, indent=1), encoding="utf-8")

    # The editor's edition: which beats reached the wire. The renderer reads
    # this to decide what publishes, so an article from a held beat cannot leak.
    Ledger(args.ledger, writer="editor")._write_json(f"editions/{DAY}.json", {
        "day": DAY,
        "wire": [{"id": a.beat, "beat": a.beat, "material_changes": len(a.changed),
                  "claims": 0, "rejected_claims": 0, "changes": [], "added": [],
                  "removed": [], "unchanged": 0} for a, _ in scored],
        "omissions": [], "holds": [],
        # `refused` means a SAFETY gate fired. An article that failed the
        # schema or the entailment gate is `unpublishable` — a different thing,
        # and labelling it as a refusal tells the reader someone was protected
        # when in fact the writing simply could not be supported.
        "counts": {"wire": len(scored), "refused": 0, "holds": 0,
                   "unpublishable": len(refused),
                   "omissions": 0, "capped_out": 0, "dropped": 0},
        "unpublishable": refused,
        "publish": False, "publish_blocked_by": "dry_run"})

    print()
    print(f"FRONT PAGE  {page['date']}")
    if page["nothing_survived"]:
        print("  NOTHING SURVIVED — the page says so rather than going quiet.")
    else:
        print(f"  LEAD       {page['lead']['headline'][:66]}")
        print(f"             {page['lead']['word_count']} words · "
              f"{page['lead']['dateline']} · {page['lead']['published_at']}")
        for a in page["secondary"]:
            print(f"  SECONDARY  {a['headline'][:66]}")
    for line in page["also_moving"]:
        print(f"  ALSO       {line['name']}: {line['reason']}")
    print(f"  DID NOT PUBLISH  {page['did_not_publish']}")
    print(f"\nwrote {out / 'edition.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
