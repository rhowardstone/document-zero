"""The only module that touches the filesystem.

Sources are immutable: writing one that already exists is an error, not an update.
State is overwritten. History is append-only. Every write is validated first and
checked against the writer's partition, so an invalid or out-of-partition write
never reaches disk.
"""
from __future__ import annotations
import json, os
from pathlib import Path
from . import paths as P
from .schema import validate_source, validate_claim, validate_beat_state


class Ledger:
    def __init__(self, root, writer: str | None = None):
        self.root = Path(root)
        self.writer = writer
        self.written: list[str] = []

    # ---- internals -------------------------------------------------
    def _abs(self, rel: str) -> Path:
        return self.root / rel

    def _guard(self, rel: str) -> None:
        if self.writer:
            P.assert_owns(self.writer, [rel])

    def _write_json(self, rel: str, obj, exclusive: bool = False) -> str:
        self._guard(rel)
        p = self._abs(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        if exclusive and p.exists():
            raise FileExistsError(f"{rel} already exists; sources are immutable")
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, p)
        self.written.append(rel)
        return rel

    def _read_json(self, rel: str):
        p = self._abs(rel)
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    # ---- sources ---------------------------------------------------
    def put_source(self, day: str, source: dict) -> str:
        validate_source(source)
        return self._write_json(P.source_path(day, source["sha256"]), source, exclusive=True)

    def get_source(self, day: str, sha: str):
        return self._read_json(P.source_path(day, sha))

    def list_sources(self, day: str) -> list[str]:
        d = self._abs(f"{P.SOURCES}/{day}")
        return sorted(f.stem for f in d.glob("*.json")) if d.exists() else []

    # ---- claims ----------------------------------------------------
    def put_claim(self, claim: dict) -> str:
        """Claims are immutable. Re-writing an identical claim is a no-op; writing
        DIFFERENT content to an existing claim id is an error, because a ledger
        that lets a stored claim change is not a ledger."""
        validate_claim(claim)
        rel = P.claim_path(claim["beat"], claim["id"])
        existing = self._read_json(rel)
        if existing is not None:
            if existing == claim:
                return rel
            raise FileExistsError(
                f"{rel} exists with different content; claims are immutable. "
                "Supersede it with a new claim instead of rewriting it.")
        return self._write_json(rel, claim)

    def list_claims(self, beat_id: str) -> list[dict]:
        d = self._abs(f"{P.CLAIMS}/{beat_id}")
        if not d.exists():
            return []
        return [json.loads(f.read_text(encoding="utf-8")) for f in sorted(d.glob("*.json"))]

    # ---- beat state and history ------------------------------------
    def put_state(self, beat_id: str, state: dict) -> str:
        validate_beat_state(state)
        return self._write_json(P.beat_state_path(beat_id), state)

    def get_state(self, beat_id: str):
        return self._read_json(P.beat_state_path(beat_id))

    def append_history(self, beat_id: str, row: dict) -> str:
        rel = P.beat_history_path(beat_id)
        self._guard(rel)
        p = self._abs(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        self.written.append(rel)
        return rel

    def read_history(self, beat_id: str) -> list[dict]:
        p = self._abs(P.beat_history_path(beat_id))
        if not p.exists():
            return []
        return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]

    def list_beats(self) -> list[str]:
        d = self._abs(P.BEATS)
        return sorted(x.name for x in d.iterdir() if x.is_dir()) if d.exists() else []
