#!/usr/bin/env python3
"""
autofill_assistant.py — Intelligent Form Autofill & Tailoring Assistant
Launches a real browser window with Playwright, navigates to the job posting,
and automatically pre-fills applicant info, screening dropdowns, and generates
grounded, tailored answers to open-ended essay questions.

Leaves the browser live in front of you so YOU review and press Submit.

Usage:
  python autofill_assistant.py <row_number>       # e.g., python autofill_assistant.py 5
  python autofill_assistant.py <job_url>          # e.g., python autofill_assistant.py https://jobs.lever.co/cred/...
"""

import os
import sys
import csv
import time
import re
from datetime import datetime
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

import config_loader
import tailor_engine

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
OPPORTUNITIES_CSV = os.path.join(PROJECT_ROOT, "opportunities.csv")
APPLICATIONS_MD = os.path.join(PROJECT_ROOT, "data", "applications.md")
STATUS_LOG_TSV = os.path.join(PROJECT_ROOT, "data", "status-log.tsv")

def resolve_target_info(arg):
    """Resolves target URL, company name, and job role from row index or raw URL."""
    company = "Company"
    role = "Software Role"
    url = arg

    try:
        idx = int(arg)
        if os.path.exists(OPPORTUNITIES_CSV):
            with open(OPPORTUNITIES_CSV, "r", encoding="utf-8") as f:
                reader = list(csv.DictReader(f))
                if 1 <= idx <= len(reader):
                    row = reader[idx - 1]
                    url = row.get("apply link", "").strip()
                    company = row.get("Firm name", "").strip() or "Company"
                    role = row.get("Job role", "").strip() or "Software Role"
                    return url, company, role
    except ValueError:
        pass

    # If raw URL, try to infer company from domain
    if "greenhouse.io" in url:
        m = re.search(r"greenhouse\.io/([^/]+)", url)
        if m:
            company = m.group(1).replace("-", " ").title()
    elif "lever.co" in url:
        m = re.search(r"lever\.co/([^/]+)", url)
        if m:
            company = m.group(1).replace("-", " ").title()
    elif "ashbyhq.com" in url:
        m = re.search(r"ashbyhq\.com/([^/]+)", url)
        if m:
            company = m.group(1).replace("-", " ").title()

    return url, company, role

def handle_react_selects(page, cand):
    """Handles custom React-select / Greenhouse combobox dropdowns."""
    try:
        controls = page.locator(".select__control").all()
        for ctrl in controls:
            try:
                parent = ctrl.locator("xpath=./ancestor::div[contains(@class, 'field') or contains(@class, 'question') or contains(@class, 'application--questions')][1]")
                txt = parent.inner_text().lower() if parent.count() > 0 else ""
                curr_val = ctrl.inner_text().lower()
                if "select..." not in curr_val and "select" not in curr_val and "united states" not in curr_val:
                    continue

                # Country code selector
                if "phone" in txt or "country" in txt or "iti" in txt:
                    ctrl.click()
                    page.wait_for_timeout(200)
                    india_opt = page.locator(".select__option:has-text('India +91')").first
                    if india_opt.count() > 0:
                        india_opt.click()
                        page.wait_for_timeout(200)
                        continue

                ctrl.click()
                page.wait_for_timeout(200)
                options = page.locator(".select__option").all()
                if not options:
                    continue

                chosen = None
                if any(w in txt for w in ["privacy", "acknowledge", "consent"]):
                    chosen = next((o for o in options if any(w in o.inner_text().lower() for w in ["acknowledge", "agree", "yes", "accept"])), options[0])
                elif any(w in txt for w in ["years of experience", "overall", "experience do you have"]):
                    chosen = next((o for o in options if any(w in o.inner_text().lower() for w in ["0-4", "0-2", "1-2", "1", "2"])), options[0])
                elif any(w in txt for w in ["sponsorship", "require visa"]):
                    chosen = next((o for o in options if o.inner_text().lower() == "no"), options[-1])
                elif any(w in txt for w in ["how soon", "joining", "join us"]):
                    chosen = next((o for o in options if any(w in o.inner_text().lower() for w in ["immediate", "15 days", "30 days"])), options[0])
                elif any(w in txt for w in ["authorized", "work in"]):
                    chosen = next((o for o in options if o.inner_text().lower() == "yes"), options[0])
                else:
                    chosen = next((o for o in options if "yes" in o.inner_text().lower()), options[0])

                if chosen:
                    chosen.click()
                    page.wait_for_timeout(200)
            except Exception:
                continue
    except Exception:
        pass

