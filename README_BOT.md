# 🚀 Autonomous Job Hunting & Auto-Apply Bot

An end-to-end, zero-manual-intervention Python job acquisition pipeline. Automatically discovers verified tech opportunities across direct ATS APIs, web portals, startup talent networks, audits link liveness, compiles styled Excel spreadsheets, and autonomously submits applications using headless Playwright.

---

## ⚡ Key Capabilities

1. **Multi-Channel Job Discovery**:
   - **Direct ATS APIs**: Zero-cost, zero-token scans across Greenhouse, Lever, Ashby, and SmartRecruiters.
   - **Remote Tech APIs**: Aggregates verified remote roles from Remotive, Jobicy, and Arbeitnow.
   - **Dynamic Portal Crawler (`Crawl4AI`)**: Headless browser crawler for complex JavaScript/SPA career sites.
   - **Leading Portals**: Tailored Crawl4AI scrapers for Naukri and Instahyre.
   - **Startup Talent Networks**: Scans monthly Hacker News "Who is Hiring?" threads and Y Combinator directories.

2. **Deep ATS Link Liveness & Expiry Cleaner**:
   - Multi-tier validation: checks direct ATS APIs first (Greenhouse, Lever, Ashby, Workday CXS), then falls back to regex body inspection (20+ closed/expired patterns).
   - Automatically archives closed jobs and purges dead links so you never apply to expired postings.

3. **Dependency-Free Spreadsheet Engine**:
   - Pure Python standard library (zipfile + OpenXML) generates styled `.xlsx` workbooks and `.csv` files with zero external dependencies.

4. **Headless Auto-Apply Engine**:
   - Autonomous Playwright browser automation with anti-bot evasion arguments.
   - Form field resolution (First/Last name, Email, Phone, LinkedIn, GitHub, Current Org, Notice Period, Education).
   - Handles custom React-select dropdowns, work authorization questions, and consent checkboxes.
   - Automatically uploads your resume (`.pdf` or `.docx`).
   - Takes pre-submit and confirmation proof screenshots in `output/confirmations/`.

---

## 🛠️ Quickstart Guide

### 1. Prerequisites
- Python 3.10+
- Linux, macOS, or Windows (WSL recommended on Windows)

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/rishi-th219/career-ops-bot.git
cd career-ops-bot

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browser binaries
playwright install chromium
```

### 3. Configure Your Profile & Resume
1. Copy the example configuration file:
   ```bash
   cp config/profile.example.yml config/profile.yml
   ```
2. Open `config/profile.yml` and fill in your details:
   - Contact info (Name, Email, Phone, Location, LinkedIn, GitHub)
   - Screening responses (Education, Notice Period, Work Authorization)
   - Target locations (e.g., `["bengaluru", "pune", "remote", "india"]`)
   - Target roles & keywords (e.g., `["data analyst", "machine learning engineer", "data engineer"]`)
3. Drop your resume in the project root as `resume.pdf` (or specify its filename in `config/profile.yml`).

---

## 💻 CLI Commands

The master command runner is `job_pipeline.py`:

```bash
# Display pipeline statistics & help menu
python job_pipeline.py

# 1. Run Complete Discovery Suite (APIs + Crawlers + Startups)
python job_pipeline.py --all

# 2. Fast Scan (Direct ATS APIs & Remote Tech APIs only)
python job_pipeline.py --apis

# 3. Dynamic Portal Crawler (Crawl4AI for SPAs)
python job_pipeline.py --crawl4ai

# 4. Indian Portals Scraper (Naukri & Instahyre)
python job_pipeline.py --naukri

# 5. Startup & VC Networks (Hacker News & YC)
python job_pipeline.py --startups

# 6. Verify Link Liveness & Clean Expired Jobs
python job_pipeline.py --clean-dead

# 7. Headless Auto-Apply to Top N Jobs (default: 5)
python job_pipeline.py --auto-apply 5

# 8. 100% Autonomous Hands-off Pipeline (Discover -> Clean -> Apply -> Track)
python job_pipeline.py --autonomous

# 9. 1-Click Form Autofill Assistant (Opens a visible browser for row #5)
python job_pipeline.py --autofill 5
```

---

## ⏰ Automated Scheduling (Cron Daemon)

To automatically run the autonomous pipeline every morning at 09:00 AM:

```bash
bash install_cron.sh
```

Logs are appended to `data/autonomous_cron.log`. To check existing schedule:
```bash
crontab -l
```

---

## 🔒 Privacy & Security

- **Strict `.gitignore` Protection**: Resumes (`*.pdf`, `*.docx`), output spreadsheets (`opportunities.xlsx`, `opportunities.csv`), application logs, confirmation screenshots, and `config/profile.yml` are excluded from Git to prevent accidental PII leakage.
- **Dry-Run Mode**: Test form filling without submitting:
  ```bash
  python auto_apply_bot.py --batch 3 --dry-run
  ```
- **Screenshot Proofs**: Pre-submission and post-submission snapshots are saved locally to `output/confirmations/` so you have visual audit proof of every application.

---

## 📄 License
MIT License. Open-source and customizable for your personal career operations.
