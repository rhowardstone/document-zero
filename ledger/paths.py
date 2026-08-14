"""Path construction and the write-partition rule.

Every writer owns a set of path prefixes and may write nothing outside them.
This is what allows every agent to push directly to main with no locking and no
merge resolution: two writers never touch the same file.

Pure functions. No I/O.
"""
from __future__ import annotations

SOURCES = "sources"
CLAIMS = "claims"
BEATS = "beats"
EDITIONS = "editions"
SHARED = ("questions", "triggers", "contradictions", "editions", "_index")


class PartitionError(Exception):
    """A writer attempted to write outside the prefixes it owns."""


def source_path(day: str, sha256: str) -> str:
    return f"{SOURCES}/{day}/{sha256}.json"


def claim_path(beat_id: str, claim_id: str) -> str:
    return f"{CLAIMS}/{beat_id}/{claim_id}.json"


def beat_state_path(beat_id: str) -> str:
    return f"{BEATS}/{beat_id}/state.json"


def beat_history_path(beat_id: str) -> str:
    return f"{BEATS}/{beat_id}/history.jsonl"


def beat_meta_path(beat_id: str) -> str:
    return f"{BEATS}/{beat_id}/meta.json"


def edition_path(day: str) -> str:
    return f"{EDITIONS}/{day}.json"


def owned_prefixes(writer: str) -> tuple[str, ...]:
    """Prefixes this writer may write. The trailing slash is significant: it is
    what stops beat 'fed' from owning 'federal-policing'."""
    if writer == "ingest":
        return (f"{SOURCES}/",)
    if writer == "editor":
        return tuple(f"{s}/" for s in SHARED)
    if writer.startswith("beat:"):
        beat_id = writer[5:]
        if not beat_id:
            return ()
        return (f"{BEATS}/{beat_id}/", f"{CLAIMS}/{beat_id}/")
    return ()


def owns_path(writer: str, path: str) -> bool:
    return any(path.startswith(p) for p in owned_prefixes(writer))


def assert_owns(writer: str, paths) -> None:
    bad = [p for p in paths if not owns_path(writer, p)]
    if bad:
        raise PartitionError(
            f"writer {writer!r} may not write: {', '.join(sorted(bad))}. "
            f"Owned prefixes: {', '.join(owned_prefixes(writer)) or '(none)'}"
        )
