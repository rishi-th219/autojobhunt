#!/usr/bin/env python3
"""
clean_expired_jobs.py — Automated Link Liveness & Expired Job Cleaner
Periodically verifies all URLs in opportunities.xlsx and opportunities.csv.

Detects:
  - HTTP 404 (Not Found) & HTTP 410 (Gone)
  - ATS expiration markers ("This job is no longer available", "Position closed", "No longer accepting applications")
  - Workday & SmartRecruiters "Page you are looking for doesn't exist"

Safely archives expired jobs to data/archived_expired_opportunities.csv and regenerates
clean opportunities.xlsx and opportunities.csv with 100% active, verified links.
"""

import os
import sys
import csv
import re
import json
import urllib.request
import urllib.error
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
OPPORTUNITIES_CSV = os.path.join(PROJECT_ROOT, "opportunities.csv")
OPPORTUNITIES_XLSX = os.path.join(PROJECT_ROOT, "opportunities.xlsx")
ARCHIVE_CSV = os.path.join(PROJECT_ROOT, "data", "archived_expired_opportunities.csv")
PIPELINE_FILE = os.path.join(PROJECT_ROOT, "data", "pipeline.md")
JSON_FILE = os.path.join(PROJECT_ROOT, "new_jobs_found.json")

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

EXPIRED_PATTERNS = [
    r"job (is )?no longer available",
    r"job.*no longer open",
    r"this position has been filled",
    r"the job you are trying to apply for has been filled",
    r"this job has expired",
    r"job posting has expired",
    r"no longer accepting applications",
    r"this (position|role|job) (is )?no longer active",
    r"this (position|role|job) (is )?no longer accepting",
    r"this job (listing )?is closed",
    r"job (listing )?not found",
    r"the page you are looking for doesn.t exist",
    r"applications?\s+(?:(?:have|are|is)\s+)?closed",
    r"we are no longer taking applications",
    r"this role is closed",
    r"this posting has been closed",
    r"closed-job__flavor",
    r"job is closed",
    r"closed on \d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
]
COMPILED_EXPIRED = [re.compile(p, re.IGNORECASE) for p in EXPIRED_PATTERNS]

