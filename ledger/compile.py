"""Compile the git ledger into a queryable SQLite index.

No model. Fully deterministic. The database is derived: delete it and rebuild.
A corrupted database is therefore never data loss.
"""
from __future__ import annotations
import json, sqlite3
from pathlib import Path
from . import paths as P

DDL = """
drop table if exists sources;
drop table if exists source_beats;
drop table if exists claims;
drop table if exists beat_state;
drop table if exists beat_history;
create table sources(sha256 text primary key, url text, title text, source_name text,
  source_type text, published_at text, first_seen text, day text);
create table source_beats(sha256 text, beat text, score real);
create table claims(id text primary key, beat text, claim_text text, quote text,
  source_sha text, source_type text, source_url text, source_doi text, confidence real,
  confidence_justification text, tier text, extracted_by text, extracted_at text,
  verification_rounds integer, verifier_families text);
create table beat_state(beat text, as_of text, k text, v text, since text, flag text);
create table beat_history(beat text, d text, c text, s text, ord integer);
create index ix_claims_beat on claims(beat);
create index ix_claims_sha on claims(source_sha);
create index ix_state_beat on beat_state(beat);
create index ix_srcbeats on source_beats(beat);
"""


def _load(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def compile_db(root, db_path) -> Path:
    root, db_path = Path(root), Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.executescript(DDL)

    sdir = root / P.SOURCES
    if sdir.exists():
        for day in sorted(x for x in sdir.iterdir() if x.is_dir()):
            for f in sorted(day.glob("*.json")):
                s = _load(f)
                if not s:
                    continue
                con.execute("insert or replace into sources values(?,?,?,?,?,?,?,?)",
                            (s["sha256"], s.get("url"), s.get("title"), s.get("source_name"),
                             s.get("source_type"), s.get("published_at"), s.get("first_seen"),
                             day.name))
                for cb in s.get("candidate_beats", []):
                    con.execute("insert into source_beats values(?,?,?)",
                                (s["sha256"], cb.get("beat"), cb.get("score")))

    cdir = root / P.CLAIMS
    if cdir.exists():
        for bd in sorted(x for x in cdir.iterdir() if x.is_dir()):
            for f in sorted(bd.glob("*.json")):
                c = _load(f)
                if not c:
                    continue
                con.execute(
                    "insert or replace into claims values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (c["id"], c.get("beat"), c.get("claim_text"), c.get("quote"),
                     c.get("source_sha"), c.get("source_type"), c.get("source_url"),
                     c.get("source_doi"), c.get("confidence"),
                     c.get("confidence_justification"), c.get("tier"),
                     c.get("extracted_by"), c.get("extracted_at"),
                     c.get("verification_rounds"),
                     ",".join(c.get("verifier_families") or []) or None))

    bdir = root / P.BEATS
    if bdir.exists():
        for bd in sorted(x for x in bdir.iterdir() if x.is_dir()):
            st = _load(bd / "state.json")
            if st:
                for fld in st.get("fields", []):
                    con.execute("insert into beat_state values(?,?,?,?,?,?)",
                                (st["beat"], st.get("as_of"), fld.get("k"), fld.get("v"),
                                 fld.get("since"), fld.get("flag")))
            hp = bd / "history.jsonl"
            if hp.exists():
                for i, line in enumerate(hp.read_text(encoding="utf-8").splitlines()):
                    if not line.strip():
                        continue
                    r = json.loads(line)
                    con.execute("insert into beat_history values(?,?,?,?,?)",
                                (bd.name, r.get("d"), r.get("c"), r.get("s"), i))
    con.commit()
    con.close()
    return db_path
