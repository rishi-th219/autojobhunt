#!/usr/bin/env python3
"""
job_pipeline.py — Master Orchestration Tool for Career-Ops Job Discovery & Tracking

Integrates multiple discovery & application engines into one unified command center:
  1. Direct ATS APIs (Greenhouse, Lever, Ashby, SmartRecruiters)
  2. Public Remote Tech APIs (Remotive, Jobicy, Arbeitnow)
  3. JobSpy Multi-Portal Scraper (LinkedIn, Indeed)
  4. Crawl4AI Dynamic JS/SPA Crawler & Deep Detail Extractor (unclecode/crawl4AI)
  5. Naukri & Instahyre Scraper (Crawl4AI stealth mode)
  6. Startup & VC Talent Directory Scanner (Hacker News Who's Hiring, YC, VC Boards)
  7. Automated Link Liveness & Expired Job Cleaner (clean_expired_jobs.py)
  8. 1-Click Form Autofill Assistant (Playwright browser autofill)
  9. OpenXML Spreadsheet Sync & Formatter (opportunities.xlsx & opportunities.csv)

Usage:
  python job_pipeline.py --all        # Run all discovery tools + auto-sync to Excel
  python job_pipeline.py --apis       # Fast scan across all direct ATS and Remote APIs
  python job_pipeline.py --jobspy     # Scan LinkedIn and Indeed via python-jobspy
  python job_pipeline.py --crawl4ai   # Crawl dynamic JS/SPA portals via Crawl4AI
  python job_pipeline.py --naukri     # Crawl Naukri & Instahyre for early-career analyst roles
  python job_pipeline.py --startups   # Scan Hacker News & YC startup boards
  python job_pipeline.py --clean-dead # Verify link liveness & archive expired postings
  python job_pipeline.py --autofill 1 # Launch 1-click headed browser form filler for job #1
  python job_pipeline.py --stats      # Show summary counts across pipeline and tracker
"""

import os
import sys
import subprocess
import argparse
import csv
import json
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
PYTHON_BIN = os.path.join(PROJECT_ROOT, ".venv", "bin", "python")
if not os.path.exists(PYTHON_BIN):
    PYTHON_BIN = sys.executable

PIPELINE_FILE = os.path.join(PROJECT_ROOT, "data", "pipeline.md")
TRACKER_FILE = os.path.join(PROJECT_ROOT, "data", "applications.md")
OPPORTUNITIES_XLSX = os.path.join(PROJECT_ROOT, "opportunities.xlsx")
OPPORTUNITIES_CSV = os.path.join(PROJECT_ROOT, "opportunities.csv")

def run_cmd(cmd_list, description=""):
    if description:
        print(f"\n▶ {description}...")
    try:
        res = subprocess.run(cmd_list, cwd=PROJECT_ROOT, check=True)
        return res.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {e}")
        return False

