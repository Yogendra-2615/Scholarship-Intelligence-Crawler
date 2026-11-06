import re, time, json
from datetime import datetime
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from .config import SEED_SOURCES, USER_AGENT, TIMEOUT, MAX_DISCOVERED_URLS
from .db import init_db, save_record, mark_not_seen, connect
from .verify import is_official, classify_source, confidence, status_from_deadline

SCHOLARSHIP_WORDS=re.compile(r"(scholarship|fellowship|financial assistance|stipend)",re.I)
DATE_RE=re.compile(r"(\\d{2}-\\d{2}-\\d{4})")
HEADERS={"User-Agent":USER_AGENT}

def fetch(url):
    r=requests.get(url,headers=HEADERS,timeout=TIMEOUT)
    r.raise_for_status()
    return r.text, r.status_code

def discover_urls():
    found={s["url"]:s for s in SEED_SOURCES}
    # Open web discovery: DuckDuckGo HTML is used only to discover URLs.
    queries=[
      'site:gov.in scholarship students India 2026',
      'site:nic.in scholarship India students',
      'site:ac.in scholarship financial aid students India',
      'site:org.in scholarship India official foundation'
    ]
    for q in queries:
        try:
            html,_=fetch("https://html.duckduckgo.com/html/?q="+requests.utils.quote(q))
            soup=BeautifulSoup(html,"html.parser")
            for a in soup.select("a.result__a"):
                u=a.get("href","")
                if u.startswith("http") and is_official(u):
                    found.setdefault(u,{"url":u,"type":classify_source(u),"name":a.get_text(" ",strip=True)})
                    if len(found)>=len(SEED_SOURCES)+MAX_DISCOVERED_URLS: return list(found.values())
            time.sleep(1)
        except Exception:
            continue
    return list(found.values())

def parse_nsp(html,url):
    soup=BeautifulSoup(html,"html.parser")
    out=[]
    # NSP listing groups each scholarship heading with provider heading and the nearby scheme date text.
    for h in soup.find_all(re.compile("^h[1-6]$")):
        name=h.get_text(" ",strip=True)
        if not SCHOLARSHIP_WORDS.search(name): continue
        if len(name)<12: continue
        parent=h.parent
        context=parent.get_text(" ",strip=True) if parent else name
        # Extend to nearby parent if dates are outside the heading wrapper.
        if not DATE_RE.search(context) and parent and parent.parent:
            context=parent.parent.get_text(" ",strip=True)
        dates=DATE_RE.findall(context)
        provider="Not specified"
        prev=h.find_previous(["h2","h3","h4","h5","h6"])
        if prev:
            p=prev.get_text(" ",strip=True)
            if len(p)<100 and not SCHOLARSHIP_WORDS.search(p): provider=p
        if len(dates)>=2:
            opening,closing=dates[0],dates[1]
        elif len(dates)==1:
            opening,closing="Not specified",dates[0]
        else:
            opening,closing="Not specified","Not specified"
        out.append(make_record(name,provider,url,"https://scholarships.gov.in/",context,opening,closing,"government_portal"))
    # Remove duplicates in the same page
    dedup={}
    for r in out: dedup[(r["name"].lower(),r["provider"].lower())]=r
    return list(dedup.values())

def parse_generic(html,url):
    soup=BeautifulSoup(html,"html.parser")
    text=soup.get_text(" ",strip=True)
    out=[]
    # Candidate titles are headings/links containing scholarship terms.
    candidates=[]
    for tag in soup.find_all(["h1","h2","h3","h4","h5","a"]):
        title=tag.get_text(" ",strip=True)
        if SCHOLARSHIP_WORDS.search(title) and 12<=len(title)<=220:
            candidates.append((tag,title))
    for tag,title in candidates:
        ctx=tag.parent.get_text(" ",strip=True)[:2500] if tag.parent else title
        # Avoid interpreting unrelated page-wide dates as a scheme deadline.
        close="Not specified"; opening="Not specified"
        date_match=re.search(r"(?:last date|closing date|apply by|application.*?(?:till|by)|deadline)[^0-9]{0,30}(\\d{1,2}[/-]\\d{1,2}[/-]\\d{4})",ctx,re.I)
        if date_match: close=date_match.group(1)
        provider=urlparse(url).hostname or "Not specified"
        out.append(make_record(title,provider,url,url,ctx,opening,close,classify_source(url)))
    return out

def make_record(name,provider,source,application,context,opening,closing,stype):
    evidence=[{"field":"name","value":name,"url":source,"snippet":context[:600]}]
    if provider!="Not specified": evidence.append({"field":"provider","value":provider,"url":source,"snippet":context[:600]})
    if opening!="Not specified": evidence.append({"field":"opening_date","value":opening,"url":source,"snippet":context[:600]})
    if closing!="Not specified": evidence.append({"field":"closing_date","value":closing,"url":source,"snippet":context[:600]})
    return {"name":name,"provider":provider,"official_source_url":source,"application_url":application,
      "source_type":stype,"amount":"Not specified","eligibility":"Not specified","academic_requirements":"Not specified",
      "course_level":"Not specified","income_criteria":"Not specified","age_criteria":"Not specified",
      "gender_criteria":"Not specified","category_criteria":"Not specified","domicile_state":"Not specified",
      "institution_requirements":"Not specified","opening_date":opening,"closing_date":closing,
      "documents_required":"Not specified","selection_process":"Not specified","renewal_requirements":"Not specified",
      "evidence":evidence,"notes":"Only values directly observed in official page text are extracted."}

def run_crawl():
    init_db()
    started=datetime.now().astimezone().isoformat(timespec="seconds")
    discovered=discover_urls(); seen=set(); errors=0; stored=0; logs=[]
    for source in discovered:
        url=source["url"]
        try:
            html,code=fetch(url)
            with connect() as c:
                c.execute("INSERT INTO sources(url,source_type,classification_reason,last_crawled_at,http_status) VALUES(?,?,?,?,?) ON CONFLICT(url) DO UPDATE SET last_crawled_at=excluded.last_crawled_at,http_status=excluded.http_status",
                          (url,source.get("type",classify_source(url)),"Official domain allowlist / seed source",started,code))
            rows=parse_nsp(html,url) if "scholarships.gov.in/All-Scholarships" in url else parse_generic(html,url)
            text=BeautifulSoup(html,"html.parser").get_text(" ",strip=True)
            for r in rows:
                if not is_official(r["official_source_url"]): continue
                score,why=confidence(r,text,started)
                r["confidence_score"]=score
                r["verification_status"]="VERIFIED" if score>=95 else "REVIEW REQUIRED"
                r["status"]=status_from_deadline(r.get("closing_date"))
                r["last_verified_at"]=started
                r["evidence"].append({"field":"confidence_breakdown","value":json.dumps(why),"url":url,"snippet":"Deterministic verification rubric"})
                sid=save_record(r); stored+=1
                from .db import fingerprint
                seen.add(fingerprint(r["name"],r.get("provider","")))
            logs.append(f"OK {url}: {len(rows)} candidates")
        except Exception as e:
            errors+=1; logs.append(f"ERROR {url}: {type(e).__name__}: {e}")
    if seen: mark_not_seen(seen)
    finished=datetime.now().astimezone().isoformat(timespec="seconds")
    with connect() as c:
        c.execute("INSERT INTO crawl_runs(started_at,finished_at,discovered,stored,errors,log) VALUES(?,?,?,?,?,?)",
                  (started,finished,len(discovered),stored,errors,"\\n".join(logs)))
        c.commit()
    return {"discovered":len(discovered),"stored":stored,"errors":errors,"log":logs}
