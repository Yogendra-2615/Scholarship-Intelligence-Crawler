import sqlite3, json
from datetime import datetime, timezone
from .config import DB_PATH

def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c=sqlite3.connect(DB_PATH)
    c.row_factory=sqlite3.Row
    return c

def init_db():
    with connect() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS scholarships(
          id INTEGER PRIMARY KEY AUTOINCREMENT, fingerprint TEXT UNIQUE, name TEXT NOT NULL,
          provider TEXT, official_source_url TEXT, application_url TEXT, source_type TEXT,
          amount TEXT, eligibility TEXT, academic_requirements TEXT, course_level TEXT,
          income_criteria TEXT, age_criteria TEXT, gender_criteria TEXT, category_criteria TEXT,
          domicile_state TEXT, institution_requirements TEXT, opening_date TEXT, closing_date TEXT,
          documents_required TEXT, selection_process TEXT, renewal_requirements TEXT,
          status TEXT, confidence_score REAL, verification_status TEXT,
          last_verified_at TEXT, last_seen_at TEXT, missing_runs INTEGER DEFAULT 0,
          evidence_json TEXT, notes TEXT
        );
        CREATE TABLE IF NOT EXISTS snapshots(
          id INTEGER PRIMARY KEY AUTOINCREMENT, scholarship_id INTEGER, captured_at TEXT,
          payload_json TEXT, source_url TEXT
        );
        CREATE TABLE IF NOT EXISTS changes(
          id INTEGER PRIMARY KEY AUTOINCREMENT, scholarship_id INTEGER, field_name TEXT,
          old_value TEXT, new_value TEXT, detected_at TEXT, source_url TEXT, evidence TEXT
        );
        CREATE TABLE IF NOT EXISTS crawl_runs(
          id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT, finished_at TEXT,
          discovered INTEGER, stored INTEGER, errors INTEGER, log TEXT
        );
        CREATE TABLE IF NOT EXISTS sources(
          id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT UNIQUE, source_type TEXT,
          classification_reason TEXT, last_crawled_at TEXT, http_status INTEGER
        );
        """)
        c.commit()

def fingerprint(name, provider=""):
    import hashlib
    return hashlib.sha256((name.strip().lower()+"|"+(provider or "").strip().lower()).encode()).hexdigest()

def save_record(record):
    now=datetime.now().astimezone().isoformat(timespec="seconds")
    fp=fingerprint(record["name"],record.get("provider",""))
    fields=["name","provider","official_source_url","application_url","source_type","amount","eligibility",
    "academic_requirements","course_level","income_criteria","age_criteria","gender_criteria","category_criteria",
    "domicile_state","institution_requirements","opening_date","closing_date","documents_required",
    "selection_process","renewal_requirements","status","confidence_score","verification_status",
    "last_verified_at","evidence_json","notes"]
    values=[]
    for f in fields:
        v=record.get(f)
        if f=="evidence_json": v=json.dumps(record.get("evidence",[]),ensure_ascii=False)
        values.append(v)
    with connect() as c:
        old=c.execute("SELECT * FROM scholarships WHERE fingerprint=?",(fp,)).fetchone()
        if old:
            sid=old["id"]
            for f in ["name","provider","official_source_url","application_url","source_type","amount","eligibility",
            "academic_requirements","course_level","income_criteria","age_criteria","gender_criteria","category_criteria",
            "domicile_state","institution_requirements","opening_date","closing_date","documents_required",
            "selection_process","renewal_requirements","status","confidence_score","verification_status","evidence_json"]:
                newv=record.get(f)
                if f=="evidence_json": newv=json.dumps(record.get("evidence",[]),ensure_ascii=False)
                oldv=old[f]
                if str(oldv or "") != str(newv or ""):
                    c.execute("INSERT INTO changes(scholarship_id,field_name,old_value,new_value,detected_at,source_url,evidence) VALUES(?,?,?,?,?,?,?)",
                    (sid,f,str(oldv or ""),str(newv or ""),now,record.get("official_source_url"),json.dumps(record.get("evidence",[]),ensure_ascii=False)))
            assignments=",".join([f"{f}=?" for f in fields]+["last_seen_at=?","missing_runs=0"])
            c.execute(f"UPDATE scholarships SET {assignments} WHERE id=?",values+[now,sid])
        else:
            cols=["fingerprint"]+fields+["last_seen_at"]
            c.execute(f"INSERT INTO scholarships({','.join(cols)}) VALUES({','.join(['?']*len(cols))})",[fp]+values+[now])
            sid=c.execute("SELECT id FROM scholarships WHERE fingerprint=?",(fp,)).fetchone()["id"]
        c.execute("INSERT INTO snapshots(scholarship_id,captured_at,payload_json,source_url) VALUES(?,?,?,?)",
                  (sid,now,json.dumps(record,ensure_ascii=False),record.get("official_source_url")))
        c.commit()
        return sid

def mark_not_seen(seen_fingerprints):
    with connect() as c:
        rows=c.execute("SELECT id,fingerprint,missing_runs FROM scholarships").fetchall()
        for r in rows:
            if r["fingerprint"] not in seen_fingerprints:
                n=r["missing_runs"]+1
                status="NO_LONGER_VERIFIABLE" if n>=2 else "REVIEW_REQUIRED"
                c.execute("UPDATE scholarships SET missing_runs=?,status=?,verification_status='REVIEW REQUIRED' WHERE id=?",(n,status,r["id"]))
        c.commit()

def seed_sample():
    import json
    from .config import SAMPLE_PATH
    if not SAMPLE_PATH.exists(): return
    with open(SAMPLE_PATH,encoding="utf-8") as f: rows=json.load(f)
    for r in rows: save_record(r)

def list_records(search=""):
    with connect() as c:
        if search:
            q=f"%{search}%"
            return c.execute("""SELECT * FROM scholarships WHERE name LIKE ? OR provider LIKE ? OR eligibility LIKE ? ORDER BY name""",(q,q,q)).fetchall()
        return c.execute("SELECT * FROM scholarships ORDER BY name").fetchall()
