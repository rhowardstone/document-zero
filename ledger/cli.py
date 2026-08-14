"""Entry points.

  python3 -m ledger.cli compile <ledger-root> <db-path>
  python3 -m ledger.cli beats
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
    if cmd == "beats":
        for b in load_beats(argv[1] if len(argv) > 1 else "config/beats.yaml"):
            print(f"{b.id:14s} {b.name:45s} {','.join(b.dossiers)}")
        return 0
    print(f"unknown command: {cmd}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
