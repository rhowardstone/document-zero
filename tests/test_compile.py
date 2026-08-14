import sqlite3, pytest
from ledger.store import Ledger
from ledger.compile import compile_db

@pytest.fixture
def populated(tmp_path):
    led=Ledger(tmp_path/"data")
    led.put_source("2026-08-14",{"sha256":"a"*64,"url":"https://x","title":"T","source_name":"E",
        "source_type":"news","published_at":"2026-08-14T03:00:00Z","first_seen":"2026-08-14T04:00:00Z",
        "candidate_beats":[{"beat":"hormuz","score":0.5}]})
    led.put_state("hormuz",{"beat":"hormuz","as_of":"2026-08-14","fields":[
        {"k":"Blockade","v":"In force","since":"Aug"},{"k":"Transit","v":"Near standstill","since":"14 Aug"}]})
    led.append_history("hormuz",{"d":"2026-08-14","c":"Transit changed","s":"wire"})
    led.put_claim({"id":"hormuz-1","beat":"hormuz","claim_text":"X","quote":"x",
        "source_type":"news","source_url":"https://x","confidence":0.6,
        "confidence_justification":"news ceiling","tier":"documented_fact",
        "extracted_by":"t","extracted_at":"2026-08-14T05:00:00Z"})
    return led, tmp_path/"out.db"

def test_compile_creates_all_tables(populated):
    led,db=populated; compile_db(led.root,db)
    names={r[0] for r in sqlite3.connect(db).execute("select name from sqlite_master where type='table'")}
    assert {"sources","claims","beat_state","beat_history"} <= names

def test_state_fields_become_queryable_rows(populated):
    led,db=populated; compile_db(led.root,db)
    rows=sqlite3.connect(db).execute("select k,v from beat_state where beat='hormuz' order by k").fetchall()
    assert rows==[("Blockade","In force"),("Transit","Near standstill")]

def test_claims_carry_confidence_and_tier(populated):
    led,db=populated; compile_db(led.root,db)
    assert sqlite3.connect(db).execute("select confidence,tier from claims where id='hormuz-1'").fetchone()==(0.6,"documented_fact")

def test_compile_is_idempotent(populated):
    led,db=populated; compile_db(led.root,db); compile_db(led.root,db)
    assert sqlite3.connect(db).execute("select count(*) from claims").fetchone()[0]==1

def test_compile_on_empty_tree_succeeds(tmp_path):
    compile_db(tmp_path/"empty", tmp_path/"e.db")
    assert sqlite3.connect(tmp_path/"e.db").execute("select count(*) from sources").fetchone()[0]==0
