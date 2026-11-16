#!/usr/bin/env python3
"""
web_dashboard.py — Localhost Browser Dashboard for AutoJobHunt (based on career-ops)
Lists all opportunities from opportunities.xlsx / opportunities.csv and enables
1-click tailored auto-fill applications and background job scanning from the browser.

Zero external web dependencies — runs entirely on Python standard library (http.server).
"""

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
import csv
import json
import time
import re
import urllib.parse
import subprocess
import threading
import webbrowser
import config_loader
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
OPPORTUNITIES_CSV = os.path.join(PROJECT_ROOT, "opportunities.csv")
OPPORTUNITIES_XLSX = os.path.join(PROJECT_ROOT, "opportunities.xlsx")
PIPELINE_FILE = os.path.join(PROJECT_ROOT, "data", "pipeline.md")
APPLICATIONS_FILE = os.path.join(PROJECT_ROOT, "data", "applications.md")
STATUS_LOG_FILE = os.path.join(PROJECT_ROOT, "data", "status-log.tsv")

candidate_bins = [
    os.path.join(PROJECT_ROOT, ".venv", "Scripts", "python.exe"),
    os.path.join(PROJECT_ROOT, ".venv", "bin", "python"),
]
PYTHON_BIN = next((p for p in candidate_bins if os.path.exists(p)), sys.executable)

# Global state for background scans and applications
ACTIVE_SCAN = {
    "is_running": False,
    "channel": None,
    "start_time": None,
    "logs": []
}
SCAN_LOCK = threading.Lock()

