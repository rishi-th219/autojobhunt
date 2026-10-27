#!/usr/bin/env python3
"""
daily_job_scanner.py — Automated Headless Job Discovery Scanner
Designed to run via Linux cron (or systemd timer) every morning at 09:00 AM IST.

Zero external dependencies: uses Python standard library (urllib.request, json, re, datetime, os).
Scans public job APIs across multiple providers:
  1. Greenhouse Public Boards (Thoughtworks, Databricks, MongoDB, Razorpay, etc.)
  2. Lever Public Boards (CRED, Meesho, Urban Company, Slice, Atlan, etc.)
  3. Ashby Public Boards (Juniper Square, Parker, Ramp, Retool, Cursor, etc.)
  4. SmartRecruiters Public API (Bosch Group, Eurofins, Nagarro, Pentoz Technology, etc.)
  5. Remotive Public API (Remote Data / Analytics roles worldwide/India)
  6. Jobicy Public API (Remote Data Science / Analytics roles)
  7. Arbeitnow Public API (Global Tech Remote roles)
  8. JobSpy Scraper integration (LinkedIn, Indeed)

Deduplicates against data/pipeline.md and data/scan-history.tsv, then appends fresh
leads directly into data/pipeline.md and synchronizes opportunities.xlsx / opportunities.csv.
"""

import os
import sys
import json
import re
import time
import urllib.request
import urllib.parse
from datetime import datetime

# Base paths
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
PIPELINE_FILE = os.path.join(PROJECT_ROOT, "data", "pipeline.md")
SCAN_HISTORY_FILE = os.path.join(PROJECT_ROOT, "data", "scan-history.tsv")
LOG_FILE = os.path.join(PROJECT_ROOT, "data", "cron_scan.log")
BLACKLIST_FILE = os.path.join(PROJECT_ROOT, "data", "blacklist.md")

# Profile Keyword Filters (aligned with portals.yml and config/profile.yml)
POSITIVE_KEYWORDS = [
    "data analyst",
    "business analyst",
    "bi analyst",
    "bi developer",
    "power bi developer",
    "powerbi developer",
    "business intelligence",
    "reporting analyst",
    "mis analyst",
    "mis executive",
    "mis reporting",
    "analytics analyst",
    "data analytics",
    "product analyst",
    "insights analyst",
    "sql analyst",
    "power bi",
    "analytics associate",
    "associate analyst",
    "data associate",
    "operations analyst",
    "decision support analyst",
    "research analyst",
    "r&d",
    "research engineer",
    "research scientist",
    "applied scientist",
    "associate researcher",
    "r&d engineer",
    "data engineer",
    "junior data engineer",
    "associate data engineer",
    "analytics engineer",
    "etl developer",
    "data platform engineer",
    "machine learning engineer",
    "applied ai",
    "jrf",
    "junior research fellow",
    "srf",
    "senior research fellow",
    "project associate",
    "project engineer",
    "research associate",
    "assistant professor",
    "lecturer",
    "teaching associate",
    "academic associate",
    "ad-hoc faculty",
    "faculty",
    "junior machine learning engineer",
    "associate machine learning engineer",
    "junior ml engineer",
    "associate ml engineer",
    "ml engineer",
    "junior ai engineer",
    "associate ai engineer",
    "ai engineer",
    "applied ml engineer",
    "applied machine learning engineer",
    "junior data scientist",
    "associate data scientist",
    "data scientist",
    "deep learning engineer",
    "computer vision engineer",
    "nlp engineer",
    "generative ai engineer",
    "genai engineer",
    "llm engineer",
    "ai/ml engineer",
    "ai/ml developer",
    "machine learning associate",
    "dsai",
    "python developer",
    "junior python developer",
    "associate python developer",
    "python engineer",
    "python backend",
    "backend developer",
    "backend engineer",
    "junior backend engineer",
    "fastapi",
    "flask",
    "software engineer - python",
    "sde - python",
    "software development engineer - python",
    "machine learning intern",
    "ml intern",
    "ai intern",
    "artificial intelligence intern",
    "data science intern",
    "data scientist intern",
    "deep learning intern",
    "computer vision intern",
    "nlp intern",
    "genai intern",
    "generative ai intern",
    "llm intern",
    "research intern",
    "r&d intern",
    "ai research intern",
    "contract",
    "contractor",
    "supply chain analyst",
    "inventory analyst",
    "materials planner",
    "logistics analyst",
    "supply chain specialist"
]