def fill_form(page, cand, company, role, jd_text=""):
    """Fills candidate contact, dropdowns, and injects tailored answers."""
    filled_count = 0

    # 1. Fill First Name
    for sel in ["#first_name", "input[name='first_name']", "input[name*='firstName']", "input[name='firstname']", "input[autocomplete='given-name']"]:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=500):
                el.fill(cand["first_name"])
                filled_count += 1
                break
        except Exception:
            pass

    # 2. Fill Last Name
    for sel in ["#last_name", "input[name='last_name']", "input[name*='lastName']", "input[name='lastname']", "input[autocomplete='family-name']"]:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=500):
                el.fill(cand["last_name"])
                filled_count += 1
                break
        except Exception:
            pass

    # 3. Fill Full Name
    for sel in ["input[name='name']", "#name", "input[name='full_name']", "input[autocomplete='name']"]:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=500):
                el.fill(cand["full_name"])
                filled_count += 1
                break
        except Exception:
            pass

    # 4. Fill Email
    for sel in ["input[type='email']", "#email", "input[name='email']", "input[name*='email']", "input[autocomplete='email']"]:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=500):
                el.fill(cand["email"])
                filled_count += 1
                break
        except Exception:
            pass

    # 5. Fill Phone
    for sel in ["input[type='tel']", "#phone", "input[name='phone']", "input[name*='phoneNumber']", "input[name*='phone']", "input[autocomplete='tel']"]:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=500):
                el.fill(cand["phone"])
                filled_count += 1
                break
        except Exception:
            pass

    # 6. Fill Organization / Current Company
    for sel in ["input[name='org']", "input[name*='current_company']", "input[name*='company']"]:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=500):
                el.fill(cand["current_org"])
                filled_count += 1
                break
        except Exception:
            pass

    # 7. Fill LinkedIn URL
    for sel in ["input[name*='linkedin' i]", "input[id*='linkedin' i]", "input[name*='urls[LinkedIn]']", "input[placeholder*='linkedin' i]"]:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=500):
                el.fill(cand["linkedin"])
                filled_count += 1
                break
        except Exception:
            pass

    # 8. Fill GitHub / Website URL
    for sel in ["input[name*='github' i]", "input[id*='github' i]", "input[name*='urls[GitHub]']", "input[placeholder*='github' i]", "input[name*='website' i]"]:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=500):
                el.fill(cand["github"])
                filled_count += 1
                break
        except Exception:
            pass

    # 9. Handle Custom React Select Dropdowns
    handle_react_selects(page, cand)

    # 10. Intelligent Textarea / Open-Ended Question Answering
    try:
        textareas = page.locator("textarea, div[contenteditable='true']").all()
        for ta in textareas:
            try:
                # Get surrounding context to understand what question is being asked
                aria = (ta.get_attribute("aria-label") or "").lower()
                ph = (ta.get_attribute("placeholder") or "").lower()
                name = (ta.get_attribute("name") or "").lower()
                parent = ta.locator("xpath=./ancestor::div[contains(@class, 'field') or contains(@class, 'question') or contains(@class, 'container')][1]")
                parent_txt = parent.inner_text().lower() if parent.count() > 0 else ""
                if not parent_txt:
                    parent_txt = ta.locator("xpath=../..").inner_text().lower()

                prompt_ctx = f"{aria} {ph} {name} {parent_txt}"
                
                # Check if already filled
                curr_val = ta.input_value() if ta.evaluate("el => el.tagName.toLowerCase()") == "textarea" else ta.inner_text()
                if curr_val and len(curr_val.strip()) > 5:
                    continue

                tailored_ans = tailor_engine.generate_tailored_answer(prompt_ctx, company, role, jd_text)
                if tailored_ans:
                    ta.fill(tailored_ans)
                    filled_count += 1
                    first_line = tailored_ans.split("\n")[0][:45]
                    print(f"  ✓ Injected tailored answer ({first_line}...)")
            except Exception:
                continue
    except Exception:
        pass

    # 11. Consent Checkboxes
    try:
        for cb in page.locator("input[type='checkbox']").all():
            try:
                cb.check(force=True)
            except Exception:
                pass
    except Exception:
        pass

    # 12. Auto-attach Tailored Resume if file input present
    resume_file = config_loader.find_resume_file(role)
    if resume_file:
        try:
            file_input = page.locator("input[type='file']").first
            if file_input.count() > 0:
                file_input.set_input_files(resume_file)
                print(f"  ✓ Attached tailored resume: {os.path.basename(resume_file)} (Matched role: '{role}')")
                filled_count += 1
        except Exception:
            pass

    return filled_count

