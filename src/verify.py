from urllib.parse import urlparse
from datetime import datetime, date
from .config import OFFICIAL_SUFFIXES, OFFICIAL_EXACT

def is_official(url):
    try:
        host=urlparse(url).hostname.lower().removeprefix("www.")
        return host in OFFICIAL_EXACT or any(host.endswith(s) for s in OFFICIAL_SUFFIXES)
    except Exception:
        return False

def classify_source(url):
    host=urlparse(url).hostname.lower() if url else ""
    if "scholarships.gov.in" in host: return "government_portal"
    if "ugc.gov.in" in host or "aicte-india.org" in host: return "regulator"
    if any(x in host for x in ["socialjustice.gov.in","tribal.nic.in","education.gov.in"]): return "ministry_department"
    if host.endswith(".ac.in") or host.endswith(".edu.in"): return "university"
    return "official_provider" if is_official(url) else "unverified"

def confidence(record, page_text, fetched_at=None):
    # Deterministic evidence rubric. No LLM-generated scores.
    score=0
    checks={}
    checks["official_domain"]=30 if is_official(record.get("official_source_url","")) else 0
    checks["title_on_page"]=20 if record.get("name","").lower() in page_text.lower() else 0
    checks["provider_evidence"]=10 if record.get("provider") and record["provider"].lower() in page_text.lower() else 0
    checks["application_route"]=10 if record.get("application_url") and is_official(record["application_url"]) else 0
    checks["deadline_evidence"]=10 if record.get("closing_date") and record["closing_date"] in page_text else 0
    checks["opening_date_evidence"]=5 if record.get("opening_date") and record["opening_date"] in page_text else 0
    checks["traceable_evidence"]=10 if len(record.get("evidence",[]))>=3 else 0
    checks["fresh_fetch"]=5 if fetched_at else 0
    score=sum(checks.values())
    return round(score,1), checks

def status_from_deadline(closing_date):
    if not closing_date: return "REVIEW_REQUIRED"
    for fmt in ("%d-%m-%Y","%Y-%m-%d"):
        try:
            d=datetime.strptime(closing_date,fmt).date(); break
        except ValueError: d=None
    if not d: return "REVIEW_REQUIRED"
    today=date.today()
    if d<today: return "EXPIRED"
    if (d-today).days<=10: return "EXPIRING_SOON"
    return "ACTIVE"
