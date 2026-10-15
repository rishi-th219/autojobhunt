#!/usr/bin/env python3
"""
naukri_instahyre_scanner.py — Crawl4AI-powered Scraper for India's Leading Job Boards
Crawls Naukri.com and Instahyre.com using Crawl4AI with Playwright stealth mode.

Target Profiles:
  - Data Analyst (Bengaluru & Remote, 0-2 years)
  - Business Analyst (Bengaluru & Remote, 0-2 years)
  - BI / Power BI Developer (Bengaluru & Remote, 0-2 years)
  - Junior / Associate Data Engineer (Bengaluru & Remote, 0-2 years)

Automatically parses job titles, company names, experience requirements, and apply links,
deduplicates against pipeline history, and syncs directly into opportunities.xlsx.
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
    "dsai"
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

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] [Naukri/Instahyre] {msg}"
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
                    seen.add(match.group(0).split("#")[0].rstrip("/"))

    if os.path.exists(SCAN_HISTORY_FILE):
        with open(SCAN_HISTORY_FILE, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                parts = line.split("\t")
                if parts:
                    seen.add(parts[0].strip().split("#")[0].rstrip("/"))
    return seen

def matches_filters(title):
    title_lower = title.lower()
    if not any(pos in title_lower for pos in POSITIVE_KEYWORDS):
        return False
    if any(neg in title_lower for neg in NEGATIVE_KEYWORDS):
        return False
    return True

async def scan_naukri(crawler, r_conf, seen):
    queries = [
        ("Data Analyst (BLR)", "https://www.naukri.com/data-analyst-jobs-in-bengaluru?experience=0&experience=2"),
        ("Business Analyst (BLR)", "https://www.naukri.com/business-analyst-jobs-in-bengaluru?experience=0&experience=2"),
        ("Data Engineer (BLR)", "https://www.naukri.com/data-engineer-jobs-in-bengaluru?experience=0&experience=2"),
        ("ML Engineer (BLR)", "https://www.naukri.com/machine-learning-engineer-jobs-in-bengaluru?experience=0&experience=2"),
        ("AI Engineer (BLR)", "https://www.naukri.com/ai-engineer-jobs-in-bengaluru?experience=0&experience=2"),
        ("Research Associate (BLR)", "https://www.naukri.com/research-associate-jobs-in-bengaluru?experience=0&experience=2"),
        ("Assistant Professor CSE", "https://www.naukri.com/assistant-professor-computer-science-jobs?experience=0&experience=2"),
        ("Data Analyst (Remote)", "https://www.naukri.com/data-analyst-jobs?wfhType=0&experience=0&experience=2"),
        ("Data Analyst (Pune)", "https://www.naukri.com/data-analyst-jobs-in-pune?experience=0&experience=2"),
        ("Business Analyst (Pune)", "https://www.naukri.com/business-analyst-jobs-in-pune?experience=0&experience=2"),
        ("Data Engineer (Pune)", "https://www.naukri.com/data-engineer-jobs-in-pune?experience=0&experience=2"),
        ("ML/AI Engineer (Pune)", "https://www.naukri.com/machine-learning-engineer-jobs-in-pune?experience=0&experience=2"),
        ("Data & Tech Roles (Raipur)", "https://www.naukri.com/jobs-in-raipur?experience=0&experience=2"),
        ("Assistant Professor / Faculty (Raipur)", "https://www.naukri.com/assistant-professor-jobs-in-raipur"),
        ("Accenture Analytics / Tech", "https://www.naukri.com/accenture-jobs?experience=0&experience=2"),
        ("Cognizant Analytics / Tech", "https://www.naukri.com/cognizant-jobs?experience=0&experience=2"),
        ("TCS Analytics / Tech", "https://www.naukri.com/tcs-jobs?experience=0&experience=2"),
        ("Infosys Analytics / Tech", "https://www.naukri.com/infosys-jobs?experience=0&experience=2"),
        ("Wipro Analytics / Tech", "https://www.naukri.com/wipro-jobs?experience=0&experience=2")
    ]
    discovered = []
    for label, url in queries:
        log(f"Crawling Naukri: {label}...")
        try:
            res = await crawler.arun(url=url, config=r_conf)
            if not res.success:
                log(f"  -> Naukri crawl failed for {label}")
                continue

            links = res.links.get("internal", []) + res.links.get("external", [])
            count = 0
            for l in links:
                href = l.get("href", "")
                text = (l.get("text", "") or "").strip()
                if "/job-listings-" not in href:
                    continue

                clean_href = href.split("?")[0].split("#")[0].rstrip("/")
                if clean_href in seen:
                    continue

                # Parse URL structure: job-listings-{title}-{company}-{location}-{exp}-years-{id}
                slug = clean_href.split("/job-listings-")[-1]
                slug_parts = slug.split("-")
                
                # Heuristic title recovery from link text or URL slug
                title = text if text and len(text) > 4 and "..." not in text else " ".join(slug_parts[:3]).title()

                if not matches_filters(title):
                    continue

                # Extract company and experience from slug if possible
                comp_match = re.search(r"-([a-z0-9]+(?:-limited|-pvt|-services|-technologies|-solutions)?)-(?:bengaluru|bangalore|pune|raipur|india|mumbai|remote)", slug)
                if comp_match:
                    company = comp_match.group(1).replace("-", " ").title()
                elif "accenture" in slug or "accenture" in label.lower():
                    company = "Accenture"
                elif "cognizant" in slug or "cognizant" in label.lower():
                    company = "Cognizant"
                elif "tcs" in slug or "tcs" in label.lower():
                    company = "TCS"
                elif "infosys" in slug or "infosys" in label.lower():
                    company = "Infosys"
                elif "wipro" in slug or "wipro" in label.lower():
                    company = "Wipro"
                else:
                    company = "Enterprise on Naukri"
                
                exp_match = re.search(r"(\d+-to-\d+-years)", slug)
                exp = exp_match.group(1).replace("-to-", "-").replace("-years", " years") if exp_match else "0-2 years (Inferred)"

                # Location resolution
                if "pune" in slug or "pune" in label.lower():
                    loc_resolved = "Pune, Maharashtra, IND"
                elif "raipur" in slug or "raipur" in label.lower():
                    loc_resolved = "Raipur, Chhattisgarh, IND"
                elif "remote" in label.lower() or "wfh" in slug:
                    loc_resolved = "India (Remote)"
                else:
                    loc_resolved = "Bengaluru, IND"

                seen.add(clean_href)
                discovered.append({
                    "url": clean_href,
                    "company": company,
                    "title": title,
                    "location": loc_resolved,
                    "experience": exp,
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "portal": "naukri-crawl4ai"
                })
                count += 1

            log(f"  -> Extracted {count} matching roles from Naukri ({label})")
        except Exception as e:
            log(f"  -> Error crawling Naukri {label}: {e}")

    return discovered

async def scan_instahyre(crawler, r_conf, seen):
    queries = [
        ("Data Analyst (BLR)", "https://www.instahyre.com/jobs-in-bangalore/?search=data%20analyst"),
        ("Business Analyst (BLR)", "https://www.instahyre.com/jobs-in-bangalore/?search=business%20analyst"),
        ("Data Engineer (BLR)", "https://www.instahyre.com/jobs-in-bangalore/?search=data%20engineer"),
        ("ML Engineer (BLR)", "https://www.instahyre.com/jobs-in-bangalore/?search=machine%20learning"),
        ("Data Analyst (Pune)", "https://www.instahyre.com/jobs-in-pune/?search=data%20analyst"),
        ("Data Engineer (Pune)", "https://www.instahyre.com/jobs-in-pune/?search=data%20engineer"),
        ("ML Engineer (Pune)", "https://www.instahyre.com/jobs-in-pune/?search=machine%20learning"),
    ]
    discovered = []
    for label, url in queries:
        log(f"Crawling Instahyre: {label}...")
        try:
            res = await crawler.arun(url=url, config=r_conf)
            if not res.success:
                log(f"  -> Instahyre crawl failed for {label}")
                continue

            links = res.links.get("internal", []) + res.links.get("external", [])
            count = 0
            for l in links:
                href = l.get("href", "")
                text = (l.get("text", "") or "").strip()
                if "/job-" not in href:
                    continue

                clean_href = href.split("?")[0].split("#")[0].rstrip("/")
                if clean_href in seen:
                    continue

                # Slug: job-{id}-{title}-at-{company}-{location}/
                slug = clean_href.split("/job-")[-1].rstrip("/")
                at_parts = slug.split("-at-")
                if len(at_parts) == 2:
                    raw_title = re.sub(r"^\d+-", "", at_parts[0]).replace("-", " ").title()
                    raw_comp = re.sub(r"-(bangalore|bengaluru|pune|mumbai|remote)$", "", at_parts[1]).replace("-", " ").title()
                else:
                    raw_title = text or "Data Analyst"
                    raw_comp = "Tech Company (Instahyre)"

                if not matches_filters(raw_title):
                    continue

                loc_instahyre = "Pune, Maharashtra, IND" if "pune" in label.lower() or "pune" in slug else "Bengaluru, IND"

                seen.add(clean_href)
                discovered.append({
                    "url": clean_href,
                    "company": raw_comp,
                    "title": raw_title,
                    "location": loc_instahyre,
                    "experience": "0-2 years (Inferred)",
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "portal": "instahyre-crawl4ai"
                })
                count += 1

            log(f"  -> Extracted {count} matching roles from Instahyre ({label})")
        except Exception as e:
            log(f"  -> Error crawling Instahyre {label}: {e}")

    return discovered

async def run_scrapers():
    try:
        from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig, CacheMode
    except ImportError:
        log("crawl4ai not found in environment. Please install it via .venv.")
        return []

    b_conf = BrowserConfig(headless=True, enable_stealth=True)
    r_conf = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        wait_until="networkidle",
        delay_before_return_html=3.0,
        scan_full_page=True
    )

    seen = load_seen_urls()
    discovered = []

    async with AsyncWebCrawler(config=b_conf, verbose=False) as crawler:
        naukri_jobs = await scan_naukri(crawler, r_conf, seen)
        discovered.extend(naukri_jobs)
        
        instahyre_jobs = await scan_instahyre(crawler, r_conf, seen)
        discovered.extend(instahyre_jobs)

    log(f"Crawl completed. {len(discovered)} total fresh roles found on Naukri and Instahyre.")
    return discovered

def main():
    log("==================================================")
    log("Starting Naukri & Instahyre Crawl4AI job discovery...")
    jobs = asyncio.run(run_scrapers())
    if not jobs:
        log("No new unique jobs discovered from Naukri/Instahyre on this run.")
        return

    # Update pipeline.md
    pipeline_lines = []
    if os.path.exists(PIPELINE_FILE):
        with open(PIPELINE_FILE, "r", encoding="utf-8") as f:
            pipeline_lines = f.readlines()

    new_entries = [
        f"- [ ] {j['url']} | {j['company']} | {j['title']} | {j['location']} | posted: {j['date']}\n"
        for j in jobs
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
        for j in jobs:
            f.write(f"{j['url']}\t{j['date']}\t{j['portal']}\t{j['title']}\t{j['company']}\tadded\t{j['location']}\n")

    # Sync into opportunities.xlsx
    try:
        from opportunities_manager import main as sync_opportunities
        sync_opportunities()
        log("Synced new opportunities into opportunities.xlsx.")
    except Exception as e:
        log(f"Error syncing to opportunities.xlsx: {e}")

    log(f"Successfully added {len(jobs)} Naukri & Instahyre opportunities to pipeline!")
    log("==================================================")

if __name__ == "__main__":
    main()
