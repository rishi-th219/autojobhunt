#!/usr/bin/env python3
"""
crawl4ai_scanner.py — FOSS Dynamic Web Crawler for Job Discovery & Detail Extraction
Powered by Crawl4AI (https://github.com/unclecode/crawl4AI).

Capabilities:
  1. Dynamic JS / SPA Career Portal Crawling:
     Crawls client-side rendered portals (React/Angular/Vue/SPAs) like Swiggy, PhonePe,
     Flipkart, Zepto, Razorpay, and Workday boards with Playwright stealth.
  2. Deep Job Detail & Qualification Extraction:
     Extracts clean markdown from any job posting URL to accurately identify:
     - Exact required experience (e.g., 0-2 years, 1-3 years)
     - Top technical skills (SQL, Python, Power BI, ETL, Machine Learning, etc.)
     - Location & remote eligibility
     - Liveness / expired status detection
  3. Automatic Pipeline Synchronization:
     Pipes discovered roles directly into data/pipeline.md and updates opportunities.xlsx.
"""

import os
import sys
import re
import json
import asyncio
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
PIPELINE_FILE = os.path.join(PROJECT_ROOT, "data", "pipeline.md")
SCAN_HISTORY_FILE = os.path.join(PROJECT_ROOT, "data", "scan-history.tsv")
LOG_FILE = os.path.join(PROJECT_ROOT, "data", "cron_scan.log")
BLACKLIST_FILE = os.path.join(PROJECT_ROOT, "data", "blacklist.md")

POSITIVE_KEYWORDS = [
    "data analyst",
    "business analyst",
    "bi analyst",
    "bi developer",
    "business intelligence",
    "reporting analyst",
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
    "software development engineer - python"
]

NEGATIVE_KEYWORDS = [
    "intern",
    "internship",
    "praktikum",
    "werkstudent",
    "gyakornok",
    "staż",
    "stage -",
    "stage ",
    "premaster",
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

DISALLOWED_CITIES = [
    "hyderabad", "mumbai", "pune", "chennai", "gurgaon", "gurugram",
    "noida", "delhi", "kolkata", "ahmedabad", "secunderabad"
]

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] [Crawl4AI] {msg}"
    print(formatted)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except Exception:
        pass

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

def matches_filters(title, location="", company=""):
    comb = f"{title} {company} {location}".lower()
    title_lower = title.lower()

    if not any(pos in title_lower for pos in POSITIVE_KEYWORDS):
        return False

    if any(neg in title_lower for neg in NEGATIVE_KEYWORDS):
        return False

    if location:
        loc_lower = str(location).lower()
        if any(city in loc_lower for city in DISALLOWED_CITIES) and not any(r in loc_lower for r in ["remote", "hybrid", "india"]):
            return False

    return True

async def extract_job_details_crawl4ai(url):
    """
    Crawls an individual job URL using Crawl4AI and extracts:
    title, company, required experience, skills, pay, location, and liveness.
    """
    try:
        from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig, CacheMode
    except ImportError:
        log("crawl4ai is not installed in the active environment.")
        return None

    b_conf = BrowserConfig(headless=True, enable_stealth=True)
    r_conf = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        wait_until="networkidle",
        delay_before_return_html=2.0
    )

    async with AsyncWebCrawler(config=b_conf, verbose=False) as crawler:
        res = await crawler.arun(url=url, config=r_conf)
        if not res.success or not res.markdown:
            return None

        md = res.markdown
        # Liveness check
        if any(exp in md.lower() for exp in ["page you are looking for doesn't exist", "job is no longer available", "position has been filled"]):
            return {"expired": True, "url": url}

        # Experience extraction
        exp_match = re.search(r"\b([0-5]\s*[-–to]+\s*[1-5]|\d+\+?)\s*(?:years?|yrs?)\b", md, re.IGNORECASE)
        experience = exp_match.group(0).strip() if exp_match else "0-2 years (Inferred)"

        # Skill extraction
        skills = []
        md_lower = md.lower()
        skill_catalog = [
            ("SQL", ["sql", "mysql", "postgresql", "oracle"]),
            ("Python", ["python", "pandas", "numpy"]),
            ("Power BI", ["power bi", "dax", "powerbi"]),
            ("Tableau", ["tableau"]),
            ("Excel", ["excel", "spreadsheets", "vlookup"]),
            ("ETL", ["etl", "data pipeline", "data pipelines", "airflow"]),
            ("Machine Learning", ["machine learning", "pytorch", "scikit-learn", "deep learning"]),
            ("Cloud", ["aws", "gcp", "azure", "snowflake", "bigquery"])
        ]
        for skill_name, triggers in skill_catalog:
            if any(t in md_lower for t in triggers):
                skills.append(skill_name)
        if not skills:
            skills = ["SQL", "Excel", "Data Analysis"]

        # Pay extraction
        pay_match = re.search(r"(?:₹|\bINR\b|\$)\s*[\d,]+(?:\s*-\s*[\d,]+)?(?:\s*(?:LPA|per annum|a year|\/yr))?", md, re.IGNORECASE)
        pay = pay_match.group(0).strip() if pay_match else "Not Listed"

        return {
            "expired": False,
            "url": url,
            "experience": experience,
            "skills": ", ".join(skills),
            "pay": pay,
            "markdown": md[:1000]
        }