def get_applied_urls():
    """Returns set of normalized URLs already in applications.md."""
    applied = set()
    if os.path.exists(APPLICATIONS_FILE):
        try:
            with open(APPLICATIONS_FILE, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    m = re.search(r"https?://[^\s\)\|\"]+", line)
                    if m:
                        applied.add(m.group(0).split("#")[0].rstrip("/"))
        except Exception:
            pass
    return applied

def classify_role(title):
    """Categorizes a job title for dashboard quick filters."""
    t = title.lower()
    categories = []
    
    # Core Analytics
    if "data analyst" in t or "analytics associate" in t or "data associate" in t:
        categories.append("Data Analyst")
    if "business analyst" in t:
        categories.append("Business Analyst")
        
    # Domain / Industry Analysts
    if "financial analyst" in t or "finance analyst" in t:
        categories.append("Financial Analyst")
        categories.append("Domain Analyst")
    if "marketing analyst" in t:
        categories.append("Marketing Analyst")
        categories.append("Domain Analyst")
    if "operations analyst" in t:
        categories.append("Operations Analyst")
        categories.append("Domain Analyst")
    if "product analyst" in t:
        categories.append("Product Analyst")
        categories.append("Domain Analyst")
    if "supply chain" in t or "logistics analyst" in t or "inventory analyst" in t:
        categories.append("Supply Chain Analyst")
        categories.append("Domain Analyst")
    if "sales analyst" in t or "revenue analyst" in t:
        categories.append("Sales & Revenue")
        categories.append("Domain Analyst")
    if "risk analyst" in t or "fraud analyst" in t:
        categories.append("Risk & Fraud")
        categories.append("Domain Analyst")
    if "people analyst" in t or "hr analyst" in t or "people analytics" in t:
        categories.append("People & HR")
        categories.append("Domain Analyst")
    if "healthcare analyst" in t or "retail analyst" in t or "database analyst" in t:
        categories.append("Domain Analyst")

    # Functional / Tool / Duty Analysts
    if any(k in t for k in ["power bi", "powerbi", "bi developer", "bi analyst", "business intelligence", "tableau"]):
        categories.append("BI & Power BI")
    if "tableau" in t:
        categories.append("Tableau")
    if any(k in t for k in ["sql analyst", "reporting analyst", "mis analyst", "mis executive", "mis reporting", "reporting", "database analyst", "data quality", "forecasting"]):
        categories.append("SQL / MIS / Reporting")

    # Broad Data Analytics bucket
    if any(k in t for k in ["analyst", "analytics", "bi", "tableau", "sql", "reporting", "mis"]):
        categories.append("Data Analytics")

    if any(w in t for w in ["intern", "internship", "trainee"]):
        categories.append("Internship")
    if "contract" in t or "contractor" in t or "fixed term" in t:
        categories.append("Contract")
    if any(k in t for k in ["machine learning", "ml", "ai", "artificial intelligence", "data scientist", "deep learning", "computer vision", "nlp", "genai", "generative ai", "llm", "research", "r&d"]):
        categories.append("AI / ML")
    if any(k in t for k in ["python", "fastapi", "flask", "django", "backend"]):
        categories.append("Python / Backend")
    if any(k in t for k in ["data engineer", "etl", "data warehouse", "pipeline"]):
        categories.append("Data Engineering")
        
    if not categories:
        categories.append("General Tech")
    return categories

def load_opportunities_data():
    """Loads and formats all opportunities from opportunities.csv."""
    if not os.path.exists(OPPORTUNITIES_CSV):
        return []

    applied_set = get_applied_urls()
    opportunities = []

    with open(OPPORTUNITIES_CSV, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=1):
            url = row.get("apply link", "").strip()
            norm_url = url.split("#")[0].rstrip("/")
            role = row.get("Job role", "").strip()
            company = row.get("Firm name", "").strip()
            loc = row.get("job location", "").strip()
            exp = row.get("experience required", "").strip()
            skills = row.get("top skills required", "").strip()
            pay = row.get("pay", "").strip()

            categories = classify_role(role)
            is_applied = (norm_url in applied_set) or (url in applied_set)

            # Detect ATS/Platform
            portal = "Other"
            if "greenhouse.io" in url:
                portal = "Greenhouse"
            elif "lever.co" in url:
                portal = "Lever"
            elif "ashbyhq.com" in url:
                portal = "Ashby"
            elif "myworkdayjobs.com" in url or "workday" in url:
                portal = "Workday"
            elif "smartrecruiters.com" in url:
                portal = "SmartRecruiters"
            elif "naukri.com" in url:
                portal = "Naukri"
            elif "linkedin.com" in url:
                portal = "LinkedIn"
            elif "indeed.com" in url:
                portal = "Indeed"
            elif "ycombinator.com" in url or "news.ycombinator.com" in url:
                portal = "YC / HN"

            opportunities.append({
                "id": idx,
                "company": company,
                "role": role,
                "url": url,
                "location": loc,
                "experience": exp,
                "skills": skills,
                "pay": pay,
                "portal": portal,
                "categories": categories,
                "is_applied": is_applied
            })

    return opportunities

def get_stats():
    """Computes summary statistics."""
    opps = load_opportunities_data()
    total = len(opps)
    da = sum(1 for o in opps if "Data Analyst" in o["categories"])
    ba = sum(1 for o in opps if "Business Analyst" in o["categories"])
    domain = sum(1 for o in opps if "Domain Analyst" in o["categories"])
    powerbi = sum(1 for o in opps if "BI & Power BI" in o["categories"])
    sql_mis = sum(1 for o in opps if "SQL / MIS / Reporting" in o["categories"])
    applied = sum(1 for o in opps if o["is_applied"])
    
    return {
        "total": total,
        "da": da,
        "ba": ba,
        "domain": domain,
        "powerbi": powerbi,
        "sql_mis": sql_mis,
        "applied": applied
    }

def run_scan_worker(channel):
    """Background worker that runs discovery scanners."""
    global ACTIVE_SCAN
    with SCAN_LOCK:
        ACTIVE_SCAN["is_running"] = True
        ACTIVE_SCAN["channel"] = channel
        ACTIVE_SCAN["start_time"] = datetime.now().strftime("%H:%M:%S")
        ACTIVE_SCAN["logs"] = [f"[{ACTIVE_SCAN['start_time']}] Starting job scan for '{channel}'..."]

    cmd = [PYTHON_BIN, "job_pipeline.py"]
    if channel == "apis":
        cmd.append("--apis")
    elif channel == "startups":
        cmd.append("--startups")
    elif channel == "naukri":
        cmd.append("--naukri")
    elif channel == "jobspy":
        cmd.append("--jobspy")
    elif channel == "all":
        cmd.append("--all")
    else:
        cmd.append("--apis")

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        for line in iter(proc.stdout.readline, ""):
            line_clean = line.strip()
            if line_clean:
                with SCAN_LOCK:
                    ACTIVE_SCAN["logs"].append(line_clean)
                    if len(ACTIVE_SCAN["logs"]) > 200:
                        ACTIVE_SCAN["logs"].pop(0)
        proc.stdout.close()
        proc.wait()
        with SCAN_LOCK:
            ACTIVE_SCAN["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] ✓ Scan finished successfully!")
    except Exception as e:
        with SCAN_LOCK:
            ACTIVE_SCAN["logs"].append(f"⚠️ Error running scan: {e}")
    finally:
        with SCAN_LOCK:
            ACTIVE_SCAN["is_running"] = False

def run_apply_worker(row_id):
    """Spawns Playwright autofill assistant for the specified row."""
    cmd = [PYTHON_BIN, "autofill_assistant.py", str(row_id)]
    subprocess.Popen(cmd, cwd=PROJECT_ROOT)

def mark_opportunity_applied(company, role, url):
    """Records an application manually to data/applications.md and status-log.tsv."""
    today = datetime.now().strftime("%Y-%m-%d")
    clean_url = url.split("#")[0].rstrip("/")
    
    # 1. Update applications.md
    if os.path.exists(APPLICATIONS_FILE):
        with open(APPLICATIONS_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Check if company already in table
        if clean_url not in content:
            new_row = f"| {company} | {role} | Applied | {today} | [Link]({clean_url}) | — | Applied via Dashboard |\n"
            lines = content.splitlines(keepends=True)
            inserted = False
            for i, line in enumerate(lines):
                if line.startswith("|") and i > 2 and ("| Company" not in line) and ("|---" not in line):
                    lines.insert(i, new_row)
                    inserted = True
                    break
            if not inserted:
                lines.append(new_row)
            with open(APPLICATIONS_FILE, "w", encoding="utf-8") as f:
                f.writelines(lines)
                
    # 2. Update status-log.tsv
    with open(STATUS_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"manual\t{today}\t-\tApplied\tdashboard\tApplied via web dashboard\n")

# Threaded HTTP Server
class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Quiet standard HTTP access logs to keep terminal clean
        pass

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            html_bytes = HTML_CONTENT.encode("utf-8")
            self.send_header("Content-Length", str(len(html_bytes)))
            self.end_headers()
            self.wfile.write(html_bytes)
        elif path == "/api/profile":
            cand = config_loader.get_candidate_profile()
            self.send_json(cand)
        elif path == "/autofill.js":
            js_path = os.path.join(PROJECT_ROOT, "autofill.js")
            if os.path.exists(js_path):
                with open(js_path, "rb") as f:
                    js_bytes = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/javascript; charset=utf-8")
                self.send_header("Content-Length", str(len(js_bytes)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(js_bytes)
            else:
                self.send_response(404)
                self.end_headers()
        elif path == "/api/opportunities":
            opps = load_opportunities_data()
            self.send_json(opps)
        elif path == "/api/stats":
            stats = get_stats()
            self.send_json(stats)
        elif path == "/api/scan-status":
            with SCAN_LOCK:
                self.send_json(ACTIVE_SCAN)
        elif path == "/api/daemon":
            import background_daemon
            pid = background_daemon.get_active_daemon_pid()
            status_file = os.path.join(PROJECT_ROOT, "data", "daemon_status.json")
            info = {"is_running": bool(pid), "pid": pid}
            if os.path.exists(status_file):
                try:
                    with open(status_file, "r", encoding="utf-8") as f:
                        info.update(json.load(f))
                except Exception:
                    pass
            self.send_json(info)
        elif path == "/api/email/latest":
            latest_html = os.path.join(PROJECT_ROOT, "data", "email_alerts", "latest_alert.html")
            if os.path.exists(latest_html):
                with open(latest_html, "rb") as f:
                    data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_json({"message": "No alerts generated yet."})
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        content_length = int(self.headers.get("Content-Length", 0))
        post_body = self.rfile.read(content_length) if content_length > 0 else b"{}"
        try:
            payload = json.loads(post_body.decode("utf-8")) if post_body else {}
        except Exception:
            payload = {}

        if path == "/api/apply":
            row_id = payload.get("row")
            launch_standalone = payload.get("standalone", False)
            if not row_id:
                self.send_json({"error": "Missing row id"}, 400)
                return
            
            # Look up company and role
            opps = load_opportunities_data()
            target = next((o for o in opps if o["id"] == int(row_id)), None)
            comp = target["company"] if target else "Company"
            role = target["role"] if target else "Role"
            target_url = target["url"] if target else ""

            # Only spawn standalone Chromium if explicitly requested
            if launch_standalone:
                threading.Thread(target=run_apply_worker, args=(row_id,), daemon=True).start()
            
            self.send_json({
                "status": "ok",
                "url": target_url,
                "company": comp,
                "role": role,
                "message": f"Target for #{row_id}: {comp} — {role}"
            })

        elif path == "/api/scan":
            channel = payload.get("channel", "apis")
            with SCAN_LOCK:
                if ACTIVE_SCAN["is_running"]:
                    self.send_json({"error": "A scan is already in progress."}, 409)
                    return
            threading.Thread(target=run_scan_worker, args=(channel,), daemon=True).start()
            self.send_json({"status": "started", "channel": channel})

        elif path == "/api/mark-applied":
            comp = payload.get("company", "Unknown")
            role = payload.get("role", "Unknown Role")
            url = payload.get("url", "")
            mark_opportunity_applied(comp, role, url)
            self.send_json({"status": "ok", "message": f"Marked {comp} as Applied."})

        elif path == "/api/open-browser":
            url = payload.get("url")
            if url:
                webbrowser.open(url)
            self.send_json({"status": "ok"})
        elif path == "/api/daemon/start":
            import background_daemon
            interval = payload.get("interval", 60)
            background_daemon.start_detached(interval)
            self.send_json({"status": "started", "interval": interval})
        elif path == "/api/daemon/stop":
            import background_daemon
            background_daemon.stop_daemon()
            self.send_json({"status": "stopped"})
        elif path == "/api/email/test":
            import email_notifier
            success, msg = email_notifier.send_test_email()
            self.send_json({"success": success, "message": msg})
        else:
            self.send_response(404)
            self.end_headers()

# Single-page modern dashboard application
HTML_CONTENT = """<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AutoJobHunt • Pipeline & Opportunities</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #09090b;
      --surface: #121215;
      --surface-hover: #18181c;
      --surface-subtle: #1c1c22;
      --border: #27272a;
      --border-subtle: #1f1f24;
      --text: #fafafa;
      --text-muted: #a1a1aa;
      --text-subtle: #71717a;
      --primary: #2563eb;
      --primary-hover: #1d4ed8;
      --primary-subtle: rgba(37, 99, 235, 0.12);
      --success: #10b981;
      --success-subtle: rgba(16, 185, 129, 0.12);
      --badge-bg: #18181c;
      --badge-border: #27272a;
      --badge-text: #d4d4d8;
      --chip-bg: #121215;
      --chip-border: #27272a;
      --chip-active-bg: #27272a;
      --chip-active-text: #ffffff;
      --table-header: #0d0d10;
      --table-row-hover: #141418;
      --table-row-border: #1a1a1f;
      --avatar-bg: #18181b;
      --avatar-border: #27272a;
      --avatar-text: #e4e4e7;
    }

    [data-theme="light"] {
      --bg: #f8fafc;
      --surface: #ffffff;
      --surface-hover: #f1f5f9;
      --surface-subtle: #f8fafc;
      --border: #e2e8f0;
      --border-subtle: #edf2f7;
      --text: #0f172a;
      --text-muted: #475569;
      --text-subtle: #94a3b8;
      --primary: #2563eb;
      --primary-hover: #1d4ed8;
      --primary-subtle: rgba(37, 99, 235, 0.08);
      --success: #059669;
      --success-subtle: rgba(5, 150, 105, 0.08);
      --badge-bg: #f1f5f9;
      --badge-border: #e2e8f0;
      --badge-text: #334155;
      --chip-bg: #ffffff;
      --chip-border: #e2e8f0;
      --chip-active-bg: #0f172a;
      --chip-active-text: #ffffff;
      --table-header: #f8fafc;
      --table-row-hover: #f8fafc;
      --table-row-border: #f1f5f9;
      --avatar-bg: #f1f5f9;
      --avatar-border: #e2e8f0;
      --avatar-text: #334155;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background-color: var(--bg);
      color: var(--text);
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      overflow-x: hidden;
      font-size: 13.5px;
      line-height: 1.5;
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
      transition: background-color 0.15s ease, color 0.15s ease;
    }

    /* Minimal Header */
    header {
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      position: sticky;
      top: 0;
      z-index: 50;
      padding: 0 1.5rem;
      height: 52px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 0.65rem;
    }
    .brand-icon {
      width: 24px;
      height: 24px;
      border-radius: 5px;
      background: var(--text);
      color: var(--bg);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 0.72rem;
      font-weight: 800;
    }
    .brand-title {
      font-size: 0.9rem;
      font-weight: 600;
      letter-spacing: -0.01em;
      color: var(--text);
    }
    .brand-badge {
      font-size: 0.68rem;
      font-weight: 500;
      padding: 1px 6px;
      border-radius: 4px;
      background: var(--surface-subtle);
      border: 1px solid var(--border);
      color: var(--text-subtle);
      font-family: 'JetBrains Mono', monospace;
    }

    .header-actions {
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }

    /* Clean Buttons */
    .btn {
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      padding: 0.38rem 0.75rem;
      border-radius: 5px;
      font-size: 0.78rem;
      font-weight: 500;
      cursor: pointer;
      border: 1px solid var(--border);
      background: var(--surface);
      color: var(--text);
      transition: all 0.12s ease;
      text-decoration: none;
      white-space: nowrap;
    }
    .btn:hover {
      background: var(--surface-hover);
      border-color: var(--text-subtle);
    }
    .btn-primary {
      background: var(--text);
      border-color: var(--text);
      color: var(--bg);
      font-weight: 600;
    }
    .btn-primary:hover {
      opacity: 0.88;
    }
    .btn-theme {
      width: 30px;
      height: 30px;
      padding: 0;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border-radius: 5px;
      background: transparent;
      border: 1px solid var(--border);
      color: var(--text-muted);
      cursor: pointer;
      font-size: 0.85rem;
    }
    .btn-theme:hover {
      background: var(--surface-hover);
      color: var(--text);
    }

    /* Minimal Info Strip */
    .info-strip {
      background: var(--surface);
      border-bottom: 1px solid var(--border-subtle);
      padding: 0.45rem 1.5rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      font-size: 0.75rem;
      color: var(--text-muted);
    }
    .info-strip-left {
      display: flex;
      align-items: center;
      gap: 0.45rem;
    }
    .status-dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: var(--success);
      display: inline-block;
    }
    .info-strip-right {
      display: flex;
      align-items: center;
      gap: 0.65rem;
    }
    .bookmarklet-pill {
      background: var(--surface-subtle);
      border: 1px dashed var(--border);
      padding: 2px 7px;
      border-radius: 4px;
      color: var(--text);
      font-weight: 500;
      text-decoration: none;
      cursor: grab;
      font-size: 0.72rem;
      display: inline-flex;
      align-items: center;
      gap: 0.3rem;
    }
    .bookmarklet-pill:hover {
      border-color: var(--text-muted);
    }
    .guide-link {
      color: var(--text-subtle);
      cursor: pointer;
      text-decoration: underline;
      text-underline-offset: 2px;
    }
    .guide-link:hover {
      color: var(--text);
    }

    /* Main Container */
    main {
      flex: 1;
      max-width: 1440px;
      width: 100%;
      margin: 0 auto;
      padding: 1rem 1.5rem 2.5rem 1.5rem;
      display: flex;
      flex-direction: column;
      gap: 0.85rem;
    }

    /* Metrics Grid */
    .metrics-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 0.55rem;
    }
    .metric-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 0.65rem 0.85rem;
      cursor: pointer;
      transition: border-color 0.12s ease;
    }
    .metric-card:hover {
      border-color: var(--text-subtle);
    }
    .metric-card.active-filter {
      border-color: var(--primary);
      background: var(--primary-subtle);
    }
    .metric-label {
      font-size: 0.68rem;
      font-weight: 600;
      color: var(--text-subtle);
      text-transform: uppercase;
      letter-spacing: 0.04em;
      margin-bottom: 0.2rem;
    }
    .metric-val {
      font-size: 1.25rem;
      font-weight: 700;
      color: var(--text);
      font-family: 'JetBrains Mono', monospace;
      letter-spacing: -0.02em;
    }

    /* Toolbar / Filters */
    .toolbar {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 0.65rem 0.85rem;
      display: flex;
      flex-direction: column;
      gap: 0.55rem;
    }
    .toolbar-row {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 0.65rem;
    }
    .search-box {
      flex: 1;
      min-width: 260px;
      position: relative;
    }
    .search-box input {
      width: 100%;
      background: var(--surface-subtle);
      border: 1px solid var(--border);
      border-radius: 5px;
      padding: 0.45rem 0.8rem 0.45rem 2rem;
      color: var(--text);
      font-size: 0.82rem;
      font-family: inherit;
      outline: none;
      transition: border-color 0.12s ease;
    }
    .search-box input:focus {
      border-color: var(--primary);
    }
    .search-icon {
      position: absolute;
      left: 0.7rem;
      top: 50%;
      transform: translateY(-50%);
      color: var(--text-subtle);
      font-size: 0.8rem;
      pointer-events: none;
    }

    .select-dropdown {
      background: var(--surface-subtle);
      border: 1px solid var(--border);
      border-radius: 5px;
      padding: 0.45rem 0.65rem;
      color: var(--text);
      font-size: 0.78rem;
      outline: none;
      cursor: pointer;
    }

    .filter-chips {
      display: flex;
      flex-wrap: wrap;
      gap: 0.3rem;
    }
    .chip {
      background: var(--chip-bg);
      border: 1px solid var(--chip-border);
      color: var(--text-muted);
      padding: 0.25rem 0.6rem;
      border-radius: 4px;
      font-size: 0.72rem;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.12s ease;
      white-space: nowrap;
    }
    .chip:hover {
      background: var(--surface-hover);
      color: var(--text);
      border-color: var(--text-subtle);
    }
    .chip.active {
      background: var(--chip-active-bg);
      color: var(--chip-active-text);
      border-color: var(--chip-active-bg);
      font-weight: 600;
    }

    /* Table */
    .table-container {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 6px;
      overflow-x: auto;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      text-align: left;
    }
    thead {
      background: var(--table-header);
      border-bottom: 1px solid var(--border);
    }
    th {
      padding: 0.55rem 0.75rem;
      font-size: 0.68rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: var(--text-subtle);
    }
    tbody tr {
      border-bottom: 1px solid var(--table-row-border);
      transition: background-color 0.1s ease;
    }
    tbody tr:hover {
      background-color: var(--table-row-hover);
    }
    td {
      padding: 0.6rem 0.75rem;
      font-size: 0.8rem;
      vertical-align: middle;
    }

    .row-id {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.7rem;
      color: var(--text-subtle);
    }
    .company-cell {
      display: flex;
      align-items: center;
      gap: 0.55rem;
    }
    .company-avatar {
      width: 24px;
      height: 24px;
      border-radius: 4px;
      background: var(--avatar-bg);
      border: 1px solid var(--avatar-border);
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 600;
      font-size: 0.7rem;
      color: var(--avatar-text);
      flex-shrink: 0;
    }
    .company-name {
      font-weight: 600;
      color: var(--text);
    }
    .role-title {
      font-weight: 500;
      color: var(--text);
      text-decoration: none;
      display: inline-block;
      line-height: 1.35;
    }
    .role-title:hover {
      color: var(--primary);
    }

    /* Badges */
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 0.2rem;
      padding: 1px 5px;
      border-radius: 3px;
      font-size: 0.68rem;
      font-weight: 500;
      white-space: nowrap;
      background: var(--badge-bg);
      border: 1px solid var(--badge-border);
      color: var(--badge-text);
    }
    .badge-applied {
      background: var(--success-subtle);
      border-color: rgba(16, 185, 129, 0.25);
      color: var(--success);
    }
    .badge-portal {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.65rem;
    }
    .badge-skills {
      display: inline-block;
      max-width: 180px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-size: 0.72rem;
      color: var(--text-subtle);
      font-family: 'JetBrains Mono', monospace;
    }

    /* Action Buttons */
    .action-group {
      display: flex;
      align-items: center;
      gap: 0.3rem;
    }
    .btn-apply-fast {
      background: var(--text);
      color: var(--bg);
      padding: 0.3rem 0.6rem;
      border-radius: 4px;
      font-size: 0.72rem;
      font-weight: 600;
      border: none;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 0.25rem;
      transition: opacity 0.12s ease;
    }
    .btn-apply-fast:hover {
      opacity: 0.85;
    }
    .btn-icon-sm {
      background: transparent;
      border: 1px solid var(--border);
      color: var(--text-muted);
      width: 24px;
      height: 24px;
      border-radius: 4px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      text-decoration: none;
      font-size: 0.72rem;
      transition: all 0.12s ease;
    }
    .btn-icon-sm:hover {
      background: var(--surface-hover);
      color: var(--text);
      border-color: var(--text-subtle);
    }

    /* Spinner */
    .scan-status-pill {
      display: inline-flex;
      align-items: center;
      gap: 0.35rem;
      padding: 0.2rem 0.5rem;
      border-radius: 4px;
      font-size: 0.7rem;
      background: var(--surface-subtle);
      border: 1px solid var(--border);
      color: var(--text-muted);
    }
    .spinner {
      width: 9px;
      height: 9px;
      border: 1.5px solid var(--border);
      border-top-color: var(--primary);
      border-radius: 50%;
      animation: spin 0.7s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }

    /* Toast */
    #toast {
      position: fixed;
      bottom: 1.25rem;
      right: 1.25rem;
      background: var(--surface);
      color: var(--text);
      padding: 0.55rem 0.9rem;
      border-radius: 5px;
      border: 1px solid var(--border);
      box-shadow: 0 4px 14px rgba(0,0,0,0.2);
      display: flex;
      align-items: center;
      gap: 0.45rem;
      font-size: 0.78rem;
      font-weight: 500;
      z-index: 100;
      opacity: 0;
      pointer-events: none;
      transform: translateY(6px);
      transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
    }
    #toast.show {
      opacity: 1;
      pointer-events: auto;
      transform: translateY(0);
    }

    /* Pagination */
    .pagination {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0.4rem 0;
      font-size: 0.75rem;
      color: var(--text-subtle);
    }
    .page-controls {
      display: flex;
      gap: 0.3rem;
    }
    .page-btn {
      background: var(--surface);
      border: 1px solid var(--border);
      color: var(--text);
      padding: 0.25rem 0.55rem;
      border-radius: 4px;
      font-size: 0.74rem;
      font-weight: 500;
      cursor: pointer;
    }
    .page-btn:hover:not(:disabled) {
      background: var(--surface-hover);
    }
    .page-btn:disabled {
      opacity: 0.35;
      cursor: not-allowed;
    }
  </style>
</head>
<body>

  <!-- Top Header -->
  <header>
    <div class="brand">
      <div class="brand-icon">AJ</div>
      <div>
        <span class="brand-title">AutoJobHunt</span>
        <span class="brand-badge">career-ops</span>
      </div>
    </div>

    <div class="header-actions">
      <div id="scan-indicator" class="scan-status-pill" style="display:none;">
        <div class="spinner"></div>
        <span id="scan-status-text">Scanning...</span>
      </div>

      <button class="btn" onclick="triggerScan('apis')">Scan ATS</button>
      <button class="btn" onclick="triggerScan('startups')">Scan Startups</button>
      <button class="btn btn-primary" onclick="triggerScan('all')">Run Sweep</button>
      <button class="btn" onclick="loadOpportunities()" title="Reload data">Refresh</button>
      <button class="btn-theme" onclick="toggleTheme()" id="theme-btn" title="Toggle theme">☀️</button>
    </div>
  </header>

  <!-- Clean Info Strip -->
  <div class="info-strip">
    <div class="info-strip-left">
      <span class="status-dot"></span>
      <span>Browser Session Active · Links open directly in your tabs with active logins</span>
    </div>
    <div class="info-strip-right">
      <a href="javascript:(function(){var s=document.createElement('script');s.src='http://127.0.0.1:5000/autofill.js?t='+Date.now();document.body.appendChild(s);})();" 
         class="bookmarklet-pill" 
         title="Drag this bookmarklet to your browser Bookmarks Bar">
        📌 Bookmarklet: AutoFill
      </a>
      <span class="guide-link" onclick="showExtensionModal()">Extension Guide</span>
    </div>
  </div>

  <!-- Main Content Area -->
  <main>
    <!-- Summary Metrics Grid -->
    <div class="metrics-grid">
      <div class="metric-card active-filter" onclick="filterCategory('All')">
        <div class="metric-label">Total Jobs</div>
        <div class="metric-val" id="metric-total">...</div>
      </div>
      <div class="metric-card" onclick="filterCategory('Data Analyst')">
        <div class="metric-label">Data Analysts</div>
        <div class="metric-val" id="metric-da">...</div>
      </div>
      <div class="metric-card" onclick="filterCategory('Business Analyst')">
        <div class="metric-label">Business Analysts</div>
        <div class="metric-val" id="metric-ba">...</div>
      </div>
      <div class="metric-card" onclick="filterCategory('Domain Analyst')">
        <div class="metric-label">Domain Analysts</div>
        <div class="metric-val" id="metric-domain">...</div>
      </div>
      <div class="metric-card" onclick="filterCategory('BI & Power BI')">
        <div class="metric-label">BI & Power BI</div>
        <div class="metric-val" id="metric-bi">...</div>
      </div>
      <div class="metric-card" onclick="filterCategory('SQL / MIS / Reporting')">
        <div class="metric-label">SQL / Reporting</div>
        <div class="metric-val" id="metric-sql">...</div>
      </div>
      <div class="metric-card" onclick="filterCategory('Applied')">
        <div class="metric-label">Applied</div>
        <div class="metric-val" id="metric-applied">...</div>
      </div>
    </div>

    <!-- Toolbar: Search & Chips -->
    <div class="toolbar">
      <div class="toolbar-row">
        <div class="search-box">
          <span class="search-icon">🔍</span>
          <input type="text" id="search-input" placeholder="Search by title, company, skills, or city..." onkeyup="handleSearch()">
        </div>

        <div style="display:flex; gap:0.4rem; align-items:center;">
          <select id="location-select" class="select-dropdown" onchange="handleSearch()">
            <option value="All">All Locations</option>
            <option value="Bengaluru">Bengaluru</option>
            <option value="Remote">Remote</option>
            <option value="Pune">Pune</option>
            <option value="India">India</option>
          </select>

          <select id="pagesize-select" class="select-dropdown" onchange="changePageSize()">
            <option value="25">25 / page</option>
            <option value="50" selected>50 / page</option>
            <option value="100">100 / page</option>
            <option value="1000">Show All</option>
          </select>
        </div>
      </div>

      <div class="filter-chips">
        <div class="chip active" data-cat="All" onclick="filterCategory('All')">All Roles</div>
        <div class="chip" data-cat="Data Analyst" onclick="filterCategory('Data Analyst')">Data Analyst</div>
        <div class="chip" data-cat="Business Analyst" onclick="filterCategory('Business Analyst')">Business Analyst</div>
        <div class="chip" data-cat="Financial Analyst" onclick="filterCategory('Financial Analyst')">Financial Analyst</div>
        <div class="chip" data-cat="Marketing Analyst" onclick="filterCategory('Marketing Analyst')">Marketing Analyst</div>
        <div class="chip" data-cat="Operations Analyst" onclick="filterCategory('Operations Analyst')">Operations Analyst</div>
        <div class="chip" data-cat="Product Analyst" onclick="filterCategory('Product Analyst')">Product Analyst</div>
        <div class="chip" data-cat="Supply Chain Analyst" onclick="filterCategory('Supply Chain Analyst')">Supply Chain</div>
        <div class="chip" data-cat="BI & Power BI" onclick="filterCategory('BI & Power BI')">Power BI & BI</div>
        <div class="chip" data-cat="SQL / MIS / Reporting" onclick="filterCategory('SQL / MIS / Reporting')">SQL / Reporting</div>
        <div class="chip" data-cat="Applied" onclick="filterCategory('Applied')">Applied</div>
      </div>
    </div>

    <!-- Opportunities Table -->
    <div class="table-container">
      <table>
        <thead>
          <tr>
            <th style="width: 45px;">#</th>
            <th style="width: 210px;">Company</th>
            <th>Role Title</th>
            <th style="width: 150px;">Location</th>
            <th style="width: 120px;">Platform</th>
            <th style="width: 180px;">Key Skills</th>
            <th style="width: 150px; text-align: right;">Action</th>
          </tr>
        </thead>
        <tbody id="opportunities-tbody">
          <tr>
            <td colspan="7" style="text-align:center; padding: 2.5rem; color: var(--text-muted);">
              Loading opportunities...
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination Footer -->
    <div class="pagination">
      <div id="pagination-info">Showing 0 of 0 opportunities</div>
      <div class="page-controls">
        <button class="page-btn" id="prev-btn" onclick="prevPage()" disabled>Previous</button>
        <button class="page-btn" id="next-btn" onclick="nextPage()">Next</button>
      </div>
    </div>
  </main>

  <!-- Floating Toast -->
  <div id="toast">
    <span id="toast-msg">Notification message</span>
  </div>

  <script>
    let allOpportunities = [];
    let filteredList = [];
    let currentPage = 1;
    let pageSize = 50;
    let activeCategory = 'All';

    function initTheme() {
      const saved = localStorage.getItem('co_theme') || (window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
      document.documentElement.setAttribute('data-theme', saved);
      updateThemeIcon(saved);
    }
    function toggleTheme() {
      const current = document.documentElement.getAttribute('data-theme') || 'dark';
      const next = current === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      localStorage.setItem('co_theme', next);
      updateThemeIcon(next);
    }
    function updateThemeIcon(t) {
      const btn = document.getElementById('theme-btn');
      if (btn) btn.innerText = t === 'dark' ? '☀️' : '🌙';
    }

    async function loadOpportunities() {
      try {
        const res = await fetch('/api/opportunities');
        allOpportunities = await res.json();
        
        // Update stats
        const statsRes = await fetch('/api/stats');
        const stats = await statsRes.json();
        document.getElementById('metric-total').innerText = stats.total || 0;
        document.getElementById('metric-da').innerText = stats.da || 0;
        document.getElementById('metric-ba').innerText = stats.ba || 0;
        document.getElementById('metric-domain').innerText = stats.domain || 0;
        document.getElementById('metric-bi').innerText = stats.powerbi || 0;
        document.getElementById('metric-sql').innerText = stats.sql_mis || 0;
        document.getElementById('metric-applied').innerText = stats.applied || 0;

        applyFilters();
      } catch (err) {
        showToast('Error loading opportunities: ' + err.message);
      }
    }

    function filterCategory(cat) {
      activeCategory = cat;
      document.querySelectorAll('.chip').forEach(c => {
        c.classList.toggle('active', c.dataset.cat === cat);
      });
      document.querySelectorAll('.metric-card').forEach(m => m.classList.remove('active-filter'));
      currentPage = 1;
      applyFilters();
    }

    function handleSearch() {
      currentPage = 1;
      applyFilters();
    }

    function applyFilters() {
      const q = document.getElementById('search-input').value.toLowerCase().trim();
      const locFilter = document.getElementById('location-select').value.toLowerCase();

      filteredList = allOpportunities.filter(o => {
        if (activeCategory === 'Applied' && !o.is_applied) return false;
        if (activeCategory !== 'All' && activeCategory !== 'Applied') {
          if (!o.categories || !o.categories.includes(activeCategory)) return false;
        }

        if (locFilter !== 'all') {
          if (!o.location.toLowerCase().includes(locFilter)) return false;
        }

        if (q) {
          const matchQuery = 
            o.company.toLowerCase().includes(q) ||
            o.role.toLowerCase().includes(q) ||
            o.location.toLowerCase().includes(q) ||
            o.skills.toLowerCase().includes(q);
          if (!matchQuery) return false;
        }

        return true;
      });

      renderTable();
    }

    function renderTable() {
      const tbody = document.getElementById('opportunities-tbody');
      const start = (currentPage - 1) * pageSize;
      const end = start + pageSize;
      const pageItems = filteredList.slice(start, end);

      if (pageItems.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding: 2.5rem; color: var(--text-muted);">
          No matching opportunities found.
        </td></tr>`;
        document.getElementById('pagination-info').innerText = '0 opportunities';
        document.getElementById('prev-btn').disabled = true;
        document.getElementById('next-btn').disabled = true;
        return;
      }

      tbody.innerHTML = pageItems.map(o => {
        const initial = (o.company || 'C').charAt(0).toUpperCase();
        
        let tags = '';
        if (o.is_applied) {
          tags += '<span class="badge badge-applied">Applied</span> ';
        }
        if (o.categories && o.categories.includes('Internship')) {
          tags += '<span class="badge">Intern</span> ';
        }
        if (o.categories && o.categories.includes('Contract')) {
          tags += '<span class="badge">Contract</span> ';
        }

        return `
          <tr>
            <td class="row-id">#${o.id}</td>
            <td>
              <div class="company-cell">
                <div class="company-avatar">${initial}</div>
                <div class="company-name">${escapeHtml(o.company)}</div>
              </div>
            </td>
            <td>
              <div>
                <a href="${escapeHtml(o.url)}" target="_blank" class="role-title">${escapeHtml(o.role)}</a>
                <div style="margin-top: 0.2rem;">${tags}</div>
              </div>
            </td>
            <td>
              <span style="color: var(--text-muted); font-size: 0.78rem;">${escapeHtml(o.location || 'Bengaluru')}</span>
            </td>
            <td>
              <span class="badge badge-portal">${escapeHtml(o.portal)}</span>
            </td>
            <td>
              <span class="badge-skills" title="${escapeHtml(o.skills)}">${escapeHtml(o.skills || 'SQL, Python')}</span>
            </td>
            <td style="text-align: right;">
              <div class="action-group" style="justify-content: flex-end;">
                <button class="btn-apply-fast" onclick="launchAutoApply(${o.id}, '${escapeJs(o.company)}', '${escapeJs(o.role)}', '${escapeJs(o.url)}')">
                  Auto-Apply
                </button>
                <a href="${escapeHtml(o.url)}" target="_blank" class="btn-icon-sm" title="Open Posting">
                  ↗
                </a>
                <button class="btn-icon-sm" onclick="markApplied('${escapeJs(o.company)}', '${escapeJs(o.role)}', '${escapeJs(o.url)}', ${o.id})" title="Mark Applied">
                  ✓
                </button>
              </div>
            </td>
          </tr>
        `;
      }).join('');

      document.getElementById('pagination-info').innerText = 
        `Showing ${start + 1} to ${Math.min(end, filteredList.length)} of ${filteredList.length} opportunities`;
      
      document.getElementById('prev-btn').disabled = currentPage <= 1;
      document.getElementById('next-btn').disabled = end >= filteredList.length;
    }

    function launchAutoApply(rowId, company, role, url) {
      if (!url || url === '#' || !url.startsWith('http')) {
        showToast('No direct apply URL available.');
        return;
      }
      window.open(url, '_blank');
      showToast(`Opened ${company}. Use your bookmarklet to autofill.`);
    }

    function showExtensionModal() {
      document.getElementById('guide-modal').style.display = 'flex';
    }
    function closeExtensionModal() {
      document.getElementById('guide-modal').style.display = 'none';
    }

    async function markApplied(company, role, url, id) {
      try {
        const res = await fetch('/api/mark-applied', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ company, role, url })
        });
        const data = await res.json();
        showToast(`Marked ${company} as Applied!`);
        
        const item = allOpportunities.find(o => o.id === id);
        if (item) item.is_applied = true;
        applyFilters();
      } catch (err) {
        showToast('Error marking applied: ' + err.message);
      }
    }

    async function triggerScan(channel) {
      showToast(`Starting ${channel} scan in background...`);
      try {
        const res = await fetch('/api/scan', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ channel })
        });
        const data = await res.json();
        if (data.error) {
          showToast(data.error);
        } else {
          pollScanStatus();
        }
      } catch (err) {
        showToast('Scan failed: ' + err.message);
      }
    }

    async function pollScanStatus() {
      const pill = document.getElementById('scan-indicator');
      const text = document.getElementById('scan-status-text');
      pill.style.display = 'inline-flex';

      const interval = setInterval(async () => {
        try {
          const res = await fetch('/api/scan-status');
          const data = await res.json();
          if (data.is_running) {
            text.innerText = `Scanning (${data.channel})...`;
          } else {
            clearInterval(interval);
            pill.style.display = 'none';
            showToast('Scan completed. Refreshing...');
            loadOpportunities();
          }
        } catch {
          clearInterval(interval);
          pill.style.display = 'none';
        }
      }, 3000);
    }

    function changePageSize() {
      pageSize = parseInt(document.getElementById('pagesize-select').value);
      currentPage = 1;
      renderTable();
    }
    function prevPage() {
      if (currentPage > 1) {
        currentPage--;
        renderTable();
      }
    }
    function nextPage() {
      if ((currentPage * pageSize) < filteredList.length) {
        currentPage++;
        renderTable();
      }
    }

    function showToast(msg) {
      const toast = document.getElementById('toast');
      document.getElementById('toast-msg').innerText = msg;
      toast.classList.add('show');
      setTimeout(() => toast.classList.remove('show'), 4000);
    }

    function escapeHtml(str) {
      if (!str) return '';
      return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }
    function escapeJs(str) {
      if (!str) return '';
      return String(str).replace(/'/g, "\'").replace(/"/g, '\"');
    }

    window.addEventListener('DOMContentLoaded', () => {
      initTheme();
      loadOpportunities();
    });
  </script>

  <!-- Clean Modal -->
  <div id="guide-modal" style="display:none; position:fixed; inset:0; background:rgba(0,0,0,0.6); z-index:999999; align-items:center; justify-content:center; backdrop-filter:blur(3px);">
    <div style="background:var(--surface); border:1px solid var(--border); border-radius:8px; max-width:500px; width:90%; padding:20px; box-shadow:0 10px 30px rgba(0,0,0,0.3);">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
        <h3 style="margin:0; font-size:15px; font-weight:600; color:var(--text);">AutoFill Setup</h3>
        <button onclick="closeExtensionModal()" style="background:transparent; border:none; color:var(--text-subtle); font-size:18px; cursor:pointer;">✕</button>
      </div>

      <p style="font-size:13px; color:var(--text-muted); line-height:1.5; margin-bottom:12px;">
        Open job postings directly in your browser so all your pre-existing session logins remain active.
      </p>

      <div style="background:var(--surface-subtle); border-radius:6px; padding:12px; margin-bottom:10px; border:1px solid var(--border);">
        <strong style="color:var(--text); font-size:12.5px;">1. Bookmarklet (Zero Install)</strong>
        <p style="font-size:12px; color:var(--text-muted); margin-top:4px; line-height:1.4;">
          Drag the <strong>[📌 Bookmarklet: AutoFill]</strong> link from the top banner to your Bookmarks Bar. When on any job application page, click it to fill candidate details instantly.
        </p>
      </div>

      <div style="background:var(--surface-subtle); border-radius:6px; padding:12px; margin-bottom:16px; border:1px solid var(--border);">
        <strong style="color:var(--text); font-size:12.5px;">2. Chrome / Brave Extension</strong>
        <p style="font-size:12px; color:var(--text-muted); margin-top:4px; line-height:1.4;">
          Go to <code>chrome://extensions</code>, toggle <strong>Developer mode</strong>, and click <strong>Load unpacked</strong> selecting the <code>extension</code> folder in this repo.
        </p>
      </div>

      <button onclick="closeExtensionModal()" class="btn btn-primary" style="width:100%; justify-content:center; padding:8px;">
        Done
      </button>
    </div>
  </div>
</body>
</html>"""

def main():
    port = 5000
    server_address = ("127.0.0.1", port)
    
    # Try finding an open port starting at 5000
    server = None
    for p in range(5000, 5010):
        try:
            server_address = ("127.0.0.1", p)
            server = ThreadedHTTPServer(server_address, DashboardHandler)
            port = p
            break
        except OSError:
            continue

    if not server:
        print("Error: Could not bind to port 5000-5010.")
        sys.exit(1)

    url = f"http://127.0.0.1:{port}"
    print("=" * 65)
    print(f"⚡ AutoJobHunt 1-Click Auto-Apply Dashboard (based on career-ops) running at: {url}")
    print(f"📊 Serving 600+ opportunities from: {OPPORTUNITIES_CSV}")
    print("🚀 Opening dashboard in your default browser...")
    print("   Press Ctrl+C in this terminal to stop the server.")
    print("=" * 65)

    # Open browser automatically
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down AutoJobHunt Dashboard server. Goodbye!")
        server.shutdown()

if __name__ == "__main__":
    main()
