#!/usr/bin/env python3
"""
autofill_assistant.py — 1-Click Form Autofill Assistant for Job Applications
Launches a real browser window with Playwright, opens the job posting,
and automatically pre-fills standard candidate application fields.

Compatible ATS Platforms:
  - Greenhouse (boards.greenhouse.io / job-boards.greenhouse.io)
  - Lever (jobs.lever.co)
  - Ashby (jobs.ashbyhq.com)
  - SmartRecruiters (jobs.smartrecruiters.com)
  - Generic / Custom Career application forms

Usage:
  python autofill_assistant.py <row_number>       # e.g., python autofill_assistant.py 5
  python autofill_assistant.py <job_url>          # e.g., python autofill_assistant.py https://jobs.lever.co/cred/...
"""

import os
import sys
import csv
import time
import yaml
from playwright.sync_api import sync_playwright

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
PROFILE_YML = os.path.join(PROJECT_ROOT, "config", "profile.yml")
OPPORTUNITIES_CSV = os.path.join(PROJECT_ROOT, "opportunities.csv")

import config_loader

# Candidate Defaults from config_loader
CANDIDATE = config_loader.get_candidate_profile()

def load_candidate_profile():
    global CANDIDATE
    CANDIDATE = config_loader.get_candidate_profile()
    return CANDIDATE

def resolve_target_url(arg):
    if arg.startswith("http://") or arg.startswith("https://"):
        return arg, "Target Job"

    # Try resolving row index from opportunities.csv
    try:
        idx = int(arg)
        if os.path.exists(OPPORTUNITIES_CSV):
            with open(OPPORTUNITIES_CSV, "r", encoding="utf-8") as f:
                reader = list(csv.DictReader(f))
                if 1 <= idx <= len(reader):
                    row = reader[idx - 1]
                    url = row.get("apply link", "").strip()
                    desc = f"#{idx}: {row.get('Firm name')} - {row.get('Job role')}"
                    return url, desc
    except ValueError:
        pass

    return arg, "Target Job"

def find_resume_file():
    return config_loader.find_resume_file()


def fill_form(page, cand):
    filled_count = 0

    # 1. Fill First Name
    first_name_selectors = [
        "#first_name", "input[name='first_name']", "input[name*='firstName']",
        "input[name='firstname']", "input[autocomplete='given-name']"
    ]
    for sel in first_name_selectors:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=500):
                el.fill(cand["first_name"])
                filled_count += 1
                break
        except Exception:
            pass

    # 2. Fill Last Name
    last_name_selectors = [
        "#last_name", "input[name='last_name']", "input[name*='lastName']",
        "input[name='lastname']", "input[autocomplete='family-name']"
    ]
    for sel in last_name_selectors:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=500):
                el.fill(cand["last_name"])
                filled_count += 1
                break
        except Exception:
            pass

    # 3. Fill Full Name (Lever / Ashby / Generic)
    full_name_selectors = [
        "input[name='name']", "#name", "input[name='full_name']", "input[autocomplete='name']"
    ]
    for sel in full_name_selectors:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=500):
                el.fill(cand["full_name"])
                filled_count += 1
                break
        except Exception:
            pass

    # 4. Fill Email
    email_selectors = [
        "input[type='email']", "#email", "input[name='email']", "input[name*='email']", "input[autocomplete='email']"
    ]
    for sel in email_selectors:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=500):
                el.fill(cand["email"])
                filled_count += 1
                break
        except Exception:
            pass

    # 5. Fill Phone
    phone_selectors = [
        "input[type='tel']", "#phone", "input[name='phone']", "input[name*='phoneNumber']",
        "input[name*='phone']", "input[autocomplete='tel']"
    ]
    for sel in phone_selectors:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=500):
                el.fill(cand["phone"])
                filled_count += 1
                break
        except Exception:
            pass

    # 6. Fill Organization / Current Company
    org_selectors = ["input[name='org']", "input[name*='current_company']", "input[name*='company']"]
    for sel in org_selectors:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=500):
                el.fill(cand["current_org"])
                filled_count += 1
                break
        except Exception:
            pass

    # 7. Fill LinkedIn URL
    linkedin_selectors = [
        "input[name*='linkedin' i]", "input[id*='linkedin' i]", "input[name*='urls[LinkedIn]']",
        "input[placeholder*='linkedin' i]"
    ]
    for sel in linkedin_selectors:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=500):
                el.fill(cand["linkedin"])
                filled_count += 1
                break
        except Exception:
            pass

    # 8. Fill GitHub / Website URL
    github_selectors = [
        "input[name*='github' i]", "input[id*='github' i]", "input[name*='urls[GitHub]']",
        "input[placeholder*='github' i]", "input[name*='website' i]"
    ]
    for sel in github_selectors:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=500):
                el.fill(cand["github"])
                filled_count += 1
                break
        except Exception:
            pass

    # 9. Auto-attach Resume if file input present
    resume_file = find_resume_file()
    if resume_file:
        try:
            file_input = page.locator("input[type='file']").first
            if file_input.count() > 0:
                file_input.set_input_files(resume_file)
                print(f"  ✓ Attached resume file: {os.path.basename(resume_file)}")
                filled_count += 1
        except Exception:
            pass

    return filled_count

def run_assistant(target_arg):
    cand = load_candidate_profile()
    url, label = resolve_target_url(target_arg)

    if not url.startswith("http"):
        print(f"Error: Invalid URL or row reference: {target_arg}")
        print("Usage: python autofill_assistant.py <row_number_or_url>")
        return

    print("==================================================")
    print("   1-CLICK APPLICATION AUTOFILL ASSISTANT")
    print("==================================================")
    print(f"Candidate:  {cand['full_name']} ({cand['email']})")
    print(f"Target:     {label}")
    print(f"URL:        {url}")
    print("--------------------------------------------------")
    print("Launching Chromium headed browser...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        print(f"Navigating to {url}...")
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(2)
        except Exception as e:
            print(f"Navigation note: {e}")

        # If it's a page with an "Apply" or "Apply for this job" button, click it to scroll down
        apply_buttons = [
            "a[href*='#apply']", "button:has-text('Apply')", "a:has-text('Apply')",
            "button:has-text('Apply Now')", "a:has-text('Apply for this job')"
        ]
        for btn_sel in apply_buttons:
            try:
                btn = page.locator(btn_sel).first
                if btn.is_visible(timeout=1000):
                    btn.click()
                    time.sleep(1)
                    break
            except Exception:
                pass

        # Fill standard form fields
        print("Pre-filling candidate fields (Name, Email, Phone, LinkedIn, GitHub)...")
        count = fill_form(page, cand)
        print(f"✓ Form pre-filled successfully ({count} fields populated)!")

        print("\n" + "=" * 60)
        print("👉 The browser window is OPEN and pre-filled with your details.")
        print("👉 Review answers, make any final adjustments, and submit.")
        print("👉 Press [ENTER] in this terminal when finished to close.")
        print("=" * 60 + "\n")

        try:
            input("Press Enter to close browser session...")
        except (KeyboardInterrupt, EOFError):
            pass

        browser.close()
        print("Browser session closed.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python autofill_assistant.py <row_number_or_url>")
        print("Example: python autofill_assistant.py 1")
        sys.exit(1)
    run_assistant(sys.argv[1])
