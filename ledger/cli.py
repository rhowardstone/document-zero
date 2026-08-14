"""Entry points. None of these cost money.

  python3 -m ledger.cli compile <ledger-root> <db-path>
  python3 -m ledger.cli beats
  python3 -m ledger.cli routing <ledger-root>   # what tier-1 routing is missing
"""
from __future__ import annotations
import sys
from pathlib import Path
from .compile import compile_db
from .beats import load_beats


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(__doc__)
        return 2
    cmd = argv[0]
    if cmd == "compile":
        if len(argv) < 3:
            print("usage: compile <ledger-root> <db-path>")
            return 2
        out = compile_db(argv[1], argv[2])
        print(f"compiled {Path(argv[1])} -> {out}")
        return 0
    if cmd == "routing":
        import json
        from .tuning import analyse_routing, format_report
        root = Path(argv[1] if len(argv) > 1 else "data")
        srcs = [json.loads(f.read_text(encoding="utf-8"))
                for d in sorted((root / "sources").glob("*")) if d.is_dir()
                for f in sorted(d.glob("*.json"))]
        print(format_report(analyse_routing(srcs, load_beats("config/beats.yaml"))))
        return 0
    if cmd == "beats":
        for b in load_beats(argv[1] if len(argv) > 1 else "config/beats.yaml"):
            print(f"{b.id:14s} {b.name:45s} {','.join(b.dossiers)}")
        return 0
    print(f"unknown command: {cmd}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
