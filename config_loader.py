#!/usr/bin/env python3
"""
config_loader.py — Unified Configuration and Profile Loader for Career-Ops Bot
Safely extracts candidate information, targeting preferences, and resume paths
without hardcoding personal credentials in the core scripts.
"""

import os
import sys
import json
import re
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

def get_tailored_resume_filename(role_title=None):
    """
    Determines the appropriate tailored resume filename based on job role keywords.
    Supported tracks:
      1. SQL Developer / Database / ETL / Data Engineering
      2. Power BI Developer / BI Reporting / Visualization
      3. Business Analyst / Strategy / Operations
      4. Data Analyst / Analytics (Default)
    """
    cand = get_candidate_profile()
    name_slug = cand.get("full_name", "").strip().replace(" ", "_")
    prefix = f"{name_slug}_" if name_slug and name_slug != "Candidate_User" else ""

    if not role_title:
        return f"{prefix}Data_Analyst_Resume.pdf"

    r_lower = str(role_title).lower().strip()

    matches = []
    tracks = [
        ("Python", r'\b(python|fastapi|flask|django|backend|api\s+developer|backend\s+engineer|software\s+engineer|sde)\b', f"{prefix}Python_Developer_Resume.pdf"),
        ("PowerBI", r'\b(power\s*bi|powerbi|power-bi|tableau|looker|oac|bi\s+developer|bi\s+engineer|bi\s+analyst|business\s+intelligence|dashboard|reporting)\b', f"{prefix}PowerBI_Developer_Resume.pdf"),
        ("SQL", r'\b(sql|database|dba|data\s+engineer|data\s+engineering|etl|warehouse|dwh|postgres|postgresql|oracle|mariadb|mysql)\b', f"{prefix}SQL_Developer_Resume.pdf"),
        ("BA", r'\b(business\s+analyst|business\s+analytics|strategy|strategic|operations\s+analyst|operation\s+analyst|consultant|product\s+analyst|risk\s+analyst|process\s+analyst|systems?\s+analyst)\b', f"{prefix}Business_Analyst_Resume.pdf"),
        ("DA", r'\b(data\s+analyst|data\s+analytics|analytics|analyst|data)\b', f"{prefix}Data_Analyst_Resume.pdf"),
    ]
    for track_name, pattern, filename in tracks:
        m = re.search(pattern, r_lower)
        if m:
            matches.append((m.start(), filename))

    if matches:
        matches.sort(key=lambda x: x[0])
        return matches[0][1]

    return f"{prefix}Data_Analyst_Resume.pdf"

def find_resume_file(role_title=None):
    """
    Selects and returns the absolute path to the optimal tailored resume based on the job role.
    Prioritizes tailoring directories matching the specific role track:
      - SQL Developer -> *SQL_Developer_Resume.(pdf|docx)
      - Power BI Developer -> *PowerBI_Developer_Resume.(pdf|docx)
      - Business Analyst -> *Business_Analyst_Resume.(pdf|docx)
      - Data Analyst -> *Data_Analyst_Resume.(pdf|docx)
    Falls back gracefully to standard root resumes if tailoring files are missing.
    """
    target_filename = get_tailored_resume_filename(role_title)
    base_name = os.path.splitext(target_filename)[0]

    # Candidate directories containing tailored resumes
    search_dirs = [
        os.path.abspath(os.path.join(PROJECT_ROOT, "..", "tailoring")),
        os.path.abspath(os.path.join(PROJECT_ROOT, "tailoring")),
        os.path.abspath(os.path.join(PROJECT_ROOT, "..", "portfolio", "tailoring")),
        os.path.abspath(os.path.join(PROJECT_ROOT, "..", "portfolio", "assets")),
    ]

    # 1. Search for exact role-matched PDF then DOCX
    for sdir in search_dirs:
        if os.path.isdir(sdir):
            for ext in [".pdf", ".docx"]:
                candidate_path = os.path.join(sdir, f"{base_name}{ext}")
                if os.path.exists(candidate_path) and os.path.isfile(candidate_path):
                    return candidate_path

            # Fuzzy match track keyword in directory if candidate prefix differs
            track_keywords = ["Python", "PowerBI", "SQL", "Business_Analyst", "Data_Analyst"]
            matched_track = next((tk for tk in track_keywords if tk.lower() in base_name.lower()), None)
            if matched_track:
                try:
                    for f in os.listdir(sdir):
                        if (f.lower().endswith(".pdf") or f.lower().endswith(".docx")) and matched_track.lower() in f.lower().replace("-", "_"):
                            return os.path.join(sdir, f)
                except Exception:
                    pass

    # 2. Fallback to default tailored Data Analyst resume in search directories
    for sdir in search_dirs:
        if os.path.isdir(sdir):
            try:
                for f in os.listdir(sdir):
                    if (f.lower().endswith(".pdf") or f.lower().endswith(".docx")) and "data_analyst" in f.lower().replace("-", "_").replace(" ", "_"):
                        return os.path.join(sdir, f)
            except Exception:
                pass

    # 3. Standard fallbacks in candidate config or project root
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