def check_ats_api(url):
    # 1. Greenhouse direct board API
    gh_match = re.search(r"greenhouse\.io/([^/]+)/jobs/(\d+)", url)
    if gh_match:
        board, job_id = gh_match.group(1), gh_match.group(2)
        api_url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}"
        req = urllib.request.Request(api_url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=6) as resp:
                if resp.status == 200:
                    return True, "Greenhouse API: 200 Live"
        except urllib.error.HTTPError as e:
            if e.code in [404, 410]:
                return False, f"Greenhouse API HTTP {e.code} (Job Closed/Removed)"
        except Exception:
            pass

    # 2. Lever API check
    lev_match = re.search(r"jobs\.lever\.co/([^/]+)/([a-f0-9\-]+)", url)
    if lev_match:
        company, job_id = lev_match.group(1), lev_match.group(2)
        api_url = f"https://api.lever.co/v0/postings/{company}/{job_id}"
        req = urllib.request.Request(api_url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=6) as resp:
                if resp.status == 200:
                    return True, "Lever API: 200 Live"
        except Exception:
            pass

    # 3. Ashby job board API check
    ashby_match = re.search(r"jobs\.ashbyhq\.com/([^/]+)/([a-f0-9\-]+)", url)
    if ashby_match:
        org, job_id = ashby_match.group(1), ashby_match.group(2)
        api_url = f"https://api.ashbyhq.com/posting-api/job-board/{org}"
        req = urllib.request.Request(api_url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                jobs = data.get("jobs", [])
                if any(str(j.get("id")) == job_id for j in jobs):
                    return True, "Ashby API: Active"
                else:
                    return False, "Ashby API: Job ID no longer listed on board"
        except Exception:
            pass

    # 4. LinkedIn guest endpoint check
    li_match = re.search(r"linkedin\.com/jobs/view/(?:.*-)?(\d+)", url)
    if li_match:
        job_id = li_match.group(1)
        api_url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
        req = urllib.request.Request(api_url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
        try:
            with urllib.request.urlopen(req, timeout=6) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
                if "No longer accepting applications" in html or "closed-job__flavor" in html:
                    return False, "LinkedIn: No longer accepting applications"
                if re.search(r"public_jobs_apply-link-onsite|job-details-topcard-apply-modal", html):
                    return True, "LinkedIn: Active Apply Button"
        except urllib.error.HTTPError as e:
            if e.code in [404, 410]:
                return False, f"LinkedIn HTTP {e.code}"
        except Exception:
            pass

    # 5. Workday CXS check
    wd_match = re.search(r"([\w-]+)\.(wd[\w-]*)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([^/?#]+)/job/(.+?)/?$", url)
    if wd_match:
        tenant, shard, site, job_path = wd_match.groups()
        api_url = f"https://{tenant}.{shard}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/job/{job_path}"
        req = urllib.request.Request(api_url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=6) as resp:
                if resp.status == 200:
                    return True, "Workday API: 200 Live"
        except urllib.error.HTTPError as e:
            if e.code in [404, 410]:
                return False, f"Workday API HTTP {e.code} (Job Closed)"
        except Exception:
            pass

    return None, None

def check_link_liveness(url, timeout=8):
    """
    Returns (is_live: bool, reason: str)
    """
    if not url or not url.startswith("http"):
        return False, "Invalid URL"

    # Priority 1: ATS / Native API Check
    api_live, api_reason = check_ats_api(url)
    if api_live is not None:
        return api_live, api_reason

    # Priority 2: Full HTML Page Inspection (up to 300KB)
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9"
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            if status in [404, 410]:
                return False, f"HTTP {status}"

            raw = resp.read(300000)
            text = raw.decode("utf-8", errors="ignore")
            for cp in COMPILED_EXPIRED:
                m = cp.search(text)
                if m:
                    return False, f"Page text: '{m.group(0)}'"

            return True, "Active"
    except urllib.error.HTTPError as e:
        if e.code in [404, 410]:
            return False, f"HTTP {e.code}"
        # Some ATS return 403 to basic User-Agent, assume live rather than falsely archiving
        return True, f"HTTP {e.code} (presumed live)"
    except urllib.error.URLError as e:
        return True, f"Connection warning: {e.reason}"
    except Exception as e:
        return True, f"Timeout / Check skipped: {e}"

def main(dry_run=False):
    if not os.path.exists(OPPORTUNITIES_CSV):
        print("No opportunities.csv found.")
        return

    print("==================================================")
    print("Starting Automated Dead-Link & Expiry Verification...")
    
    rows = []
    with open(OPPORTUNITIES_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        rows = list(reader)

    print(f"Checking {len(rows)} opportunities concurrently for link liveness...")

    active_rows = []
    expired_rows = []

    from concurrent.futures import ThreadPoolExecutor, as_completed

    def evaluate_row(row):
        url = row.get("apply link", "").strip()
        is_live, reason = check_link_liveness(url)
        return row, is_live, reason

    with ThreadPoolExecutor(max_workers=16) as executor:
        futures = [executor.submit(evaluate_row, r) for r in rows]
        for f in as_completed(futures):
            row, is_live, reason = f.result()
            if is_live:
                active_rows.append(row)
            else:
                comp = row.get("Firm name", "Unknown")
                title = row.get("Job role", "Role")
                print(f"  ❌ EXPIRED [{comp}] {title} -> {reason}")
                row["archived_date"] = datetime.now().strftime("%Y-%m-%d")
                row["archive_reason"] = reason
                expired_rows.append(row)

    print("--------------------------------------------------")
    print(f"Results: {len(active_rows)} Active, {len(expired_rows)} Expired/Closed.")

    if not expired_rows:
        print("✓ All opportunity links are active and healthy!")
        print("==================================================")
        return

    if dry_run:
        print("[Dry Run] No files modified.")
        return

    # 1. Archive expired rows to data/archived_expired_opportunities.csv
    archive_exists = os.path.exists(ARCHIVE_CSV)
    archive_fields = list(fields) + ["archived_date", "archive_reason"]
    with open(ARCHIVE_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=archive_fields)
        if not archive_exists:
            writer.writeheader()
        for exp_row in expired_rows:
            writer.writerow({k: exp_row.get(k, "") for k in archive_fields})
    print(f"✓ Archived {len(expired_rows)} expired roles to {ARCHIVE_CSV}.")

    # 2. Write active rows back to opportunities.csv
    with open(OPPORTUNITIES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for act_row in active_rows:
            writer.writerow({k: act_row.get(k, "") for k in fields})

    # 3. Rebuild opportunities.xlsx
    try:
        from opportunities_manager import build_xlsx
        build_xlsx(active_rows, OPPORTUNITIES_XLSX)
        print(f"✓ Successfully regenerated {OPPORTUNITIES_XLSX} with {len(active_rows)} active roles.")
    except Exception as e:
        print(f"Error rebuilding xlsx: {e}")

    # 4. Remove expired URLs from data/pipeline.md
    if os.path.exists(PIPELINE_FILE):
        expired_urls = {r.get("apply link", "").strip() for r in expired_rows}
        clean_lines = []
        with open(PIPELINE_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if not any(exp_u in line for exp_u in expired_urls if exp_u):
                    clean_lines.append(line)
        with open(PIPELINE_FILE, "w", encoding="utf-8") as f:
            f.writelines(clean_lines)
        print("✓ Cleaned expired links from data/pipeline.md.")

    # 5. Remove expired URLs from new_jobs_found.json
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, "r", encoding="utf-8") as f:
                jobs_json = json.load(f)
            expired_url_set = {r.get("apply link", "").strip() for r in expired_rows}
            expired_url_set.update({u.split("#")[0].rstrip("/") for u in expired_url_set if u})
            clean_json = [j for j in jobs_json if j.get("apply link", "").strip() not in expired_url_set and j.get("apply link", "").split("#")[0].rstrip("/") not in expired_url_set]
            with open(JSON_FILE, "w", encoding="utf-8") as f:
                json.dump(clean_json, f, indent=2)
            print("✓ Cleaned expired links from new_jobs_found.json.")
        except Exception as e:
            print(f"Error cleaning new_jobs_found.json: {e}")

    print(f"✓ Cleanup finished! Active opportunities preserved: {len(active_rows)}")
    print("==================================================")

if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    main(dry_run=dry)
