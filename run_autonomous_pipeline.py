#!/usr/bin/env python3
"""
run_autonomous_pipeline.py — End-to-End Autonomous Job Hunt Daemon & Runner

Runs the complete job acquisition pipeline with ZERO manual intervention:
  1. Discovery: Direct ATS APIs, JobSpy, Crawl4AI, Naukri, Startups
  2. Cleaning: Rapid concurrent link health check & dead-posting pruner
  3. Re-indexing: OpenXML spreadsheet compilation (opportunities.xlsx)
  4. Auto-Apply: Headless Playwright form filler & submitter for ATS roles
  5. Tracking: Syncs data/applications.md, status-log.tsv, and captures screenshot proofs

Usage:
  python run_autonomous_pipeline.py              # Full autonomous run
  python run_autonomous_pipeline.py --quick      # Fast scan (APIs only) + clean + apply
  python run_autonomous_pipeline.py --apply-only # Only run auto-apply on pending jobs
"""

import os
import sys
import subprocess
import argparse
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
PYTHON_BIN = os.path.join(PROJECT_ROOT, ".venv", "bin", "python")
if not os.path.exists(PYTHON_BIN):
    PYTHON_BIN = sys.executable

LOG_FILE = os.path.join(PROJECT_ROOT, "data", "autonomous_run.log")

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    print(formatted)
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except Exception:
        pass

def run_step(cmd_list, name):
    log(f"▶ STARTING: {name}")
    try:
        res = subprocess.run(cmd_list, cwd=PROJECT_ROOT)
        if res.returncode == 0:
            log(f"✓ COMPLETED: {name}")
            return True
        else:
            log(f"⚠️ STEP FAILED (code {res.returncode}): {name}")
            return False
    except Exception as e:
        log(f"❌ EXCEPTION in {name}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Zero-Manual Autonomous Job Pipeline")
    parser.add_argument("--quick", action="store_true", help="Fast discovery (APIs only) + apply")
    parser.add_argument("--apply-only", action="store_true", help="Skip discovery, run auto-apply")
    parser.add_argument("--apply-batch", type=int, default=5, help="Number of jobs to auto-apply")
    parser.add_argument("--dry-run", action="store_true", help="Fill forms without final submit")
    args = parser.parse_args()

    log("=" * 60)
    log("🚀 CAREER-OPS AUTONOMOUS PIPELINE RUN STARTED")
    log("=" * 60)

    if not args.apply_only:
        # --- STAGE 1: DISCOVERY ---
        log("\n--- STAGE 1: MULTI-CHANNEL DISCOVERY ---")
        run_step([PYTHON_BIN, "daily_job_scanner.py", "--no-jobspy"], "Direct ATS & Remote Tech APIs")

        if not args.quick:
            run_step([PYTHON_BIN, "jobspy_scanner.py"], "JobSpy Scraper (LinkedIn & Indeed)")
            run_step([PYTHON_BIN, "crawl4ai_scanner.py"], "Crawl4AI Dynamic SPA Crawler")
            run_step([PYTHON_BIN, "naukri_instahyre_scanner.py"], "Naukri & Instahyre Scraper")
            run_step([PYTHON_BIN, "startup_vc_scanner.py"], "Startup & VC Talent Scanner")

        # --- STAGE 2: CLEANING & LIVENESS ---
        log("\n--- STAGE 2: LINK HEALTH CHECK & DEAD POSTING CLEANER ---")
        run_step([PYTHON_BIN, "clean_expired_jobs.py"], "Concurrent Link Liveness Verification")

        # --- STAGE 3: SPREADSHEET RE-INDEXING ---
        log("\n--- STAGE 3: OPENXML SPREADSHEET SYNC ---")
        run_step([PYTHON_BIN, "opportunities_manager.py"], "Compiling opportunities.xlsx & opportunities.csv")

    # --- STAGE 4: AUTONOMOUS APPLICATION SUBMISSION ---
    log("\n--- STAGE 4: ZERO-MANUAL HEADLESS AUTO-APPLY ---")
    apply_cmd = [PYTHON_BIN, "auto_apply_bot.py", "--batch", str(args.apply_batch)]
    if args.dry_run:
        apply_cmd.append("--dry-run")
    run_step(apply_cmd, f"Headless Auto-Apply (Batch: {args.apply_batch})")

    # --- STAGE 5: REPORT SUMMARY ---
    log("\n--- STAGE 5: SUMMARY & AUDIT ---")
    run_step([PYTHON_BIN, "job_pipeline.py", "--stats"], "Pipeline Stats")

    log("=" * 60)
    log("🏁 AUTONOMOUS PIPELINE CYCLE COMPLETED SUCCESSFULLY")
    log("=" * 60 + "\n")

if __name__ == "__main__":
    main()