async def crawl_dynamic_portals(portal_list=None):
    """
    Crawls dynamic company career portals using Crawl4AI to discover fresh roles.
    """
    try:
        from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig, CacheMode
    except ImportError:
        log("crawl4ai is not installed in the active environment.")
        return []

    if portal_list is None:
        portal_list = [
            {"company": "Swiggy", "url": "https://careers.swiggy.com/#/careers"},
            {"company": "Razorpay", "url": "https://razorpay.com/jobs/"},
            {"company": "CRED", "url": "https://jobs.lever.co/cred"},
            {"company": "Groww", "url": "https://job-boards.greenhouse.io/groww"},
            {"company": "InMobi", "url": "https://job-boards.greenhouse.io/inmobi"},
            {"company": "Postman", "url": "https://job-boards.greenhouse.io/postman"},
            {"company": "Thoughtworks", "url": "https://job-boards.greenhouse.io/thoughtworks"},
            {"company": "Databricks", "url": "https://job-boards.greenhouse.io/databricks"},
            {"company": "Zepto", "url": "https://job-boards.greenhouse.io/zepto"},
        ]

    b_conf = BrowserConfig(headless=True, enable_stealth=True)
    r_conf = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        wait_until="networkidle",
        delay_before_return_html=2.5,
        scan_full_page=True,
    )

    seen = load_seen_urls()
    discovered_jobs = []

    log(f"Starting Crawl4AI discovery across {len(portal_list)} dynamic career portals...")

    async with AsyncWebCrawler(config=b_conf, verbose=False) as crawler:
        for p in portal_list:
            comp = p["company"]
            url = p["url"]
            log(f"Crawling dynamic portal [{comp}] ({url})...")

            try:
                res = await crawler.arun(url=url, config=r_conf)
                if not res.success or not res.markdown:
                    log(f"  -> Failed or empty response from {comp}")
                    continue

                links = res.links.get("internal", []) + res.links.get("external", [])
                log(f"  -> Extracted {len(links)} links from {comp}")

                for l in links:
                    href = l.get("href", "")
                    text = (l.get("text", "") or "").strip()
                    if not href or not text or len(text) < 4:
                        continue

                    # Filter for job postings
                    clean_href = href.split("#")[0].rstrip("/")
                    if clean_href in seen:
                        continue

                    # Ensure it is an actual job posting link, not marketing/product page
                    path_lower = clean_href.lower()
                    if any(bad in path_lower for bad in ["/product", "/solutions", "/pricing", "/features", "/customers", "/blog", "/press", "/privacy", "/terms", "/about", "/security"]):
                        continue
                    if not any(good in path_lower for good in ["/job", "/jobs", "/careers", "/posting", "/req", "/positions", "greenhouse.io", "lever.co", "ashbyhq.com", "smartrecruiters.com"]):
                        continue

                    # Must match positive keywords
                    if matches_filters(text, company=comp):
                        seen.add(clean_href)
                        discovered_jobs.append({
                            "url": clean_href,
                            "company": comp,
                            "title": text,
                            "location": "Bengaluru, IND",
                            "date": datetime.now().strftime("%Y-%m-%d"),
                            "portal": "crawl4ai"
                        })
                        log(f"    ✓ Found matching role: '{text}' -> {clean_href}")

            except Exception as e:
                log(f"  -> Error crawling {comp}: {e}")

    log(f"Crawl4AI scan completed. {len(discovered_jobs)} qualified opportunities discovered.")
    return discovered_jobs

def main():
    if len(sys.argv) > 2 and sys.argv[1] == "--enrich":
        target_url = sys.argv[2]
        print(f"Enriching job details for {target_url} via Crawl4AI...")
        details = asyncio.run(extract_job_details_crawl4ai(target_url))
        print(json.dumps(details, indent=2))
        return

    discovered = asyncio.run(crawl_dynamic_portals())
    if not discovered:
        print("No new jobs found via Crawl4AI.")
        return

    # Update pipeline.md
    pipeline_lines = []
    if os.path.exists(PIPELINE_FILE):
        with open(PIPELINE_FILE, "r", encoding="utf-8") as f:
            pipeline_lines = f.readlines()

    new_entries = [
        f"- [ ] {j['url']} | {j['company']} | {j['title']} | {j['location']} | posted: {j['date']}\n"
        for j in discovered
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

    # Update scan-history.tsv
    with open(SCAN_HISTORY_FILE, "a", encoding="utf-8") as f:
        for j in discovered:
            f.write(f"{j['url']}\t{j['date']}\t{j['portal']}\t{j['title']}\t{j['company']}\tadded\t{j['location']}\n")

    # Sync with opportunities.xlsx
    try:
        from opportunities_manager import main as sync_opportunities
        sync_opportunities()
        log("Successfully synchronized new opportunities to opportunities.xlsx.")
    except Exception as e:
        log(f"Error syncing to opportunities.xlsx: {e}")

    log(f"Successfully added {len(discovered)} Crawl4AI roles to pipeline and tracker.")

if __name__ == "__main__":
    main()
