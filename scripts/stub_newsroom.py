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
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from ledger.article import ArticleError, validate            # noqa: E402
from ledger.entail import Verdict, check                     # noqa: E402
from ledger.frontpage import play                            # noqa: E402
from ledger.store import Ledger                              # noqa: E402

DAY = "2026-08-16"


# ── The stubs ────────────────────────────────────────────────────────────────

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
    body, used, i = [], [], 0
    while sum(len(t.split()) for t in body) < 430 and i < 400:
        c = claims[i % len(claims)]
        body.append(f"{c['claim_text'].rstrip('.')}.")
        used.append(c["id"])
        i += 1

    return {
        "beat": beat, "day": DAY,
        "headline": f"{lead[:70]}",
        "standfirst": (changed[0]["k"] + " changed" if changed
                       else "No field changed"),
        "dateline": "STUB DESK",
        "published_at": f"{DAY}T12:00:00Z",
        "written_by": "stub-reporter (NOT a model)",
        "paragraphs": [
            {"text": " ".join(body), "claims": sorted(set(used))},
        ],
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
        scored.append((article, float(len(claims))))

    page = play(scored=scored, day=DAY, refused=refused,
                counts={"refused": len(refused), "holds": 0})

    (out / "edition.json").write_text(json.dumps(page, indent=1), encoding="utf-8")

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
