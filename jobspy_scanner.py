#!/usr/bin/env python3
"""
jobspy_scanner.py — Open-source Multi-Portal Job Scraper for Career-Ops
Uses python-jobspy to discover jobs from LinkedIn and Indeed without requiring API keys.
Scans for Data Analyst, Business Analyst, BI, and R&D roles in Bengaluru & Remote India.
Deduplicates against data/pipeline.md and data/scan-history.tsv, respecting data/blacklist.md.
"""

import os
import sys
import re
import time
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
PIPELINE_FILE = os.path.join(PROJECT_ROOT, "data", "pipeline.md")
SCAN_HISTORY_FILE = os.path.join(PROJECT_ROOT, "data", "scan-history.tsv")
LOG_FILE = os.path.join(PROJECT_ROOT, "data", "cron_scan.log")
BLACKLIST_FILE = os.path.join(PROJECT_ROOT, "data", "blacklist.md")

POSITIVE_KEYWORDS = [
    "data analyst",
    "business analyst",
    "financial analyst",
    "marketing analyst",
    "healthcare analyst",
    "supply chain analyst",
    "sales analyst",
    "people analyst",
    "people analytics",
    "hr analyst",
    "risk analyst",
    "fraud analyst",
    "retail analyst",
    "revenue analyst",
    "operations analyst",
    "product analyst",
    "database analyst",
    "business intelligence analyst",
    "tableau specialist",
    "tableau developer",
    "tableau analyst",
    "tableau",
    "data quality analyst",
    "data quality",
    "forecasting analyst",
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
    "inventory analyst",
    "logistics analyst",
    "supply chain specialist"
]

NEGATIVE_KEYWORDS = [
    "machine learning",
    "ml engineer",
    "data scientist",
    "data science",
    "ai engineer",
    "deep learning",
    "computer vision",
    "nlp engineer",
    "software engineer",
    "backend developer",
    "backend engineer",
    "data engineer",
    "etl developer",
    "data platform engineer",
    "research engineer",
    "research scientist",
    "assistant professor",
    "lecturer",
    "faculty",
    "jrf",
    "srf",
    "python developer",
    "python engineer",
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
    " iv",
]

DISALLOWED_CITIES = [
    "hyderabad",
    "mumbai",
    "pune",
    "chennai",
    "gurgaon",
    "gurugram",
    "noida",
    "delhi",
    "kolkata",
    "ahmedabad",
    "secunderabad",
]

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] [JobSpy] {msg}"
    print(formatted)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except Exception:
        pass