NEGATIVE_KEYWORDS = [
    ".net",
    "java developer",
    "ios",
    "android",
    "php",
    "embedded",
    "firmware",
    "fpga",
    "asic",
    "blockchain",
    "web3",
    "crypto",
    "salesforce admin",
    "sap abap",
    "mainframe",
    "cobol",
    "senior",
    "sr.",
    "sr ",
    "lead",
    "staff",
    "principal",
    "director",
    "head of",
    "vp",
    "vice president",
    "manager",
    "management",
    "architect",
    " iii",
    " iv"
]

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    print(formatted)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except Exception as e:
        print(f"Failed writing to log: {e}", file=sys.stderr)

import config_loader

def is_valid_location(location):
    return config_loader.is_valid_location(location)


def matches_filters(title, location, company="", url=""):
    comb = (title + " " + company + " " + url).lower()
    if any(b in comb for b in ["amazon", "adci", "asspl", "amazon.jobs"]):
        return False

    title_lower = title.lower()

    # Check positive keyword match
    if not any(pos in title_lower for pos in POSITIVE_KEYWORDS):
        return False

    # Check negative keyword exclusion
    if any(neg in title_lower for neg in NEGATIVE_KEYWORDS):
        return False

    # Check internship policy: allow only AI, ML, Data Science, and Research internships
    if any(w in title_lower for w in ["intern", "internship", "trainee", "praktikum", "werkstudent", "gyakornok", "staż"]):
        allowed_intern_tracks = [
            "machine learning", "ml", "ai", "artificial intelligence", "data science",
            "data scientist", "deep learning", "computer vision", "nlp", "genai",
            "generative ai", "llm", "research", "r&d"
        ]
        if not any(kw in title_lower for kw in allowed_intern_tracks):
            return False

    # Check explicit senior year ranges in title (e.g. 5-7 years, 4+ years)
    if re.search(r"\b([4-9]|\d{2})\+?\s*(-\s*\d+\s*)?years?", title_lower):
        return False

    # Check location filter
    if not is_valid_location(location):
        return False

    return True

