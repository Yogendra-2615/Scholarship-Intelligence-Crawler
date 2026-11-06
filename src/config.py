from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "scholarships.db"
SAMPLE_PATH = ROOT / "data" / "sample_records.json"
TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "20"))
MAX_DISCOVERED_URLS = int(os.getenv("MAX_DISCOVERED_URLS", "30"))
USER_AGENT = "ScholarshipIntelligenceCrawler/1.0 (educational research; contact: local-run)"
SEED_SOURCES = [
    {"url":"https://scholarships.gov.in/All-Scholarships","type":"government_portal","name":"National Scholarship Portal"},
    {"url":"https://www.ugc.gov.in/Home/student_Corner","type":"regulator","name":"University Grants Commission Student Corner"},
    {"url":"https://socialjustice.gov.in/schemes/27","type":"ministry_department","name":"Department of Social Justice and Empowerment"},
    {"url":"https://tribal.nic.in/Scholarship.aspx","type":"ministry_department","name":"Ministry of Tribal Affairs"},
    {"url":"https://www.education.gov.in/","type":"ministry_department","name":"Ministry of Education"},
    {"url":"https://www.aicte-india.org/","type":"regulator","name":"All India Council for Technical Education"},
]
OFFICIAL_SUFFIXES = (".gov.in", ".nic.in", ".ac.in", ".edu.in", ".gov", ".edu")
OFFICIAL_EXACT = {"scholarships.gov.in","ugc.gov.in","aicte-india.org","socialjustice.gov.in","tribal.nic.in","education.gov.in"}
