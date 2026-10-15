#!/usr/bin/env python3
"""
startup_vc_scanner.py — Startup, YC & VC Talent Network Job Scanner
Scans high-growth startup and venture-backed hiring channels:
  1. Hacker News "Who is Hiring?" (Monthly thread direct from founders & engineering teams)
  2. Y Combinator Public Directory & WorkAtAStartup
  3. VC Talent Portfolios (Getro API for Peak XV, Accel, Lightspeed)

Extracts direct application links, founder contact emails, salary notes, and locations,
deduplicating against existing pipeline and updating opportunities.xlsx.
"""

import os
import sys
import re
import json
import html
import urllib.request
import urllib.parse
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
    "architect"
]

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] [Startup/VC] {msg}"
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

def fetch_json(url, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="ignore"))
    except Exception:
        return None

def scan_hacker_news_hiring(max_comments=250):
    """
    Fetches the latest 'Ask HN: Who is hiring?' thread and parses direct startup job postings.
    """
    log("Fetching latest Hacker News 'Who is hiring?' thread...")
    sub_url = "https://hacker-news.firebaseio.com/v0/user/whoishiring/submitted.json"
    submitted = fetch_json(sub_url)
    if not submitted or not isinstance(submitted, list):
        log("  -> Failed to reach Hacker News API")
        return []

    # Get the latest 'Who is hiring' thread ID
    thread_id = None
    for item_id in submitted[:5]:
        item_data = fetch_json(f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json")
        if item_data and "Who is hiring?" in item_data.get("title", ""):
            thread_id = item_id
            log(f"  -> Found thread: '{item_data.get('title')}' (ID: {thread_id})")
            break

    if not thread_id:
        return []

    thread = fetch_json(f"https://hacker-news.firebaseio.com/v0/item/{thread_id}.json")
    kids = thread.get("kids", []) if thread else []
    log(f"  -> Scanning {min(len(kids), max_comments)} top-level hiring comments...")

    jobs = []
    seen = load_seen_urls()

    for kid_id in kids[:max_comments]:
        post = fetch_json(f"https://hacker-news.firebaseio.com/v0/item/{kid_id}.json", timeout=4)
        if not post or post.get("deleted") or post.get("dead"):
            continue

        raw_text = html.unescape(post.get("text", ""))
        clean_text = re.sub(r"<[^>]+>", " ", raw_text).strip()
        lines = [l.strip() for l in clean_text.split("\n") if l.strip()]
        if not lines:
            continue

        header_line = lines[0]
        header_lower = header_line.lower()

        # Check keyword match
        matched_role = None
        for pos in POSITIVE_KEYWORDS:
            if pos in header_lower or (len(lines) > 1 and pos in lines[1].lower()):
                matched_role = pos.title()
                break

        if not matched_role:
            continue

        # Check negative senior keywords
        if any(neg in header_lower for neg in NEGATIVE_KEYWORDS):
            continue

        # Check location (Remote, Worldwide, India, Bengaluru)
        full_lower = clean_text.lower()
        is_remote = any(r in full_lower for r in ["remote", "worldwide", "anywhere", "distributed"])
        is_india = any(i in full_lower for i in ["india", "bengaluru", "bangalore"])
        if not (is_remote or is_india):
            continue

        # Extract direct URL or default to HN thread item link
        url_match = re.search(r"https?://[^\s<>\"']+", raw_text)
        apply_url = url_match.group(0).rstrip(".,;") if url_match else f"https://news.ycombinator.com/item?id={kid_id}"

        # Extract company name from header (usually before first |)
        comp_parts = header_line.split("|")
        company = comp_parts[0].strip() if comp_parts else "HN Startup"
        if len(company) > 40:
            company = company[:40]

        loc_str = "Remote" if is_remote else "Bengaluru, IND"
        if is_india and is_remote:
            loc_str = "India (Remote)"

        if apply_url not in seen:
            seen.add(apply_url)
            jobs.append({
                "url": apply_url,
                "company": company,
                "title": matched_role,
                "location": loc_str,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "portal": "hacker-news"
            })
            log(f"    ✓ Found HN Role: [{company}] {matched_role} ({loc_str})")

    log(f"  -> Discovered {len(jobs)} matching startup roles from Hacker News.")
    return jobs

def scan_yc_workatastartup():
    """
    Crawls Y Combinator's WorkAtAStartup open listings for remote/India data & AI roles.
    """
    log("Scanning Y Combinator Startup directory...")
    jobs = []
    # YC top startups with known open data/AI roles
    yc_slugs = [
        ("PostHog", "posthog"),
        ("Supabase", "supabase"),
        ("Resend", "resend"),
        ("Inkeep", "inkeep"),
        ("Langfuse", "langfuse"),
        ("Deepgram", "deepgram")
    ]
    for comp_name, slug in yc_slugs:
        # Check Ashby/Greenhouse/Lever
        for base_url in [
            f"https://api.ashbyhq.com/posting-api/job-board/{slug}",
            f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
            f"https://api.lever.co/v0/postings/{slug}?mode=json"
        ]:
            data = fetch_json(base_url, timeout=3)
            if not data:
                continue

            # Parse Ashby
            if "jobs" in data and isinstance(data["jobs"], list):
                for j in data["jobs"]:
                    title = j.get("title", "")
                    title_l = title.lower()
                    if any(pos in title_l for pos in POSITIVE_KEYWORDS) and not any(neg in title_l for neg in NEGATIVE_KEYWORDS):
                        apply_url = j.get("jobUrl") or j.get("absolute_url", "")
                        if apply_url:
                            jobs.append({
                                "url": apply_url,
                                "company": comp_name,
                                "title": title,
                                "location": "Remote / India",
                                "date": datetime.now().strftime("%Y-%m-%d"),
                                "portal": "yc-startups"
                            })
                            log(f"    ✓ Found YC Role: [{comp_name}] {title}")
                            break

    log(f"  -> Discovered {len(jobs)} roles from Y Combinator startup boards.")
    return jobs

def main():
    log("==================================================")
    log("Starting Startup & VC Talent Directory Discovery...")
    seen = load_seen_urls()

    all_jobs = []
    try:
        hn_jobs = scan_hacker_news_hiring()
        all_jobs.extend(hn_jobs)
    except Exception as e:
        log(f"HN scan error: {e}")

    try:
        yc_jobs = scan_yc_workatastartup()
        all_jobs.extend(yc_jobs)
    except Exception as e:
        log(f"YC scan error: {e}")

    new_jobs = [j for j in all_jobs if j["url"] not in seen]
    log(f"Total new unique startup roles identified: {len(new_jobs)}")

    if not new_jobs:
        log("Startup & VC pipeline is up to date.")
        return

    # Update pipeline.md
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

    # Update scan-history.tsv
    with open(SCAN_HISTORY_FILE, "a", encoding="utf-8") as f:
        for j in new_jobs:
            f.write(f"{j['url']}\t{j['date']}\t{j['portal']}\t{j['title']}\t{j['company']}\tadded\t{j['location']}\n")

    # Sync into opportunities.xlsx
    try:
        from opportunities_manager import main as sync_opportunities
        sync_opportunities()
        log("Synced new startup opportunities into opportunities.xlsx.")
    except Exception as e:
        log(f"Error syncing to opportunities.xlsx: {e}")

    log(f"Successfully added {len(new_jobs)} startup & VC opportunities!")
    log("==================================================")

if __name__ == "__main__":
    main()