def load_seen_urls():
    seen = set()
    if os.path.exists(PIPELINE_FILE):
        with open(PIPELINE_FILE, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                match = re.search(r"https?://[^\s\|]+", line)
                if match:
                    clean_url = match.group(0).split("#")[0].rstrip("/")
                    seen.add(clean_url)

    if os.path.exists(SCAN_HISTORY_FILE):
        with open(SCAN_HISTORY_FILE, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                parts = line.split("\t")
                if parts:
                    clean_url = parts[0].strip().split("#")[0].rstrip("/")
                    seen.add(clean_url)

    return seen

def fetch_json(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read().decode("utf-8", errors="ignore")
            return json.loads(content)
    except Exception:
        return None

# Source 1: Greenhouse Public Boards
def scan_greenhouse():
    boards = [
        ("Arcana Analytics", "arcanaanalytics"),
        ("Capco", "capco"),
        ("Glean", "gleanwork"),
        ("Razorpay", "razorpaysoftwareprivatelimited"),
        ("InMobi", "inmobi"),
        ("Groww", "groww"),
        ("AiDASH", "aidashinc"),
        ("Headout", "headoutcareers"),
        ("AQR India", "india"),
        ("Black Duck Software", "blackduck"),
        ("Sigmoid", "sigmoid"),
        ("Precision AQ", "precisionaq"),
        ("Enterpret", "enterpret"),
        ("Prodigal", "prodigal"),
        ("KnowBe4", "knowbe4"),
        ("Thoughtworks", "thoughtworks"),
        ("Databricks", "databricks"),
        ("MongoDB", "mongodb"),
        ("Elastic", "elastic"),
        ("Branch", "branch"),
        ("Postman", "postman"),
        ("Zepto", "zepto"),
        ("Stripe", "stripe"),
        ("GitLab", "gitlab"),
        ("Figma", "figma"),
        ("Twilio", "twilio"),
        ("Cloudflare", "cloudflare"),
        ("Fractal", "fractal"),
        ("Quantiphi", "quantiphi"),
        ("Snowflake", "snowflake"),
        ("Rubrik", "rubrik"),
        ("Cohesity", "cohesity"),
        ("Nutanix", "nutanix"),
        ("Okta", "okta"),
        ("Zscaler", "zscaler"),
        ("Confluent", "confluent"),
        ("Samsara", "samsara"),
        ("Toast", "toasttab"),
    ]
    jobs = []
    for company, slug in boards:
        url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
        data = fetch_json(url)
        if not data or "jobs" not in data:
            continue

        for item in data["jobs"]:
            title = item.get("title", "")
            apply_url = item.get("absolute_url", "")
            loc = item.get("location", {}).get("name", "")
            
            if matches_filters(title, loc, company, apply_url):
                jobs.append({
                    "url": apply_url,
                    "company": company,
                    "title": title,
                    "location": loc or "Bengaluru, India",
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "portal": "greenhouse-api"
                })
        time.sleep(0.15)

    return jobs

# Source 2: Lever Public Boards
def scan_lever():
    boards = [
        ("CRED", "cred"),
        ("Urban Company", "urbancompany"),
        ("Slice", "slice"),
        ("Meesho", "meesho"),
        ("Drivetrain", "drivetrain"),
        ("Clevertap", "clevertap"),
        ("Atlan", "atlan"),
        ("Porter", "porter"),
        ("Spinny", "spinny"),
        ("Licious", "licious"),
        ("Turtlemint", "turtlemint"),
        ("Darwinbox", "darwinbox"),
    ]
    jobs = []
    for company, slug in boards:
        url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
        data = fetch_json(url)
        if not data or not isinstance(data, list):
            continue

        for item in data:
            title = item.get("text", "")
            apply_url = item.get("hostedUrl", "")
            categories = item.get("categories", {})
            loc = categories.get("location", "")
            
            if matches_filters(title, loc, company, apply_url):
                jobs.append({
                    "url": apply_url,
                    "company": company,
                    "title": title,
                    "location": loc or "Bengaluru, India",
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "portal": "lever-api"
                })
        time.sleep(0.15)

    return jobs

# Source 3: Ashby Public Boards
def scan_ashby():
    boards = [
        ("Juniper Square", "junipersquare"),
        ("Parker", "parker"),
        ("Ramp", "ramp"),
        ("Retool", "retool"),
        ("Cursor", "anysphere")
    ]
    jobs = []
    for company, slug in boards:
        url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
        data = fetch_json(url)
        if not data or "jobs" not in data:
            continue

        for item in data["jobs"]:
            title = item.get("title", "")
            apply_url = item.get("jobUrl", "")
            loc = str(item.get("location", ""))
            
            if matches_filters(title, loc, company, apply_url):
                jobs.append({
                    "url": apply_url,
                    "company": company,
                    "title": title,
                    "location": loc or "Bengaluru, India",
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "portal": "ashby-api"
                })
        time.sleep(0.15)

    return jobs

# Source 4: SmartRecruiters Public API (Bosch, Eurofins, Nagarro, Pentoz, SGS)
def scan_smartrecruiters():
    companies = [
        ("Bosch Group", "BoschGroup"),
        ("Eurofins", "Eurofins"),
        ("Nagarro", "Nagarro1"),
        ("Pentoz Technology", "PentozTechnology"),
        ("SGS", "SGS"),
        ("Publicis Sapient", "PublicisSapient"),
        ("Visa", "Visa")
    ]
    jobs = []
    for comp_name, comp_slug in companies:
        url = f"https://api.smartrecruiters.com/v1/companies/{comp_slug}/postings?country=in&limit=100"
        data = fetch_json(url)
        if not data or "content" not in data:
            continue

        for item in data.get("content", []):
            title = item.get("name", "")
            job_id = item.get("id", "")
            apply_url = f"https://jobs.smartrecruiters.com/{comp_slug}/{job_id}"
            
            loc_obj = item.get("location", {})
            city = loc_obj.get("city", "")
            country = loc_obj.get("country", "")
            is_remote = loc_obj.get("remote", False)
            
            loc_str = f"{city}, India" if city else "India"
            if is_remote:
                loc_str += " (Remote)"

            if matches_filters(title, loc_str, comp_name, apply_url):
                jobs.append({
                    "url": apply_url,
                    "company": comp_name,
                    "title": title,
                    "location": loc_str,
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "portal": "smartrecruiters-api"
                })
        time.sleep(0.2)

    return jobs

# Source 5: Remotive Public API (Remote Data / Analytics)
def scan_remotive():
    jobs = []
    urls = [
        "https://remotive.com/api/remote-jobs?category=data&limit=50",
        "https://remotive.com/api/remote-jobs?category=software-dev&limit=50"
    ]
    for u in urls:
        data = fetch_json(u)
        if not data or "jobs" not in data:
            continue

        for item in data.get("jobs", []):
            title = item.get("title", "")
            apply_url = item.get("url", "")
            comp = item.get("company_name", "Remote Company")
            candidate_loc = (item.get("candidate_required_location") or "").lower()
            
            # Check eligibility: Worldwide, Anywhere, India, or blank
            is_eligible = any(el in candidate_loc for el in ["worldwide", "anywhere", "india", "apac", "global"]) or not candidate_loc
            if not is_eligible:
                continue

            loc_str = f"Remote ({item.get('candidate_required_location') or 'Worldwide'})"
            if matches_filters(title, loc_str, comp, apply_url):
                jobs.append({
                    "url": apply_url,
                    "company": comp,
                    "title": title,
                    "location": loc_str,
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "portal": "remotive-api"
                })
        time.sleep(0.3)

    return jobs

# Source 6: Jobicy Public API (Remote Data Science / Analytics)
def scan_jobicy():
    jobs = []
    urls = [
        "https://jobicy.com/api/v2/remote-jobs?count=50&industry=data-science",
        "https://jobicy.com/api/v2/remote-jobs?count=50&industry=engineering"
    ]
    for u in urls:
        data = fetch_json(u)
        if not data or "jobs" not in data:
            continue

        for item in data.get("jobs", []):
            title = item.get("jobTitle", "")
            apply_url = item.get("url", "")
            comp = item.get("companyName", "Remote Company")
            geo = (item.get("jobGeo") or "").lower()
            
            # Check eligibility
            is_eligible = any(el in geo for el in ["worldwide", "anywhere", "india", "apac", "all countries", "remote"]) or not geo
            if not is_eligible:
                continue

            loc_str = f"Remote ({item.get('jobGeo') or 'Worldwide'})"
            if matches_filters(title, loc_str, comp, apply_url):
                jobs.append({
                    "url": apply_url,
                    "company": comp,
                    "title": title,
                    "location": loc_str,
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "portal": "jobicy-api"
                })
        time.sleep(0.3)

    return jobs

# Source 7: Arbeitnow Public API (Global Tech Remote)
def scan_arbeitnow():
    jobs = []
    url = "https://arbeitnow.com/api/job-board-api"
    data = fetch_json(url)
    if not data or "data" not in data:
        return jobs

    for item in data.get("data", []):
        title = item.get("title", "")
        apply_url = item.get("url", "")
        comp = item.get("company_name", "Tech Company")
        loc_str = item.get("location", "")
        is_remote = item.get("remote", False)

        if is_remote:
            loc_str = f"Remote ({loc_str})" if loc_str else "Remote"

        if matches_filters(title, loc_str, comp, apply_url):
            jobs.append({
                "url": apply_url,
                "company": comp,
                "title": title,
                "location": loc_str,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "portal": "arbeitnow-api"
            })
    return jobs

def main(include_jobspy=True):
    log("==================================================")
    log("Starting comprehensive multi-tool job discovery...")
    seen_urls = load_seen_urls()
    log(f"Loaded {len(seen_urls)} previously processed URLs for deduplication.")

    all_found = []

    # 1. Greenhouse
    try:
        gh_jobs = scan_greenhouse()
        log(f"✓ Greenhouse direct boards: {len(gh_jobs)} roles found.")
        all_found.extend(gh_jobs)
    except Exception as e:
        log(f"✗ Greenhouse error: {e}")

    # 2. Lever
    try:
        lever_jobs = scan_lever()
        log(f"✓ Lever direct boards: {len(lever_jobs)} roles found.")
        all_found.extend(lever_jobs)
    except Exception as e:
        log(f"✗ Lever error: {e}")

    # 3. Ashby
    try:
        ashby_jobs = scan_ashby()
        log(f"✓ Ashby direct boards: {len(ashby_jobs)} roles found.")
        all_found.extend(ashby_jobs)
    except Exception as e:
        log(f"✗ Ashby error: {e}")

    # 4. SmartRecruiters (Bosch, Eurofins, Nagarro, Pentoz, etc.)
    try:
        sr_jobs = scan_smartrecruiters()
        log(f"✓ SmartRecruiters API: {len(sr_jobs)} roles found.")
        all_found.extend(sr_jobs)
    except Exception as e:
        log(f"✗ SmartRecruiters error: {e}")

    # 5. Remotive
    try:
        remotive_jobs = scan_remotive()
        log(f"✓ Remotive API: {len(remotive_jobs)} roles found.")
        all_found.extend(remotive_jobs)
    except Exception as e:
        log(f"✗ Remotive error: {e}")

    # 6. Jobicy
    try:
        jobicy_jobs = scan_jobicy()
        log(f"✓ Jobicy API: {len(jobicy_jobs)} roles found.")
        all_found.extend(jobicy_jobs)
    except Exception as e:
        log(f"✗ Jobicy error: {e}")

    # 7. Arbeitnow
    try:
        an_jobs = scan_arbeitnow()
        log(f"✓ Arbeitnow API: {len(an_jobs)} roles found.")
        all_found.extend(an_jobs)
    except Exception as e:
        log(f"✗ Arbeitnow error: {e}")

    # 8. JobSpy Multi-Portal Scraper (LinkedIn, Indeed)
    if include_jobspy:
        try:
            from jobspy_scanner import run_jobspy_scan
            jobspy_jobs = run_jobspy_scan(results_per_query=8, hours_old=72)
            if jobspy_jobs:
                log(f"✓ JobSpy scraper: {len(jobspy_jobs)} roles found.")
                all_found.extend(jobspy_jobs)
        except Exception as e:
            log(f"✗ JobSpy scraper skipped/error: {e}")

    # Deduplicate against known pipeline and scan history
    new_jobs = []
    for job in all_found:
        clean_url = job["url"].split("#")[0].rstrip("/")
        if clean_url not in seen_urls:
            seen_urls.add(clean_url)
            new_jobs.append(job)

    log(f"Total new unique qualified job postings identified: {len(new_jobs)}")

    if not new_jobs:
        log("Pipeline is already up to date with all current postings.")
        return

    # Update data/pipeline.md
    pipeline_lines = []
    if os.path.exists(PIPELINE_FILE):
        with open(PIPELINE_FILE, "r", encoding="utf-8") as f:
            pipeline_lines = f.readlines()

    new_entries = []
    for job in new_jobs:
        entry = f"- [ ] {job['url']} | {job['company']} | {job['title']} | {job['location']} | posted: {job['date']}\n"
        new_entries.append(entry)

    updated_pipeline = []
    inserted = False
    for line in pipeline_lines:
        updated_pipeline.append(line)
        if line.strip() == "## Pending" and not inserted:
            updated_pipeline.extend(new_entries)
            inserted = True

    if not inserted:
        updated_pipeline = ["## Pending\n"] + new_entries + ["\n"] + pipeline_lines

    with open(PIPELINE_FILE, "w", encoding="utf-8") as f:
        f.writelines(updated_pipeline)

    # Update data/scan-history.tsv
    with open(SCAN_HISTORY_FILE, "a", encoding="utf-8") as f:
        for job in new_jobs:
            f.write(f"{job['url']}\t{job['date']}\t{job['portal']}\t{job['title']}\t{job['company']}\tadded\t{job['location']}\n")

    # Sync and build updated opportunities.xlsx and opportunities.csv
    try:
        from opportunities_manager import main as sync_opportunities
        sync_opportunities()
        log("✓ Successfully synchronized all opportunities into opportunities.xlsx and opportunities.csv.")
    except Exception as e:
        log(f"Error syncing to opportunities.xlsx: {e}")

    log(f"✓ Finished! Added {len(new_jobs)} new opportunities to pipeline and tracker.")
    log("==================================================")

if __name__ == "__main__":
    include_js = "--no-jobspy" not in sys.argv
    main(include_jobspy=include_js)