def show_stats():
    print("=" * 60)
    print("               CAREER-OPS PIPELINE SUMMARY")
    print("=" * 60)
    
    # Opportunities count
    opp_count = 0
    if os.path.exists(OPPORTUNITIES_CSV):
        with open(OPPORTUNITIES_CSV, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            opp_count = max(0, sum(1 for _ in reader) - 1)
    print(f"• Active Opportunities (Excel/CSV): {opp_count} jobs")
    print(f"  File: {OPPORTUNITIES_XLSX}")
    print(f"  File: {OPPORTUNITIES_CSV}")

    # Pipeline pending count
    pending_count = 0
    if os.path.exists(PIPELINE_FILE):
        with open(PIPELINE_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("- [ ]"):
                    pending_count += 1
    print(f"• Pending Leads in Pipeline:       {pending_count} leads")
    print(f"  File: {PIPELINE_FILE}")

    # Applications tracker count
    applied_count = 0
    if os.path.exists(TRACKER_FILE):
        with open(TRACKER_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("|") and not line.strip().startswith("| #") and not line.strip().startswith("|---"):
                    applied_count += 1
    print(f"• Tracked Applications:            {applied_count} tracked")
    print(f"  File: {TRACKER_FILE}")
    print("=" * 60)

def main():
    parser = argparse.ArgumentParser(description="Career-Ops Multi-Tool Job Pipeline Runner")
    parser.add_argument("--apis", action="store_true", help="Run fast ATS & Remote APIs scanner")
    parser.add_argument("--jobspy", action="store_true", help="Run LinkedIn & Indeed JobSpy scraper")
    parser.add_argument("--crawl4ai", action="store_true", help="Run Crawl4AI dynamic portal crawler")
    parser.add_argument("--naukri", action="store_true", help="Run Naukri & Instahyre Crawl4AI scraper")
    parser.add_argument("--startups", action="store_true", help="Run Hacker News & YC startup scanner")
    parser.add_argument("--all", action="store_true", help="Run all tools: APIs + JobSpy + Crawl4AI + Naukri + Startups + sync")
    parser.add_argument("--clean-dead", action="store_true", help="Verify and clean dead/expired links")
    parser.add_argument("--autofill", type=str, help="Launch 1-click browser autofill for a row # or URL")
    parser.add_argument("--ats-full", action="store_true", help="Run reverse ATS directory scanner")
    parser.add_argument("--sync", action="store_true", help="Consolidate and style opportunities.xlsx")
    parser.add_argument("--auto-apply", type=int, nargs="?", const=5, help="Headlessly auto-apply to top N ATS jobs (default: 5)")
    parser.add_argument("--autonomous", action="store_true", help="Run 100% autonomous end-to-end pipeline (discover + clean + apply)")
    parser.add_argument("--stats", action="store_true", help="Show current pipeline numbers")
    args = parser.parse_args()

    # Default if no arguments provided: show help and stats
    has_action = any([
        args.apis, args.jobspy, args.crawl4ai, args.naukri, args.startups,
        args.all, args.clean_dead, args.autofill, getattr(args, "ats_full", False),
        args.sync, args.stats, args.auto_apply is not None, args.autonomous
    ])
    if not has_action:
        show_stats()
        print("\nCommands:")
        print("  python job_pipeline.py --autonomous    # 100% Hands-off: discover, clean, apply, and track")
        print("  python job_pipeline.py --auto-apply 5  # Headlessly auto-apply to top 5 verified ATS jobs")
        print("  python job_pipeline.py --all           # Run complete discovery suite across all channels")
        print("  python job_pipeline.py --apis          # Fast direct APIs (Greenhouse/Lever/SmartRecruiters)")
        print("  python job_pipeline.py --jobspy        # LinkedIn & Indeed JobSpy scraper")
        print("  python job_pipeline.py --crawl4ai      # Crawl4AI dynamic JS/SPA portals (Swiggy, PhonePe, etc.)")
        print("  python job_pipeline.py --naukri        # Naukri & Instahyre scraper (0-2 yrs Data/BI/DE)")
        print("  python job_pipeline.py --startups      # Hacker News 'Who is Hiring?' & YC directory")
        print("  python job_pipeline.py --clean-dead    # Scan and archive closed/expired job links")
        print("  python job_pipeline.py --sync          # Rebuild and style opportunities.xlsx")
        return

    if args.autonomous:
        run_cmd([PYTHON_BIN, "run_autonomous_pipeline.py"], "Running 100% Autonomous Pipeline")
        return

    if args.auto_apply is not None:
        batch_size = args.auto_apply if isinstance(args.auto_apply, int) else 5
        run_cmd([PYTHON_BIN, "auto_apply_bot.py", "--batch", str(batch_size)], f"Headless Auto-Applying to {batch_size} jobs")
        return

    if args.stats:
        show_stats()

    if args.autofill:
        run_cmd([PYTHON_BIN, "autofill_assistant.py", args.autofill], f"Autofilling application form for {args.autofill}")
        return

    if args.clean_dead:
        run_cmd([PYTHON_BIN, "clean_expired_jobs.py"], "Checking link liveness and cleaning dead postings")
        show_stats()
        return

    if args.apis:
        print("\n[Tool 1/5] Running Direct ATS & Remote APIs Scanner...")
        run_cmd([PYTHON_BIN, "daily_job_scanner.py", "--no-jobspy"], "Scanning Greenhouse, Lever, Ashby, SmartRecruiters, Remotive, Jobicy, Arbeitnow")

    if args.jobspy:
        print("\n[Tool 2/5] Running JobSpy Multi-Portal Scraper (LinkedIn & Indeed)...")
        run_cmd([PYTHON_BIN, "jobspy_scanner.py"], "Scraping LinkedIn and Indeed")

    if args.crawl4ai:
        print("\n[Tool 3/5] Running Crawl4AI Dynamic JS/SPA Crawler...")
        run_cmd([PYTHON_BIN, "crawl4ai_scanner.py"], "Crawling dynamic career portals with Crawl4AI")

    if args.naukri:
        print("\n[Tool 4/5] Running Naukri & Instahyre Crawl4AI Scraper...")
        run_cmd([PYTHON_BIN, "naukri_instahyre_scanner.py"], "Crawling Naukri and Instahyre")

    if args.startups:
        print("\n[Tool 5/5] Running Startup & VC Talent Directory Scanner...")
        run_cmd([PYTHON_BIN, "startup_vc_scanner.py"], "Scanning Hacker News & YC startups")

    if args.all:
        print("\n=== Running Complete Multi-Tool Job Discovery Suite ===")
        run_cmd([PYTHON_BIN, "daily_job_scanner.py", "--no-jobspy"], "Direct ATS & Remote APIs")
        run_cmd([PYTHON_BIN, "jobspy_scanner.py"], "JobSpy (LinkedIn & Indeed)")
        run_cmd([PYTHON_BIN, "crawl4ai_scanner.py"], "Crawl4AI Dynamic Portals")
        run_cmd([PYTHON_BIN, "naukri_instahyre_scanner.py"], "Naukri & Instahyre")
        run_cmd([PYTHON_BIN, "startup_vc_scanner.py"], "Startup & VC Directory")

    if getattr(args, "ats_full", False):
        print("\n=== Running Reverse-ATS Directory Scanner ===")
        run_cmd(["node", "scan-ats-full.mjs", "--limit", "100"], "Scanning public ATS directories")

    if args.sync or args.apis or args.jobspy or args.crawl4ai or args.naukri or args.startups or args.all:
        print("\n=== Synchronizing opportunities.xlsx and opportunities.csv ===")
        run_cmd([PYTHON_BIN, "opportunities_manager.py"], "Re-indexing and styling OpenXML spreadsheet")
        show_stats()

if __name__ == "__main__":
    main()
