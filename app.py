import json, subprocess, sys
import pandas as pd
import streamlit as st
from src.db import init_db, seed_sample, list_records, connect
from src.config import ROOT

st.set_page_config(page_title="Scholarship Intelligence",page_icon="🎓",layout="wide")
init_db()
seed_sample()
st.title("🎓 Scholarship Intelligence")
st.caption("Discover → Crawl → Extract → Verify → Score → Store → Update")
with connect() as c:
    total=c.execute("SELECT COUNT(*) n FROM scholarships").fetchone()["n"]
    verified=c.execute("SELECT COUNT(*) n FROM scholarships WHERE verification_status='VERIFIED'").fetchone()["n"]
    review=c.execute("SELECT COUNT(*) n FROM scholarships WHERE verification_status!='VERIFIED'").fetchone()["n"]
    active=c.execute("SELECT COUNT(*) n FROM scholarships WHERE status IN ('ACTIVE','EXPIRING_SOON')").fetchone()["n"]
    expired=c.execute("SELECT COUNT(*) n FROM scholarships WHERE status='EXPIRED'").fetchone()["n"]
    avg=c.execute("SELECT AVG(confidence_score) n FROM scholarships").fetchone()["n"] or 0
    changes=c.execute("SELECT COUNT(*) n FROM changes").fetchone()["n"]
    recent=c.execute("SELECT COUNT(*) n FROM changes WHERE date(detected_at)=date('now','localtime')").fetchone()["n"]

cols=st.columns(7)
for col,(label,val) in zip(cols,[("Discovered",total),("Verified",verified),("Review required",review),("Active",active),("Expired",expired),("Avg confidence",f"{avg:.1f}%"),("Changes",changes)]):
    col.metric(label,val)

st.divider()
left,right=st.columns([1,3])
with left:
    st.subheader("Crawler")
    st.write("Run a fresh crawl of seed sources and discovered official URLs.")
    if st.button("▶ Run crawler now",type="primary",use_container_width=True):
        with st.spinner("Crawling official sources..."):
            result=subprocess.run([sys.executable,"-m","src.run_crawler"],cwd=ROOT,capture_output=True,text=True)
        if result.returncode==0:
            st.success("Crawl finished.")
            st.code(result.stdout[-4000:])
        else:
            st.error("Crawler returned an error.")
            st.code(result.stderr[-4000:])
    if st.button("Load sample snapshot",use_container_width=True):
        seed_sample(); st.success("Official NSP snapshot loaded.")
    st.caption("A recurring run is available with: python scheduler.py")
    st.metric("Changes detected",changes)
with right:
    st.subheader("Scholarship records")
    query=st.text_input("Search by scholarship, provider or eligibility")
    rows=list_records(query)
    if rows:
        df=pd.DataFrame([dict(r) for r in rows])
        show=["name","provider","amount","closing_date","status","confidence_score","verification_status","last_verified_at"]
        st.dataframe(df[show],use_container_width=True,hide_index=True)
        selected=st.selectbox("Open scholarship details",[""]+[f'{r["id"]} — {r["name"]}' for r in rows])
        if selected:
            sid=int(selected.split(" — ")[0])
            with connect() as c:
                r=dict(c.execute("SELECT * FROM scholarships WHERE id=?",(sid,)).fetchone())
                hist=c.execute("SELECT field_name,old_value,new_value,detected_at,source_url,evidence FROM changes WHERE scholarship_id=? ORDER BY id DESC",(sid,)).fetchall()
                snaps=c.execute("SELECT captured_at,source_url,payload_json FROM snapshots WHERE scholarship_id=? ORDER BY id DESC LIMIT 5",(sid,)).fetchall()
            st.markdown(f"### {r['name']}")
            detail_cols=st.columns(2)
            for i,(k,v) in enumerate(r.items()):
                if k in ["id","fingerprint","evidence_json","notes"]: continue
                detail_cols[i%2].write(f"**{k.replace('_',' ').title()}**: {v if v not in (None,'') else 'Not specified'}")
            st.markdown("#### Why this confidence score?")
            try:
                evidence=json.loads(r["evidence_json"] or "[]")
                st.json(evidence)
            except Exception: st.write("No evidence stored.")
            st.markdown("#### Change history")
            if hist: st.dataframe(pd.DataFrame([dict(x) for x in hist]),use_container_width=True,hide_index=True)
            else: st.info("No changes recorded yet.")
            st.markdown("#### Recent crawl snapshots")
            if snaps:
                for s in snaps: st.write(s["captured_at"],s["source_url"])
    else: st.info("No matching records.")
st.divider()
st.subheader("Recent crawler runs")
with connect() as c:
    runs=c.execute("SELECT * FROM crawl_runs ORDER BY id DESC LIMIT 10").fetchall()
if runs: st.dataframe(pd.DataFrame([dict(x) for x in runs]),use_container_width=True,hide_index=True)
else: st.info("No live crawl run recorded yet. Sample records are an official NSP snapshot, not a live crawl.")
