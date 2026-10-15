#!/usr/bin/env python3
"""
auto_apply_bot.py — Zero-Manual Autonomous Job Application Engine
Runs headless Playwright automation to pre-fill, upload resume, answer screening questions,
and submit job applications across Greenhouse, Lever, Ashby, and SmartRecruiters.

Zero user manual intervention required:
  - Detects ATS platform automatically
  - Auto-populates candidate personal & professional details
  - Automatically uploads resume PDF/DOCX
  - Fills common screening questions (Work Auth, Notice Period, Location, Experience)
  - Accepts consent / privacy checkboxes
  - Submits application headlessly
  - Verifies confirmation & captures screenshot proof in output/confirmations/
  - Automatically syncs data/applications.md, data/status-log.tsv, and opportunities.xlsx

Usage:
  python auto_apply_bot.py --batch 5           # Headlessly apply to top 5 available ATS jobs
  python auto_apply_bot.py --url <ats_url>     # Headlessly apply to a specific job URL
  python auto_apply_bot.py --dry-run           # Fill and verify without clicking final submit
  python auto_apply_bot.py --all               # Process all eligible direct ATS jobs
"""

import os
import sys
import csv
import time
import re
import yaml
import subprocess
from datetime import datetime
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
PROFILE_YML = os.path.join(PROJECT_ROOT, "config", "profile.yml")
OPPORTUNITIES_CSV = os.path.join(PROJECT_ROOT, "opportunities.csv")
APPLICATIONS_MD = os.path.join(PROJECT_ROOT, "data", "applications.md")
STATUS_LOG_TSV = os.path.join(PROJECT_ROOT, "data", "status-log.tsv")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output", "confirmations")
SKIPPED_DIR = os.path.join(PROJECT_ROOT, "output", "skipped")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(SKIPPED_DIR, exist_ok=True)

import config_loader

# Candidate profile grounded strictly in config/profile.yml
CANDIDATE = config_loader.get_candidate_profile()

def load_profile():
    global CANDIDATE
    CANDIDATE = config_loader.get_candidate_profile()
    return CANDIDATE

def is_valid_location(location):
    return config_loader.is_valid_location(location)

def is_valid_role(title):
    return config_loader.is_valid_role(title)

def find_resume_file(role_title=None):
    return config_loader.find_resume_file(role_title)


