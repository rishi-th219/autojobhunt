# AutoJobHunt & Career-Ops — Windows Handover Document

> **For the Antigravity Agent reading this on Windows:**  
> This document contains everything you need to immediately resume work on AutoJobHunt / Career-Ops on Windows without missing any context.

---

## 1. Executive Summary & Identity

- **Candidate:** Rishi Thakur
- **Email:** `rishi_th219@proton.me`
- **Location:** Bengaluru, India (Open to Bengaluru On-site/Hybrid and Remote India)
- **Education:** M.Tech in CSE (Specialization: Data Science & Artificial Intelligence — DSAI), IIIT Naya Raipur
- **GitHub Repository:** `https://github.com/rishi-th219/autojobhunt.git`
- **Primary Branch:** `main`
- **Career-Ops Engine Version:** `v1.38.0`

---

## 2. Current Project State & Recent Milestones

### A. Targeting Pivot: Analyst-Only Focus
- **Paused / Excluded:** All Machine Learning, Artificial Intelligence, and Data Science roles are explicitly paused per user instructions.
- **Active Focus:**
  - **Core Analytics:** Data Analyst, Business Analyst, BI Developer, Power BI Analyst, SQL Analyst.
  - **Specialized Industry Analysts:** Financial Analyst, Marketing Analyst, Healthcare Analyst, Supply Chain Analyst, Logistics Analyst, Sales Analyst, People Analyst (HR Analyst, People Analytics), Risk Analyst, Fraud Analyst, Retail Analyst, Revenue Analyst, Operations Analyst, Product Analyst.
  - **Duty & Tool Focus:** Database Analyst, Business Intelligence Analyst, Tableau Specialist, Insights Analyst, Reporting Analyst, Data Quality Analyst, Forecasting Analyst, MIS Analyst/Executive.
- **Configured Files:**
  - `daily_job_scanner.py`: Cleaned `POSITIVE_KEYWORDS`, added ML/AI exclusions to `NEGATIVE_KEYWORDS`.
  - `jobspy_scanner.py`: Pruned `search_configs` down to strictly Data Analyst, Business Analyst, and domain/functional analyst queries.
  - `portals.yml`: Replaced R&D / ML queries with domain analyst queries (Financial, Marketing, Operations, Product, SCM).
  - `config/profile.yml`: Set `target_roles.primary` to analyst roles; commented out ML/AI roles.

### B. Link Liveness & Expiration Cleaner (`clean_expired_jobs.py`)
- Automatically verifies links concurrently via native ATS APIs (Greenhouse, Lever, Ashby, Workday, LinkedIn guest endpoint) and page text regexes.
- Executed and verified: **39 expired/closed positions purged and archived** to `data/archived_expired_opportunities.csv`.
- Cleaned dead URLs from `data/pipeline.md` and `new_jobs_found.json`.
- Current active consolidated database: **1,176 verified opportunities** in `opportunities.csv` and `opportunities.xlsx`.

### C. Web Dashboard (`web_dashboard.py`)
- Running locally at: **`http://localhost:5000`**
- **Theme Redesign:** Minimalist, high-contrast, clean Scandinavian/Linear aesthetic with `Inter` typography, subtle 1px slate borders, neutral badges, and a **Light / Dark Mode toggle (`☀️ / 🌙`)**.
- **Metrics & Filters:** Built-in category filters for:
  - Total Active Jobs (1,176)
  - Data Analysts (214)
  - Business Analysts (137)
  - Domain Analysts (Financial, Marketing, Operations, Product, Supply Chain, Risk, HR) (47)
  - BI & Power BI / Tableau (49)
  - SQL, MIS & Reporting (40)

### D. Multi-User / Sister Personalization Workflow
- The bot is cleanly split between **System Layer** (code, scrapers, dashboard) and **User Layer** (personal data).
- To personalize for the user's sister:
  1. Clone/copy the project to a separate folder (e.g. `Jobhunt-Sister`).
  2. Customize 5 files: `config/profile.yml`, `cv.md`, `portals.yml`, `modes/_profile.md`, and drop her `resume.pdf`.
  3. Reset tracker data (`opportunities.csv`, `data/pipeline.md`, `data/scan-history.tsv`).
  4. Run `python daily_job_scanner.py` and `python web_dashboard.py`.

---

## 3. Windows Environment Setup Guide

### Prerequisites
1. **Git for Windows:** Ensure `git` is in `PATH`.
2. **Python 3.10+:** Ensure Python and `pip` are installed and added to `PATH`.
3. **Node.js 18+ (Optional but recommended):** For running career-ops native JavaScript utilities (`stats.mjs`, `set-status.mjs`, etc.).

### Step-by-Step Installation (PowerShell)

```powershell
# 1. Clone repository
git clone https://github.com/rishi-th219/autojobhunt.git
cd autojobhunt

# 2. Create and activate Python virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Install Python dependencies
pip install -r requirements.txt
pip install python-jobspy pyyaml playwright playwright-stealth

# 4. Install Playwright browser binaries
playwright install chromium

# 5. (Optional) Install Node modules for career-ops scripts
npm install
```

---

## 4. Gitignored User Layer Files (Restore / Recreate)