def load_blacklist():
    blacklist = set()
    if os.path.exists(BLACKLIST_FILE):
        with open(BLACKLIST_FILE, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line.startswith("-") or line.startswith("*"):
                    item = line.lstrip("-* ").strip().lower()
                    if item:
                        blacklist.add(item)
    return blacklist

def load_seen_urls():
    seen = set()
    if os.path.exists(PIPELINE_FILE):
        with open(PIPELINE_FILE, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                match = re.search(r"https?://[^\s\|]+", line)
                if match:
                    clean = match.group(0).split("#")[0].rstrip("/")
                    seen.add(clean)

    if os.path.exists(SCAN_HISTORY_FILE):
        with open(SCAN_HISTORY_FILE, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                parts = line.split("\t")
                if parts:
                    clean = parts[0].strip().split("#")[0].rstrip("/")
                    seen.add(clean)
    return seen

def clean_job_url(url):
    if not url:
        return ""
    # Strip tracking params from LinkedIn
    linkedin_match = re.search(r"(https?://[a-z\.]*linkedin\.com/jobs/view/\d+)", url)
    if linkedin_match:
        return linkedin_match.group(1)
    
    # Strip tracking params from Indeed
    indeed_match = re.search(r"(https?://[a-z\.]*indeed\.com/viewjob\?jk=[a-zA-Z0-9]+)", url)
    if indeed_match:
        return indeed_match.group(1)

    # General cleanup
    url = url.split("?utm_")[0].split("&utm_")[0]
    return url.split("#")[0].rstrip("/")

def is_valid_location(location):
    if not location:
        return True
    loc_lower = str(location).lower()

    if any(city in loc_lower for city in DISALLOWED_CITIES) and "remote" not in loc_lower:
        return False

    is_blr = any(b in loc_lower for b in ["bengaluru", "bangalore", "karnataka", "ka", "blr", "in-ka"])
    is_remote = "remote" in loc_lower or "work from home" in loc_lower
    is_ind = "india" in loc_lower or "ind" in loc_lower

    return is_blr or is_remote or is_ind

def matches_filters(title, location, company="", url="", blacklist=None):
    if blacklist is None:
        blacklist = set()

    comb = f"{title} {company} {url}".lower()
    for b in blacklist:
        if b in comb:
            return False

    title_lower = title.lower()

    # Must contain at least one positive keyword
    if not any(pos in title_lower for pos in POSITIVE_KEYWORDS):
        return False

    # Must not contain negative keywords
    if any(neg in title_lower for neg in NEGATIVE_KEYWORDS):
        return False

    # Check internship policy: allow only Data, Business, BI, and Analytics internships
    if any(w in title_lower for w in ["intern", "internship", "trainee"]):
        allowed_intern_tracks = [
            "data analyst", "business analyst", "bi", "analytics", "reporting", "tableau", "sql"
        ]
        if not any(kw in title_lower for kw in allowed_intern_tracks):
            return False

    # Location check
    if not is_valid_location(location):
        return False

    return True

def run_jobspy_scan(results_per_query=10, hours_old=72):
    """
    Runs multi-board job search via python-jobspy (LinkedIn & Indeed).
    Returns list of discovered job dicts.
    """
    try:
        from jobspy import scrape_jobs
    except ImportError:
        log("python-jobspy is not installed. Run in .venv to enable JobSpy scanning.")
        return []

    blacklist = load_blacklist()
    seen_urls = load_seen_urls()
    discovered_jobs = []

    # Targeted query definitions (strictly Data Analyst & specialized domain/functional analyst roles)
    search_configs = [
        # LinkedIn Bengaluru - Core Analytics & BI
        {"site_name": ["linkedin"], "search_term": "Data Analyst", "location": "Bengaluru, Karnataka, India"},
        {"site_name": ["linkedin"], "search_term": "Business Analyst", "location": "Bengaluru, Karnataka, India"},
        {"site_name": ["linkedin"], "search_term": "Power BI Developer", "location": "Bengaluru, Karnataka, India"},
        {"site_name": ["linkedin"], "search_term": "BI Developer", "location": "Bengaluru, Karnataka, India"},
        {"site_name": ["linkedin"], "search_term": "SQL Analyst", "location": "Bengaluru, Karnataka, India"},
        {"site_name": ["linkedin"], "search_term": "Reporting Analyst", "location": "Bengaluru, Karnataka, India"},
        {"site_name": ["linkedin"], "search_term": "MIS Analyst", "location": "Bengaluru, Karnataka, India"},
        {"site_name": ["linkedin"], "search_term": "Junior Data Analyst", "location": "Bengaluru, Karnataka, India"},
        # LinkedIn Bengaluru - Industry & Domain Analysts
        {"site_name": ["linkedin"], "search_term": "Financial Analyst", "location": "Bengaluru, Karnataka, India"},
        {"site_name": ["linkedin"], "search_term": "Marketing Analyst", "location": "Bengaluru, Karnataka, India"},
        {"site_name": ["linkedin"], "search_term": "Healthcare Analyst", "location": "Bengaluru, Karnataka, India"},
        {"site_name": ["linkedin"], "search_term": "Supply Chain Analyst", "location": "Bengaluru, Karnataka, India"},
        {"site_name": ["linkedin"], "search_term": "Sales Analyst", "location": "Bengaluru, Karnataka, India"},
        {"site_name": ["linkedin"], "search_term": "People Analyst", "location": "Bengaluru, Karnataka, India"},
        {"site_name": ["linkedin"], "search_term": "HR Analyst", "location": "Bengaluru, Karnataka, India"},
        {"site_name": ["linkedin"], "search_term": "Risk Analyst", "location": "Bengaluru, Karnataka, India"},
        {"site_name": ["linkedin"], "search_term": "Fraud Analyst", "location": "Bengaluru, Karnataka, India"},
        {"site_name": ["linkedin"], "search_term": "Retail Analyst", "location": "Bengaluru, Karnataka, India"},
        {"site_name": ["linkedin"], "search_term": "Revenue Analyst", "location": "Bengaluru, Karnataka, India"},
        {"site_name": ["linkedin"], "search_term": "Operations Analyst", "location": "Bengaluru, Karnataka, India"},
        {"site_name": ["linkedin"], "search_term": "Product Analyst", "location": "Bengaluru, Karnataka, India"},
        # LinkedIn Bengaluru - Duty & Tool Analysts
        {"site_name": ["linkedin"], "search_term": "Database Analyst", "location": "Bengaluru, Karnataka, India"},
        {"site_name": ["linkedin"], "search_term": "Business Intelligence Analyst", "location": "Bengaluru, Karnataka, India"},
        {"site_name": ["linkedin"], "search_term": "Tableau Specialist", "location": "Bengaluru, Karnataka, India"},
        {"site_name": ["linkedin"], "search_term": "Tableau Developer", "location": "Bengaluru, Karnataka, India"},
        {"site_name": ["linkedin"], "search_term": "Insights Analyst", "location": "Bengaluru, Karnataka, India"},
        {"site_name": ["linkedin"], "search_term": "Data Quality Analyst", "location": "Bengaluru, Karnataka, India"},
        {"site_name": ["linkedin"], "search_term": "Forecasting Analyst", "location": "Bengaluru, Karnataka, India"},
        # LinkedIn Remote India
        {"site_name": ["linkedin"], "search_term": "Data Analyst", "location": "India", "is_remote": True},
        {"site_name": ["linkedin"], "search_term": "Business Analyst", "location": "India", "is_remote": True},
        {"site_name": ["linkedin"], "search_term": "Financial Analyst", "location": "India", "is_remote": True},
        {"site_name": ["linkedin"], "search_term": "Operations Analyst", "location": "India", "is_remote": True},
        {"site_name": ["linkedin"], "search_term": "Product Analyst", "location": "India", "is_remote": True},
        {"site_name": ["linkedin"], "search_term": "Business Intelligence Analyst", "location": "India", "is_remote": True},
        # Indeed India
        {"site_name": ["indeed"], "search_term": "Data Analyst", "location": "Bengaluru, Karnataka", "country_indeed": "india"},
        {"site_name": ["indeed"], "search_term": "Business Analyst", "location": "Bengaluru, Karnataka", "country_indeed": "india"},
        {"site_name": ["indeed"], "search_term": "Power BI Developer", "location": "Bengaluru, Karnataka", "country_indeed": "india"},
        {"site_name": ["indeed"], "search_term": "SQL Analyst", "location": "Bengaluru, Karnataka", "country_indeed": "india"},
        {"site_name": ["indeed"], "search_term": "MIS Analyst", "location": "Bengaluru, Karnataka", "country_indeed": "india"},
        {"site_name": ["indeed"], "search_term": "Reporting Analyst", "location": "Bengaluru, Karnataka", "country_indeed": "india"},
        {"site_name": ["indeed"], "search_term": "Financial Analyst", "location": "Bengaluru, Karnataka", "country_indeed": "india"},
        {"site_name": ["indeed"], "search_term": "Operations Analyst", "location": "Bengaluru, Karnataka", "country_indeed": "india"},
        {"site_name": ["indeed"], "search_term": "Product Analyst", "location": "Bengaluru, Karnataka", "country_indeed": "india"},
        {"site_name": ["indeed"], "search_term": "Supply Chain Analyst", "location": "Bengaluru, Karnataka", "country_indeed": "india"},
        {"site_name": ["indeed"], "search_term": "Tableau Specialist", "location": "Bengaluru, Karnataka", "country_indeed": "india"},
        {"site_name": ["indeed"], "search_term": "Risk Analyst", "location": "Bengaluru, Karnataka", "country_indeed": "india"},
        {"site_name": ["indeed"], "search_term": "Marketing Analyst", "location": "Bengaluru, Karnataka", "country_indeed": "india"},
    ]

    log(f"Starting JobSpy search across {len(search_configs)} query profiles (max {results_per_query} results/query, past {hours_old}h)...")

    for i, cfg in enumerate(search_configs, 1):
        site_str = ",".join(cfg.get("site_name", []))
        term = cfg.get("search_term")
        loc = cfg.get("location")
        log(f"Query {i}/{len(search_configs)}: [{site_str}] '{term}' in '{loc}'")

        try:
            df = scrape_jobs(
                site_name=cfg["site_name"],
                search_term=term,
                location=loc,
                is_remote=cfg.get("is_remote", False),
                country_indeed=cfg.get("country_indeed", "india"),
                results_wanted=results_per_query,
                hours_old=hours_old,
                verbose=0
            )

            if df is None or len(df) == 0:
                log(f"  -> 0 results returned")
                time.sleep(2)
                continue

            count_valid = 0
            for _, row in df.iterrows():
                raw_url = str(row.get("job_url") or row.get("job_url_direct") or "").strip()
                clean_url = clean_job_url(raw_url)
                if not clean_url or clean_url in seen_urls:
                    continue

                title = str(row.get("title") or "").strip()
                company = str(row.get("company") or "Discovered Company").strip()
                job_loc = str(row.get("location") or loc).strip()
                site = str(row.get("site") or "jobspy").lower()

                if not matches_filters(title, job_loc, company, clean_url, blacklist):
                    continue

                # Format date
                date_val = row.get("date_posted")
                if date_val and hasattr(date_val, "strftime"):
                    date_str = date_val.strftime("%Y-%m-%d")
                else:
                    date_str = datetime.now().strftime("%Y-%m-%d")

                seen_urls.add(clean_url)
                discovered_jobs.append({
                    "url": clean_url,
                    "company": company,
                    "title": title,
                    "location": job_loc,
                    "date": date_str,
                    "portal": f"{site}-jobspy"
                })
                count_valid += 1

            log(f"  -> {count_valid} matching, non-duplicate roles added (from {len(df)} returned)")

        except Exception as e:
            log(f"  -> Query failed: {e}")

        time.sleep(2)

    log(f"JobSpy scan completed. {len(discovered_jobs)} qualified opportunities discovered.")
    return discovered_jobs

def main():
    jobs = run_jobspy_scan(results_per_query=10, hours_old=72)
    if not jobs:
        print("No new jobs found via JobSpy.")
        return

    seen_urls = load_seen_urls()
    new_jobs = [j for j in jobs if j["url"] not in seen_urls]

    # Append to pipeline.md
    pipeline_lines = []
    if os.path.exists(PIPELINE_FILE):
        with open(PIPELINE_FILE, "r", encoding="utf-8") as f:
            pipeline_lines = f.readlines()

    new_entries = [
        f"- [ ] {j['url']} | {j['company']} | {j['title']} | {j['location']} | posted: {j['date']}\n"
        for j in new_jobs
    ]

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

    # Append to scan-history.tsv
    with open(SCAN_HISTORY_FILE, "a", encoding="utf-8") as f:
        for j in new_jobs:
            f.write(f"{j['url']}\t{j['date']}\t{j['portal']}\t{j['title']}\t{j['company']}\tadded\t{j['location']}\n")

    # Sync to opportunities.xlsx
    try:
        from opportunities_manager import main as sync_opportunities
        sync_opportunities()
        log("Synced new opportunities to opportunities.xlsx.")
    except Exception as e:
        log(f"Error syncing to opportunities.xlsx: {e}")

    # Dispatch email notification alert
    try:
        import email_notifier
        email_notifier.send_job_alert(new_jobs)
    except Exception as e:
        log(f"Email alert error: {e}")

    log(f"Successfully added {len(new_jobs)} JobSpy roles to pipeline.md and scan-history.tsv.")

if __name__ == "__main__":
    main()