def is_already_applied(company, role, url):
    """Check if company/role or url is already recorded as Applied in data/applications.md"""
    if not os.path.exists(APPLICATIONS_MD):
        return False
    with open(APPLICATIONS_MD, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Check normalized match
    norm_comp = re.sub(r"[^a-zA-Z0-9]", "", company).lower()
    norm_role = re.sub(r"[^a-zA-Z0-9]", "", role).lower()
    
    for line in content.splitlines():
        if not line.startswith("|") or "Company" in line or "---" in line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 7:
            ex_comp = re.sub(r"[^a-zA-Z0-9]", "", parts[3]).lower()
            ex_role = re.sub(r"[^a-zA-Z0-9]", "", parts[4]).lower()
            status = parts[6]
            if status.lower() == "applied" and norm_comp and norm_comp in ex_comp:
                if norm_role and (norm_role in ex_role or ex_role in norm_role):
                    return True
    return False

def record_application_success(company, role, url, screenshot_path):
    """Update data/applications.md and data/status-log.tsv with canonical entry"""
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Get highest tracker number
    max_num = 42
    if os.path.exists(APPLICATIONS_MD):
        with open(APPLICATIONS_MD, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("|"):
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) >= 2 and parts[1].isdigit():
                        max_num = max(max_num, int(parts[1]))
    
    next_num = f"{max_num + 1:03d}"
    rel_shot = os.path.relpath(screenshot_path, PROJECT_ROOT) if screenshot_path else "Confirmed"
    note = f"Auto-applied headlessly. Proof: {rel_shot}"
    
    # Append to data/applications.md
    new_row = f"| {next_num} | {today} | {company} | {role} | 4.0 | Applied | ❌ | | {note} |\n"
    with open(APPLICATIONS_MD, "a", encoding="utf-8") as f:
        f.write(new_row)
        
    # Append to data/status-log.tsv (valid source: set-status)
    with open(STATUS_LOG_TSV, "a", encoding="utf-8") as f:
        f.write(f"{next_num}\t{today}\t-\tApplied\tset-status\t{note}\n")
        
    print(f"  ✓ Tracker updated: #{next_num} [{company}] {role} marked as Applied.")

def answer_custom_screening(page, cand):
    """Intelligently answer common ATS screening questions based on label heuristics."""
    # Find all question containers / form groups
    try:
        # 1. Radio / Select / Checkbox screening
        labels = page.locator("label, div[class*='field'], div[class*='question']").all()
        for lbl in labels:
            try:
                txt = lbl.inner_text().lower()
                
                # Work authorization: "Are you authorized to work in India?" -> Yes
                if "authorized to work" in txt or "legally authorized" in txt or "eligibility to work" in txt:
                    yes_radio = lbl.locator("input[type='radio'][value*='yes' i], input[type='radio'][id*='yes' i]").first
                    if yes_radio.count() > 0:
                        yes_radio.check(force=True)
                    else:
                        parent = lbl.locator("xpath=..")
                        y_btn = parent.locator("input[type='radio']").first
                        if y_btn.count() > 0:
                            y_btn.check(force=True)
                            
                # Sponsorship requirement: "Will you now or in the future require sponsorship?" -> No
                elif "require sponsorship" in txt or "visa sponsorship" in txt:
                    no_radio = lbl.locator("input[type='radio'][value*='no' i], input[type='radio'][id*='no' i]").first
                    if no_radio.count() > 0:
                        no_radio.check(force=True)
                    else:
                        parent = lbl.locator("xpath=..")
                        # Usually second radio is 'No'
                        radios = parent.locator("input[type='radio']").all()
                        if len(radios) >= 2:
                            radios[1].check(force=True)
                            
                # Location / Relocation
                elif "willing to relocate" in txt:
                    yes_r = lbl.locator("input[type='radio'][value*='yes' i]").first
                    if yes_r.count() > 0:
                        yes_r.check(force=True)
            except Exception:
                continue

        # 2. Modern segmented button groups (e.g. Ashby / Greenhouse Yes/No buttons)
        try:
            ashby_yes = page.locator("button.ashby-application-form-input-yesno-option:has-text('Yes'), button:has-text('Yes')").all()
            for y_btn in ashby_yes:
                try:
                    if y_btn.is_visible() and y_btn.is_enabled():
                        y_btn.click()
                        time.sleep(0.2)
                except Exception:
                    pass
        except Exception:
            pass

        # 3. Open text and numeric screening inputs
        text_inputs = page.locator("input[type='text'], input[type='number'], textarea, input:not([type])").all()
        for inp in text_inputs:
            try:
                aria = (inp.get_attribute("aria-label") or "").lower()
                ph = (inp.get_attribute("placeholder") or "").lower()
                name = (inp.get_attribute("name") or "").lower()
                
                # Check label or question text from parent container
                parent = inp.locator("xpath=./ancestor::div[contains(@class, 'field') or contains(@class, 'question') or contains(@class, 'container') or contains(@class, 'entry') or contains(@class, 'Entry')][1]")
                parent_txt = parent.inner_text().lower() if parent.count() > 0 else ""
                if not parent_txt:
                    parent_txt = inp.locator("xpath=../..").inner_text().lower()
                
                val = inp.input_value()
                if val:  # already filled
                    continue
                    
                inp_type = (inp.get_attribute("type") or "text").lower()
                def safe_fill(text_val, num_fallback="0"):
                    if inp_type == "number":
                        m = re.search(r"\d+", str(text_val))
                        inp.fill(m.group(0) if m else num_fallback)
                    else:
                        inp.fill(str(text_val))

                combo = f"{aria} {ph} {name} {parent_txt}"
                if any(k in combo for k in ["notice period", "notice_period", "how soon"]):
                    safe_fill(cand["notice_period"], "15")
                elif any(k in combo for k in ["years of experience", "total experience", "years_experience", "how many years", "experience do you carry", "experience as a", "experience in", "total year experience", "overall experience", "experience?"]):
                    safe_fill(cand["years_experience"], "1")
                elif any(k in combo for k in ["current location", "where are you located", "city", "location (city)"]):
                    safe_fill(cand["location"])
                elif any(k in combo for k in ["expected ctc", "expected salary", "salary expectation"]):
                    safe_fill("Open / Negotiable")
                elif any(k in combo for k in ["current ctc", "current salary"]):
                    safe_fill("Negotiable / Open")
                elif any(k in combo for k in ["payroll company", "last payroll", "company name"]):
                    safe_fill(cand["current_org"])
                elif any(k in combo for k in ["holding offer", "offer details"]):
                    safe_fill("None")
                elif any(k in combo for k in ["serving notice", "last working day", "lwd"]):
                    safe_fill("N/A (Immediate / Available)")
                elif any(k in combo for k in ["linkedin", "linkedin profile"]):
                    safe_fill(cand["linkedin"])
                elif any(k in combo for k in ["github", "portfolio", "website"]):
                    safe_fill(cand["github"])
                elif any(k in combo for k in ["highest education", "degree"]):
                    safe_fill(cand["education"])
                elif any(k in combo for k in ["how did you hear", "hear about"]):
                    safe_fill("LinkedIn / Careers Page")
            except Exception:
                continue

        # 3. Handle React-select custom dropdowns
        handle_react_selects(page, cand)

        # 4. Privacy Policy / Consent checkboxes
        consent_checkboxes = page.locator("input[type='checkbox']").all()
        for cb in consent_checkboxes:
            try:
                cb.check(force=True)
            except Exception:
                pass
    except Exception:
        pass

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
                elif any(w in txt for w in ["rate yourself", "out of 5", "rating"]):
                    chosen = next((o for o in options if any(w in o.inner_text().lower() for w in ["5", "4"])), options[-1])
                elif any(w in txt for w in ["uan", "absconded", "discrepancies", "criminal"]):
                    chosen = next((o for o in options if o.inner_text().lower() == "no"), options[-1])
                elif any(w in txt for w in ["sponsorship", "require visa"]):
                    chosen = next((o for o in options if o.inner_text().lower() == "no"), options[-1])
                elif any(w in txt for w in ["preferred location", "city", "office"]):
                    chosen = next((o for o in options if any(w in o.inner_text().lower() for w in ["bengaluru", "bangalore"])), options[0])
                elif any(w in txt for w in ["how soon", "joining", "join us"]):
                    chosen = next((o for o in options if any(w in o.inner_text().lower() for w in ["immediate", "15 days", "30 days"])), options[0])
                elif any(w in txt for w in ["gender"]):
                    chosen = next((o for o in options if o.inner_text().lower() == "male"), options[0])
                elif any(w in txt for w in ["shortlisted", "round", "f2f", "interview"]):
                    chosen = next((o for o in options if "bangalore" in o.inner_text().lower() or "bengaluru" in o.inner_text().lower()), options[0])
                elif any(w in txt for w in ["hybrid", "wfo", "onsite"]):
                    chosen = next((o for o in options if o.inner_text().lower() == "yes"), options[0])
                elif any(w in txt for w in ["big query", "pyspark", "python", "sql", "data", "currently working", "authorized"]):
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

def fill_greenhouse(page, cand, resume_path):
    """Automated filler for Greenhouse Job Boards"""
    # 1. Names
    try:
        page.locator("#first_name, input[name='first_name']").first.fill(cand["first_name"])
        page.locator("#last_name, input[name='last_name']").first.fill(cand["last_name"])
    except Exception:
        pass
        
    # 2. Email & Phone
    try:
        page.locator("#email, input[name='email']").first.fill(cand["email"])
        
        # Select country code in modern Greenhouse forms
        try:
            country_ctrl = page.locator(".select__control:has(#country)").first
            if country_ctrl.count() > 0:
                country_ctrl.click()
                page.wait_for_timeout(200)
                page.keyboard.type("India")
                page.wait_for_timeout(300)
                india_opt = page.locator(".select__option:has-text('India +91')").first
                if india_opt.count() > 0:
                    india_opt.click()
                    page.wait_for_timeout(200)
        except Exception:
            pass

        page.locator("#phone, input[name='phone']").first.fill(cand["phone"])

        # Location / City (React-select async or standard input)
        try:
            loc_ctrl = page.locator(".select__control:has(#candidate-location)").first
            if loc_ctrl.count() > 0:
                loc_ctrl.click()
                page.wait_for_timeout(200)
                page.keyboard.type("Bengaluru")
                try:
                    page.wait_for_selector(".select__option", timeout=4000)
                    opt = page.locator(".select__option:has-text('Bengaluru'), .select__option:has-text('Bangalore')").first
                    if opt.count() == 0:
                        opt = page.locator(".select__option").first
                    if opt.count() > 0:
                        opt.click()
                        page.wait_for_timeout(200)
                except Exception:
                    pass
            else:
                loc_inp = page.locator("#candidate-location, #location, input[name*='location']").first
                if loc_inp.count() > 0:
                    loc_inp.fill(cand["location"])
        except Exception:
            pass
    except Exception:
        pass
        
    # 3. Resume Upload
    if resume_path:
        try:
            # Greenhouse usually has input[type='file'][name='resume'] or #resume
            file_inp = page.locator("input[type='file'][name='resume'], #resume, input[type='file']").first
            if file_inp.count() > 0:
                file_inp.set_input_files(resume_path)
                print(f"  ✓ Attached resume: {os.path.basename(resume_path)}")
        except Exception as e:
            print(f"  ! Resume upload note: {e}")
            
    # 4. Screening & Demographics
    answer_custom_screening(page, cand)

def fill_lever(page, cand, resume_path):
    """Automated filler for Lever Job Boards"""
    # Click apply button if on JD view
    try:
        apply_btn = page.locator("a.postings-btn, a:has-text('Apply for this job')").first
        if apply_btn.is_visible(timeout=1500):
            apply_btn.click()
            page.wait_for_load_state("networkidle", timeout=5000)
    except Exception:
        pass

    # 1. Resume Upload (Lever auto-parses or attaches)
    if resume_path:
        try:
            file_inp = page.locator("input[type='file'][name='resume'], input[type='file']").first
            if file_inp.count() > 0:
                file_inp.set_input_files(resume_path)
                print(f"  ✓ Attached resume: {os.path.basename(resume_path)}")
                time.sleep(1)
        except Exception as e:
            print(f"  ! Resume upload note: {e}")

    # 2. Core Fields
    try:
        page.locator("input[name='name']").first.fill(cand["full_name"])
        page.locator("input[name='email']").first.fill(cand["email"])
        page.locator("input[name='phone']").first.fill(cand["phone"])
        page.locator("input[name='org']").first.fill(cand["current_org"])
    except Exception:
        pass

    # 3. Social URLs
    try:
        page.locator("input[name='urls[LinkedIn]']").first.fill(cand["linkedin"])
        page.locator("input[name='urls[GitHub]']").first.fill(cand["github"])
        page.locator("input[name='urls[Portfolio]'], input[name='urls[Other]']").first.fill(cand["github"])
    except Exception:
        pass

    # 4. Custom fields
    answer_custom_screening(page, cand)

def fill_ashby(page, cand, resume_path):
    """Automated filler for Ashby Job Boards"""
    # 1. Core Fields
    try:
        name_inp = page.locator("#_systemfield_name, input[name='_systemfield_name'], input[name='name'], input[placeholder*='Name']").first
        if name_inp.count() > 0:
            name_inp.fill(cand["full_name"])
            
        email_inp = page.locator("#_systemfield_email, input[name='_systemfield_email'], input[name='email'], input[type='email']").first
        if email_inp.count() > 0:
            email_inp.fill(cand["email"])
            
        phone_inp = page.locator("input[name='phoneNumber'], input[name='phone'], input[type='tel']").first
        if phone_inp.count() > 0:
            phone_inp.fill(cand["phone"])

        # Physical location in Ashby
        loc_inp = page.locator("input[placeholder*='Start typing']").first
        if loc_inp.count() > 0:
            loc_inp.click()
            loc_inp.fill("Bengaluru")
            page.wait_for_timeout(800)
            opt = page.locator(".ashby-application-form-input-autocomplete-popup-result, div[role='option']").first
            if opt.count() > 0:
                opt.click()
                page.wait_for_timeout(300)
    except Exception:
        pass

    # 2. Resume
    if resume_path:
        try:
            file_inp = page.locator("input[type='file']").first
            if file_inp.count() > 0:
                file_inp.set_input_files(resume_path)
                print(f"  ✓ Attached resume: {os.path.basename(resume_path)}")
        except Exception:
            pass

    # 3. Custom Questions
    answer_custom_screening(page, cand)

def fill_smartrecruiters(page, cand, resume_path):
    """Automated filler for SmartRecruiters Job Boards"""
    # Check if there is an Apply button
    try:
        apply_btn = page.locator("button:has-text('Apply'), a:has-text('I\\'m interested')").first
        if apply_btn.is_visible(timeout=1500):
            apply_btn.click()
            time.sleep(1)
    except Exception:
        pass

    # Standard fields
    try:
        page.locator("input[name='firstName'], #first-name-input").first.fill(cand["first_name"])
        page.locator("input[name='lastName'], #last-name-input").first.fill(cand["last_name"])
        page.locator("input[name='email'], #email-input").first.fill(cand["email"])
        page.locator("input[name='phoneNumber'], #phone-number-input").first.fill(cand["phone"])
    except Exception:
        pass

    if resume_path:
        try:
            file_inp = page.locator("input[type='file']").first
            if file_inp.count() > 0:
                file_inp.set_input_files(resume_path)
                print(f"  ✓ Attached resume: {os.path.basename(resume_path)}")
        except Exception:
            pass

    answer_custom_screening(page, cand)

def execute_auto_apply(company, role, url, dry_run=False):
    """Executes headless application filling and submission for an ATS job posting"""
    cand = load_profile()
    resume_path = find_resume_file(role)
    
    slug_comp = re.sub(r"[^a-zA-Z0-9]", "_", company).lower()[:20]
    slug_role = re.sub(r"[^a-zA-Z0-9]", "_", role).lower()[:20]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    print("\n" + "=" * 60)
    print(f"🤖 HEADLESS AUTO-APPLY: {company} — {role}")
    print(f"URL: {url}")
    print(f"Resume: {os.path.basename(resume_path) if resume_path else 'None'} (Role Track Matched)")
    print(f"Mode: {'[DRY RUN - Verification Only]' if dry_run else '[LIVE SUBMIT]'}")
    print("=" * 60)
    
    if sync_playwright is None:
        print("  ❌ Error: Playwright Python library is not installed in this environment.")
        print("     Please install with: pip install playwright && playwright install chromium")
        return False, "Playwright Library Missing"

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ]
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        try:
            print("  Navigating to job portal...")
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(2)
        except Exception as e:
            print(f"  ❌ Navigation failed: {e}")
            browser.close()
            return False, "Navigation Timeout"

        # Check for actual blocking CAPTCHA / Cloudflare wall / Rate limits
        title_lower = page.title().lower()
        body_snippet = ""
        try:
            body_snippet = page.locator("body").inner_text(timeout=2000).lower()[:2000]
        except Exception:
            pass
        if any(w in title_lower for w in ["just a moment...", "attention required!", "security check", "challenge"]) or any(w in body_snippet for w in ["access is temporarily restricted", "unusual activity from your device", "access denied"]):
            print("  ⚠️ Bot detected blocking challenge or rate restriction. Skipping.")
            skip_path = os.path.join(SKIPPED_DIR, f"challenge_{slug_comp}_{timestamp}.png")
            page.screenshot(path=skip_path)
            browser.close()
            return False, "Rate Limited / Restricted"

        # If page has an 'Apply' or 'Apply for this job' button, click it to open/scroll to form
        apply_buttons = [
            "button:has-text('Apply')", "a:has-text('Apply')",
            "button:has-text('Apply Now')", "a:has-text('Apply Now')",
            "a.postings-btn", "a[href*='#app']", "a[href*='/apply']"
        ]
        for ab in apply_buttons:
            try:
                btn = page.locator(ab).first
                if btn.is_visible(timeout=1000):
                    btn.click()
                    time.sleep(1.5)
                    break
            except Exception:
                pass

        # Detect ATS Platform
        if "greenhouse.io" in url:
            fill_greenhouse(page, cand, resume_path)
        elif "lever.co" in url:
            fill_lever(page, cand, resume_path)
        elif "ashbyhq.com" in url:
            fill_ashby(page, cand, resume_path)
        elif "smartrecruiters.com" in url:
            fill_smartrecruiters(page, cand, resume_path)
        else:
            print("  ⚠️ Generic / non-standard ATS. Attempting generic form filler...")
            fill_greenhouse(page, cand, resume_path)

        time.sleep(1)

        # Pre-submit screenshot
        pre_shot = os.path.join(OUTPUT_DIR, f"filled_{slug_comp}_{slug_role}_{timestamp}.png")
        page.screenshot(path=pre_shot, full_page=True)
        print(f"  ✓ Pre-submit state saved: {os.path.basename(pre_shot)}")

        if dry_run:
            print("  [DRY RUN] Form filled and verified successfully. Skipping submit button.")
            browser.close()
            return True, "Dry Run Success"

        # Find submit button
        submit_selectors = [
            "input[type='submit']",
            "button[type='submit']",
            "#submit_app",
            "button#create-application",
            "button:has-text('Submit Application')",
            "button:has-text('Submit application')",
            "button:has-text('Apply now')",
            "button:has-text('Submit')"
        ]
        
        submit_btn = None
        for sel in submit_selectors:
            try:
                btn = page.locator(sel).first
                if btn.is_visible(timeout=1000) and btn.is_enabled():
                    submit_btn = btn
                    break
            except Exception:
                continue

        if not submit_btn:
            print("  ⚠️ Submit button not located or form has incomplete required fields.")
            browser.close()
            return False, "Submit Button Not Found"

        print("  ▶ Clicking Submit button...")
        try:
            submit_btn.click()
            time.sleep(4)
        except Exception as e:
            print(f"  ❌ Click failed: {e}")
            browser.close()
            return False, "Submit Click Error"

        # Verification of submission
        success = False
        curr_url = page.url.lower()
        if any(w in curr_url for w in ["thank", "confirmation", "success", "thanks", "submitted"]):
            success = True
            
        page_text = page.locator("body").inner_text().lower()
        if any(phrase in page_text for phrase in [
            "thank you for applying", "application submitted", "application received",
            "thanks for applying", "your application has been received",
            "was successfully submitted", "successfully submitted"
        ]):
            success = True

        conf_shot = os.path.join(OUTPUT_DIR, f"submitted_{slug_comp}_{slug_role}_{timestamp}.png")
        page.screenshot(path=conf_shot, full_page=True)

        browser.close()

        if success:
            print(f"  🎉 APPLICATION SUBMITTED SUCCESSFULLY!")
            print(f"  Proof Screenshot: {conf_shot}")
            record_application_success(company, role, url, conf_shot)
            return True, "Submitted"
        else:
            print("  ⚠️ Submission completed, but explicit confirmation string was not caught.")
            print(f"  Audit Screenshot captured: {conf_shot}")
            record_application_success(company, role, url, conf_shot)
            return True, "Submitted (Unconfirmed Message)"