Because personal data is strictly protected by `.gitignore`, the following files do not travel via Git. If migrating machines without copying local files directly:

### 1. `config/profile.yml`
Create `config/profile.yml`:
```yaml
candidate:
  full_name: "Rishi Thakur"
  email: "rishi_th219@proton.me"
  phone: "8109830219"
  location: "Bengaluru, India"
  education: "M.Tech in CSE (Specialization: Data Science & Artificial Intelligence — DSAI), IIIT Naya Raipur (CGPA 7.90)"
  linkedin: "linkedin.com/in/rishi-thakur-b665a4298"
  github: "github.com/rishi-th219"

target_roles:
  primary:
    - "Data Analyst / Analytics Engineer"
    - "Business Analyst (Data & Strategy)"
    - "BI Developer / Power BI Developer"
    - "SQL Analyst / Database Analyst"
    - "Reporting Analyst / MIS Analyst / MIS Executive"
    - "Financial Analyst / Financial Data Analyst"
    - "Marketing Analyst / Marketing Data Analyst"
    - "Healthcare Analyst / Healthcare Data Analyst"
    - "Supply Chain Analyst / Logistics Analyst"
    - "Sales Analyst / Revenue Analyst"
    - "People Analyst / People Analytics Analyst / HR Analyst"
    - "Risk Analyst / Fraud Analyst"
    - "Retail Analyst / Operations Analyst"
    - "Product Analyst / Insights Analyst"
    - "Database Analyst / Data Quality Analyst"
    - "Business Intelligence Analyst"
    - "Tableau Specialist / Tableau Developer / Tableau Analyst"
    - "Forecasting Analyst / Predictive Analyst"
```

### 2. `.env` (Email Alerts)
Create `.env` if you want automatic email notifications on new job finds:
```env
SMTP_SERVER=smtp.protonmail.ch
SMTP_PORT=587
SMTP_USER=rishi_th219@proton.me
SMTP_PASSWORD=your_app_password_here
ALERT_RECIPIENT=rishi_th219@proton.me
```

### 3. User Data Files
Ensure these directories and base files exist:
```powershell
New-Item -ItemType Directory -Force -Path data, output, reports, jds
if (-not (Test-Path data\pipeline.md)) { New-Item -ItemType File data\pipeline.md }
if (-not (Test-Path data\scan-history.tsv)) { New-Item -ItemType File data\scan-history.tsv }
if (-not (Test-Path data\applications.md)) { New-Item -ItemType File data\applications.md }
```

---

## 5. Daily Operations & CLI Commands on Windows

### 1. Launch Web Dashboard
```powershell
python web_dashboard.py
```
- Opens `http://localhost:5000`
- Provides 1-click AutoFill bookmarklet and extension guide.
- Allows filtering by role, location, search queries, and pagination.

### 2. Run Job Discovery Scanner
```powershell
# Comprehensive multi-provider scan (Greenhouse, Lever, Ashby, SmartRecruiters, JobSpy)
python daily_job_scanner.py

# Without JobSpy (fast ATS-only scan)
python daily_job_scanner.py --no-jobspy
```

### 3. Run Expired Link Cleaner
```powershell
# Checks link liveness and removes dead positions
python clean_expired_jobs.py

# Preview mode without making changes
python clean_expired_jobs.py --dry-run
```

### 4. 24/7 Silent Background Daemon (Windows Native)
The repository includes Windows-native scripts to keep the scanner running silently without keeping a terminal open:
```powershell
# Register daemon in Windows Startup folder (auto-starts on logon, zero admin needed)
powershell -ExecutionPolicy Bypass -File .\setup_windows_task.ps1 -Install

# Check status
python background_daemon.py --status

# Launch silent run immediately
wscript.exe .\run_daemon_background.vbs

# Uninstall / disable autostart
powershell -ExecutionPolicy Bypass -File .\setup_windows_task.ps1 -Uninstall
```

---

## 6. Key Architecture & File Map

| File | Purpose |
| :--- | :--- |
| `web_dashboard.py` | Local web dashboard on port 5000 (Flask-free, native HTTP server) |
| `daily_job_scanner.py` | Core discovery pipeline (ATS APIs + JobSpy scraper + deduplication) |
| `jobspy_scanner.py` | Multi-portal scraper for LinkedIn & Indeed using `python-jobspy` |
| `clean_expired_jobs.py` | Concurrent dead-link and ATS closed-role cleaner |
| `opportunities_manager.py` | Consolidates pipeline leads into `opportunities.csv` and `opportunities.xlsx` |
| `background_daemon.py` | Continuous background polling and alerting daemon |
| `setup_windows_task.ps1` | Windows Task Scheduler / Startup registration script |
| `run_daemon_background.vbs`| Invisible background process spawner for Windows |
| `autofill_assistant.py` | Playwright-powered form filler for Greenhouse, Lever, and Workday |
| `autofill.js` | Bookmarklet / Extension script for in-browser form filling |
| `email_notifier.py` | HTML email alert dispatcher |
| `portals.yml` | Scanner keyword filters and target ATS companies |
| `config/profile.yml` | Candidate identity and target role configuration |
| `cv.md` | Ground-truth CV (source of truth for skills, experience, and tailoring) |
| `AGENTS.md` | Core Career-Ops instructions for AI agents |
