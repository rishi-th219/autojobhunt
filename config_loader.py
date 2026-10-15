#!/usr/bin/env python3
"""
config_loader.py — Unified Configuration and Profile Loader for Career-Ops Bot
Safely extracts candidate information, targeting preferences, and resume paths
without hardcoding personal credentials in the core scripts.
"""

import os
import sys
import json
import yaml

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
PROFILE_YML = os.path.join(PROJECT_ROOT, "config", "profile.yml")
PROFILE_EXAMPLE_YML = os.path.join(PROJECT_ROOT, "config", "profile.example.yml")
CORRECTIONS_FILE = os.path.join(PROJECT_ROOT, "config", "corrections.json")

# Generic fallback profile (Never hardcode PII here)
DEFAULT_CANDIDATE = {
    "first_name": "Candidate",
    "last_name": "User",
    "full_name": "Candidate User",
    "email": "candidate@example.com",
    "phone": "0000000000",
    "phone_with_code": "+910000000000",
    "location": "Bengaluru, Karnataka, India",
    "city": "Bengaluru",
    "state": "Karnataka",
    "country": "India",
    "linkedin": "https://linkedin.com",
    "github": "https://github.com",
    "current_org": "Open to Opportunities",
    "notice_period": "Immediate / 15 Days",
    "years_experience": "1",
    "education": "Bachelor's / Master's in Computer Science",
    "degree": "Bachelor's Degree",
    "school": "University",
    "discipline": "Computer Science and Engineering",
    "authorized_in_country": "Yes",
    "require_sponsorship": "No",
    "resume_file": "resume.pdf"
}

DEFAULT_TARGET_LOCATIONS = [
    "bengaluru", "bangalore", "karnataka", "blr", "in-ka",
    "pune", "maharashtra", "raipur", "chhattisgarh", "cg",
    "remote", "work from home", "anywhere", "wfh", "distributed", "global",
    "india", "ind", "pan-india", "pan india"
]

DEFAULT_EXCLUDED_LOCATIONS = [
    "united states", "usa", ", ca", ", ny", ", tx", ", wa", ", ma",
    "united kingdom", "uk", "germany", "deutschland", "france", "hungary",
    "poland", "spain", "portugal", "romania", "china", "vietnam", "singapore",
    "turkey", "bulgaria", "malaysia", "japan", "australia", "canada",
    "liechtenstein", "philippines", "brazil", "mexico",
    "san mateo", "san francisco", "new york", "london", "dublin", "seattle"
]

DEFAULT_EXCLUDE_TITLE_KEYWORDS = [
    "intern", "internship", "working student", "werkstudent", "praktikum", "praktikant",
    "gyakornok", "staż", "stage -", "stage ", "premaster"
]

_CACHED_CONFIG = None

def load_config():
    global _CACHED_CONFIG
    if _CACHED_CONFIG is not None:
        return _CACHED_CONFIG

    cfg = {}
    if os.path.exists(PROFILE_YML):
        try:
            with open(PROFILE_YML, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
        except Exception as e:
            print(f"⚠️ Warning: Could not parse {PROFILE_YML}: {e}", file=sys.stderr)
    else:
        # Don't crash immediately, but inform user
        if not os.path.exists(PROFILE_EXAMPLE_YML):
            print("⚠️ Note: config/profile.yml not found. Using default templates.", file=sys.stderr)

    _CACHED_CONFIG = cfg
    return _CACHED_CONFIG

def get_candidate_profile():
    cfg = load_config()
    c = cfg.get("candidate", {})
    
    cand = dict(DEFAULT_CANDIDATE)
    for k, v in c.items():
        if v:
            cand[k] = str(v).strip()

    # Derived first and last name if not explicitly set
    if "full_name" in c and c["full_name"]:
        full = str(c["full_name"]).strip()
        parts = full.split(" ", 1)
        cand["full_name"] = full
        cand["first_name"] = c.get("first_name") or parts[0]
        cand["last_name"] = c.get("last_name") or (parts[1] if len(parts) > 1 else "")

    # Clean URLs
    for url_key in ["linkedin", "github"]:
        val = cand.get(url_key, "")
        if val and not val.startswith("http"):
            cand[url_key] = f"https://{val}"

    return cand

def get_targeting_config():
    cfg = load_config()
    tgt = cfg.get("targeting", {})

    target_locs = tgt.get("target_locations", DEFAULT_TARGET_LOCATIONS)
    target_locs = [str(x).lower().strip() for x in target_locs if x]

    excluded_locs = tgt.get("excluded_locations", DEFAULT_EXCLUDED_LOCATIONS)
    excluded_locs = [str(x).lower().strip() for x in excluded_locs if x]

    exclude_titles = tgt.get("exclude_title_keywords", DEFAULT_EXCLUDE_TITLE_KEYWORDS)
    exclude_titles = [str(x).lower().strip() for x in exclude_titles if x]

    pos_keywords = tgt.get("positive_keywords", [])
    pos_keywords = [str(x).lower().strip() for x in pos_keywords if x]

    return {
        "target_locations": target_locs,
        "excluded_locations": excluded_locs,
        "exclude_title_keywords": exclude_titles,
        "positive_keywords": pos_keywords
    }

def is_valid_location(location):
    if not location:
        return True
    loc_lower = str(location).lower()
    tgt = get_targeting_config()

    # Exclude foreign / blacklisted locations unless explicitly qualified by a target hub
    if any(fc in loc_lower for fc in tgt["excluded_locations"]):
        # If it explicitly mentions target country or cities, allow it (e.g. "Global / India")
        if not any(tc in loc_lower for tc in ["india", "bengaluru", "bangalore", "pune", "raipur"]):
            return False

    # Check target locations
    return any(tl in loc_lower for tl in tgt["target_locations"])

def is_valid_role(title):
    if not title:
        return False
    t_lower = str(title).lower()
    tgt = get_targeting_config()
    return not any(ek in t_lower for ek in tgt["exclude_title_keywords"])

def find_resume_file():
    cand = get_candidate_profile()
    configured_resume = cand.get("resume_file")

    candidates = []
    if configured_resume:
        candidates.append(os.path.abspath(os.path.join(PROJECT_ROOT, configured_resume)))
        candidates.append(os.path.abspath(configured_resume))

    # Standard fallbacks in project root
    for fname in ["resume.pdf", "resume.docx", "cv.pdf", "cv.docx"]:
        candidates.append(os.path.join(PROJECT_ROOT, fname))

    # Also search for any user-dropped PDF in project root that contains "resume" or "cv"
    try:
        for f in os.listdir(PROJECT_ROOT):
            if (f.lower().endswith(".pdf") or f.lower().endswith(".docx")) and any(kw in f.lower() for kw in ["resume", "cv"]):
                candidates.append(os.path.join(PROJECT_ROOT, f))
    except Exception:
        pass

    for path in candidates:
        if os.path.exists(path) and os.path.isfile(path):
            return path

    return None

def get_corrections():
    rejected_urls = set()
    known_corrections = {}

    if os.path.exists(CORRECTIONS_FILE):
        try:
            with open(CORRECTIONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                rejected_urls.update(data.get("rejected_urls", []))
                known_corrections.update(data.get("known_corrections", {}))
        except Exception as e:
            print(f"⚠️ Warning: Could not read {CORRECTIONS_FILE}: {e}", file=sys.stderr)

    return rejected_urls, known_corrections