def log_applied_status(company, role, url):
    """Records the submitted application into data/applications.md and data/status-log.tsv"""
    today = datetime.now().strftime("%Y-%m-%d")
    max_num = 42
    if os.path.exists(APPLICATIONS_MD):
        with open(APPLICATIONS_MD, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("|"):
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) >= 2 and parts[1].isdigit():
                        max_num = max(max_num, int(parts[1]))

    next_num = f"{max_num + 1:03d}"
    note = "Applied via 1-Click Tailored Assistant."
    
    # Append row
    new_row = f"| {next_num} | {today} | {company} | {role} | 4.0 | Applied | ❌ | | {note} |\n"
    os.makedirs(os.path.dirname(APPLICATIONS_MD), exist_ok=True)
    with open(APPLICATIONS_MD, "a", encoding="utf-8") as f:
        f.write(new_row)

    # Append to status-log.tsv
    with open(STATUS_LOG_TSV, "a", encoding="utf-8") as f:
        f.write(f"{next_num}\t{today}\t-\tApplied\tset-status\t{note}\n")

    print(f"\n🎉 Successfully tracked application #{next_num}: [{company}] {role} marked as Applied!")

def run_assistant(target_arg):
    cand = config_loader.get_candidate_profile()
    url, company, role = resolve_target_info(target_arg)

    if not url.startswith("http"):
        print(f"Error: Invalid URL or row reference: {target_arg}")
        print("Usage: python autofill_assistant.py <row_number_or_url>")
        return

    print("=" * 65)
    print("      🚀 INTELLIGENT TAILORED APPLICATION ASSISTANT")
    print("=" * 65)
    print(f"Candidate:  {cand['full_name']} ({cand['email']})")
    print(f"Target:     {company} — {role}")
    print(f"URL:        {url}")
    print("-" * 65)
    if sync_playwright is None:
        print("Error: Playwright Python library is not installed in this environment.")
        print("Please install with: pip install playwright && playwright install chromium")
        return

    print("Launching Chromium headed browser...")

    with sync_playwright() as p:
        # 1. Attempt to connect to an existing running browser via CDP (port 9222)
        context = None
        browser = None
        try:
            browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222", timeout=2000)
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            print("✓ Connected to your active browser session via CDP (port 9222)!")
        except Exception:
            pass

        # 2. If no active CDP session, launch persistent context so logins/cookies are preserved
        if context is None:
            profile_dir = os.path.expanduser("~/.config/autojobhunt-browser-profile")
            os.makedirs(profile_dir, exist_ok=True)
            print(f"Using persistent browser profile (cookies & logins preserved across sessions): {profile_dir}")
            context = p.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                headless=False,
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

        # Extract JD text from page for tailoring
        try:
            jd_text = page.locator("body").inner_text()
        except Exception:
            jd_text = ""

        # Click Apply button to reveal form if needed
        for btn_sel in ["a[href*='#apply']", "button:has-text('Apply')", "a:has-text('Apply')", "button:has-text('Apply Now')", "a:has-text('Apply for this job')"]:
            try:
                btn = page.locator(btn_sel).first
                if btn.is_visible(timeout=1000):
                    btn.click()
                    time.sleep(1)
                    break
            except Exception:
                pass

        print("Pre-filling candidate fields & generating tailored answers...")
        count = fill_form(page, cand, company, role, jd_text)
        print(f"✓ Form populated successfully ({count} fields completed)!")

        print("\n" + "=" * 65)
        print("✨ EVERYTHING IS PRE-FILLED & TAILORED IN YOUR OPEN BROWSER!")
        print("👉 Review the answers, make any personal adjustments you'd like,")
        print("   and press [Submit Application] when ready.")
        print("=" * 65 + "\n")

        try:
            input("👉 Press [ENTER] in this terminal when finished reviewing/submitting...")
        except (KeyboardInterrupt, EOFError):
            pass

        try:
            submitted = input("\nDid you submit the application? [y/N]: ").strip().lower()
            if submitted in ["y", "yes"]:
                log_applied_status(company, role, url)
        except (KeyboardInterrupt, EOFError):
            pass

        try:
            if context:
                context.close()
            elif browser:
                browser.close()
        except Exception:
            pass
        print("Browser session closed.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python autofill_assistant.py <row_number_or_url>")
        print("Example: python autofill_assistant.py 1")
        sys.exit(1)
    run_assistant(sys.argv[1])