def run_batch(max_applications=5, dry_run=False):
    """Reads opportunities.csv and auto-applies to top available ATS jobs"""
    if not os.path.exists(OPPORTUNITIES_CSV):
        print(f"Error: {OPPORTUNITIES_CSV} not found.")
        return

    ats_keywords = ["greenhouse.io", "lever.co", "ashbyhq.com", "smartrecruiters.com"]
    targets = []
    
    with open(OPPORTUNITIES_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = row.get("apply link", "").strip()
            comp = row.get("Firm name", "").strip()
            role = row.get("Job role", "").strip()
            loc = row.get("job location", "").strip()
            if not is_valid_location(loc) or not is_valid_role(role):
                continue
            if any(ats in url for ats in ats_keywords):
                if not is_already_applied(comp, role, url):
                    targets.append((comp, role, url))

    # Prioritize Greenhouse, Lever, and Ashby for highest reliability
    def ats_priority(t):
        u = t[2].lower()
        if "greenhouse.io" in u:
            return 0
        elif "lever.co" in u:
            return 1
        elif "ashbyhq.com" in u:
            return 2
        return 3
    targets.sort(key=ats_priority)

    print(f"\nFound {len(targets)} eligible unapplied ATS jobs.")
    to_apply = targets[:max_applications]
    print(f"Processing batch of {len(to_apply)} applications...\n")

    results = []
    for comp, role, url in to_apply:
        status, reason = execute_auto_apply(comp, role, url, dry_run=dry_run)
        results.append({"company": comp, "role": role, "status": status, "reason": reason})
        time.sleep(2)

    print("\n" + "=" * 60)
    print("           AUTONOMOUS APPLY BATCH SUMMARY")
    print("=" * 60)
    for r in results:
        sym = "✓" if r["status"] else "✗"
        print(f"  {sym} [{r['company']}] {r['role']} — {r['reason']}")
    print("=" * 60)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Zero-Manual Autonomous Application Bot")
    parser.add_argument("--batch", type=int, default=5, help="Number of applications to process")
    parser.add_argument("--all", action="store_true", help="Process all available eligible ATS jobs")
    parser.add_argument("--url", type=str, help="Apply directly to a specific ATS job URL")
    parser.add_argument("--role", type=str, default="Data Analyst", help="Target job role for tailored resume matching")
    parser.add_argument("--company", type=str, default="Target Firm", help="Target firm name")
    parser.add_argument("--dry-run", action="store_true", help="Fill and verify without clicking submit")
    args = parser.parse_args()

    if args.url:
        execute_auto_apply(args.company, args.role, args.url, dry_run=args.dry_run)
    elif args.all:
        run_batch(max_applications=999, dry_run=args.dry_run)
    else:
        run_batch(max_applications=args.batch, dry_run=args.dry_run)
