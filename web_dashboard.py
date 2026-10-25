#!/usr/bin/env python3
"""
web_dashboard.py — Localhost Browser Dashboard for Career-Ops
Lists all opportunities from opportunities.xlsx / opportunities.csv and enables
1-click tailored auto-fill applications and background job scanning from the browser.

Zero external web dependencies — runs entirely on Python standard library (http.server).
"""

import os
import sys
import csv
import json
import time
import re
import urllib.parse
import subprocess
import threading
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
OPPORTUNITIES_CSV = os.path.join(PROJECT_ROOT, "opportunities.csv")
OPPORTUNITIES_XLSX = os.path.join(PROJECT_ROOT, "opportunities.xlsx")
PIPELINE_FILE = os.path.join(PROJECT_ROOT, "data", "pipeline.md")
APPLICATIONS_FILE = os.path.join(PROJECT_ROOT, "data", "applications.md")
STATUS_LOG_FILE = os.path.join(PROJECT_ROOT, "data", "status-log.tsv")

PYTHON_BIN = os.path.join(PROJECT_ROOT, ".venv", "bin", "python")
if not os.path.exists(PYTHON_BIN):
    PYTHON_BIN = sys.executable

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
    
    if any(w in t for w in ["intern", "internship", "trainee"]):
        categories.append("Internship")
    if "contract" in t or "contractor" in t or "fixed term" in t:
        categories.append("Contract")
    if any(k in t for k in ["machine learning", "ml", "ai", "artificial intelligence", "data scientist", "deep learning", "computer vision", "nlp", "genai", "generative ai", "llm", "research", "r&d"]):
        categories.append("AI / ML")
    if any(k in t for k in ["python", "fastapi", "flask", "django", "backend"]):
        categories.append("Python / Backend")
    if any(k in t for k in ["data analyst", "business analyst", "bi ", "power bi", "tableau", "analytics analyst", "reporting"]):
        categories.append("Data Analytics")
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
    internships = sum(1 for o in opps if "Internship" in o["categories"])
    contracts = sum(1 for o in opps if "Contract" in o["categories"])
    aiml = sum(1 for o in opps if "AI / ML" in o["categories"])
    python = sum(1 for o in opps if "Python / Backend" in o["categories"])
    analytics = sum(1 for o in opps if "Data Analytics" in o["categories"])
    applied = sum(1 for o in opps if o["is_applied"])
    
    return {
        "total": total,
        "internships": internships,
        "contracts": contracts,
        "aiml": aiml,
        "python": python,
        "analytics": analytics,
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
        elif path == "/api/opportunities":
            opps = load_opportunities_data()
            self.send_json(opps)
        elif path == "/api/stats":
            stats = get_stats()
            self.send_json(stats)
        elif path == "/api/scan-status":
            with SCAN_LOCK:
                self.send_json(ACTIVE_SCAN)
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
            if not row_id:
                self.send_json({"error": "Missing row id"}, 400)
                return
            
            # Look up company and role for confirmation message
            opps = load_opportunities_data()
            target = next((o for o in opps if o["id"] == int(row_id)), None)
            comp = target["company"] if target else "Company"
            role = target["role"] if target else "Role"

            # Launch Playwright autofill assistant
            threading.Thread(target=run_apply_worker, args=(row_id,), daemon=True).start()
            
            self.send_json({
                "status": "launched",
                "message": f"Opening Chromium assistant for #{row_id}: {comp} — {role}. Check your screen!"
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
        else:
            self.send_response(404)
            self.end_headers()

# Single-page modern dashboard application
HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Career-Ops • 1-Click Auto-Apply Dashboard</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #0b0f19;
      --card-bg: #111827;
      --card-hover: #172033;
      --border: #1f293d;
      --border-accent: #2e3d5b;
      --text-main: #f3f4f6;
      --text-muted: #9ca3af;
      --text-subtle: #6b7280;
      --primary: #3b82f6;
      --primary-hover: #2563eb;
      --primary-glow: rgba(59, 130, 246, 0.25);
      --accent: #8b5cf6;
      --emerald: #10b981;
      --emerald-glow: rgba(16, 185, 129, 0.25);
      --amber: #f59e0b;
      --rose: #f43f5e;
      --cyan: #06b6d4;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background-color: var(--bg);
      color: var(--text-main);
      font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      overflow-x: hidden;
    }

    /* Top Navigation */
    header {
      background: rgba(17, 24, 39, 0.85);
      backdrop-filter: blur(16px);
      border-bottom: 1px solid var(--border);
      position: sticky;
      top: 0;
      z-index: 50;
      padding: 0.85rem 2rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1.5rem;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }
    .brand-icon {
      width: 38px;
      height: 38px;
      background: linear-gradient(135deg, #3b82f6, #8b5cf6);
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 1.25rem;
      box-shadow: 0 0 20px var(--primary-glow);
    }
    .brand h1 {
      font-size: 1.25rem;
      font-weight: 800;
      letter-spacing: -0.02em;
      background: linear-gradient(90deg, #f3f4f6, #93c5fd);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    .brand p {
      font-size: 0.75rem;
      color: var(--text-muted);
      font-weight: 500;
    }

    .header-actions {
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }

    .btn {
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.55rem 1rem;
      border-radius: 8px;
      font-size: 0.82rem;
      font-weight: 600;
      cursor: pointer;
      border: 1px solid transparent;
      transition: all 0.18s ease;
      text-decoration: none;
    }
    .btn-primary {
      background: linear-gradient(135deg, #2563eb, #1d4ed8);
      color: white;
      box-shadow: 0 2px 10px var(--primary-glow);
    }
    .btn-primary:hover {
      background: linear-gradient(135deg, #1d4ed8, #1e40af);
      transform: translateY(-1px);
    }
    .btn-outline {
      background: #1e293b;
      border-color: var(--border-accent);
      color: var(--text-main);
    }
    .btn-outline:hover {
      background: #334155;
      color: white;
    }
    .btn-emerald {
      background: linear-gradient(135deg, #059669, #10b981);
      color: white;
      box-shadow: 0 2px 10px var(--emerald-glow);
    }
    .btn-emerald:hover {
      background: linear-gradient(135deg, #047857, #059669);
      transform: translateY(-1px);
    }

    /* Main Container */
    main {
      flex: 1;
      max-width: 1560px;
      width: 100%;
      margin: 0 auto;
      padding: 1.75rem 2rem;
      display: flex;
      flex-direction: column;
      gap: 1.5rem;
    }

    /* Metrics Grid */
    .metrics-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 1rem;
    }
    .metric-card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1rem 1.25rem;
      position: relative;
      overflow: hidden;
      cursor: pointer;
      transition: all 0.2s ease;
    }
    .metric-card:hover {
      border-color: var(--border-accent);
      transform: translateY(-2px);
    }
    .metric-card.active-filter {
      border-color: var(--primary);
      box-shadow: 0 0 16px var(--primary-glow);
      background: #172033;
    }
    .metric-label {
      font-size: 0.78rem;
      font-weight: 600;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.04em;
      margin-bottom: 0.35rem;
      display: flex;
      align-items: center;
      gap: 0.35rem;
    }
    .metric-val {
      font-size: 1.75rem;
      font-weight: 800;
      color: var(--text-main);
      font-family: 'JetBrains Mono', monospace;
    }

    /* Toolbar / Filter Bar */
    .toolbar {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1rem 1.25rem;
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }
    .toolbar-row {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
    }
    .search-box {
      flex: 1;
      min-width: 280px;
      position: relative;
    }
    .search-box input {
      width: 100%;
      background: #0b0f19;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 0.65rem 1rem 0.65rem 2.4rem;
      color: white;
      font-size: 0.88rem;
      font-family: inherit;
      outline: none;
      transition: border 0.15s ease;
    }
    .search-box input:focus {
      border-color: var(--primary);
      box-shadow: 0 0 10px var(--primary-glow);
    }
    .search-icon {
      position: absolute;
      left: 0.85rem;
      top: 50%;
      transform: translateY(-50%);
      color: var(--text-subtle);
      font-size: 0.95rem;
    }

    .filter-chips {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
    }
    .chip {
      background: #172033;
      border: 1px solid var(--border);
      color: var(--text-muted);
      padding: 0.4rem 0.85rem;
      border-radius: 20px;
      font-size: 0.78rem;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.15s ease;
      display: flex;
      align-items: center;
      gap: 0.4rem;
    }
    .chip:hover {
      background: #1e293b;
      color: var(--text-main);
      border-color: var(--border-accent);
    }
    .chip.active {
      background: var(--primary);
      color: white;
      border-color: var(--primary);
      box-shadow: 0 2px 8px var(--primary-glow);
    }

    .select-dropdown {
      background: #0b0f19;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 0.6rem 0.85rem;
      color: var(--text-main);
      font-size: 0.82rem;
      outline: none;
      cursor: pointer;
    }

    /* Opportunity Table / List */
    .table-container {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 4px 20px rgba(0,0,0,0.25);
    }
    table {
      width: 100%;
      border-collapse: collapse;
      text-align: left;
    }
    thead {
      background: #0f172a;
      border-bottom: 1px solid var(--border);
    }
    th {
      padding: 0.85rem 1rem;
      font-size: 0.75rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-muted);
    }
    tbody tr {
      border-bottom: 1px solid #162033;
      transition: background 0.15s ease;
    }
    tbody tr:hover {
      background: var(--card-hover);
    }
    td {
      padding: 1rem 1rem;
      font-size: 0.84rem;
      vertical-align: middle;
    }

    .row-id {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.76rem;
      color: var(--text-subtle);
      font-weight: 600;
    }
    .company-cell {
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }
    .company-avatar {
      width: 34px;
      height: 34px;
      border-radius: 8px;
      background: #1e293b;
      border: 1px solid var(--border-accent);
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 800;
      font-size: 0.82rem;
      color: #93c5fd;
      flex-shrink: 0;
    }
    .company-name {
      font-weight: 700;
      color: var(--text-main);
    }
    .role-title {
      font-weight: 600;
      color: #e2e8f0;
      text-decoration: none;
      display: inline-block;
      transition: color 0.15s ease;
    }
    .role-title:hover {
      color: var(--primary);
    }

    .badge {
      display: inline-flex;
      align-items: center;
      gap: 0.3rem;
      padding: 0.2rem 0.55rem;
      border-radius: 6px;
      font-size: 0.72rem;
      font-weight: 600;
      white-space: nowrap;
    }
    .badge-portal { background: rgba(59, 130, 246, 0.15); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); }
    .badge-intern { background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }
    .badge-contract { background: rgba(139, 92, 246, 0.15); color: #c084fc; border: 1px solid rgba(139, 92, 246, 0.3); }
    .badge-applied { background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }
    .badge-skills {
      display: inline-block;
      max-width: 220px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-size: 0.75rem;
      color: var(--text-muted);
      font-family: 'JetBrains Mono', monospace;
    }

    .action-group {
      display: flex;
      align-items: center;
      gap: 0.45rem;
    }

    .btn-apply-fast {
      background: linear-gradient(135deg, #059669, #10b981);
      color: white;
      padding: 0.45rem 0.85rem;
      border-radius: 6px;
      font-size: 0.78rem;
      font-weight: 700;
      border: none;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 0.35rem;
      box-shadow: 0 2px 8px var(--emerald-glow);
      transition: all 0.15s ease;
    }
    .btn-apply-fast:hover {
      background: linear-gradient(135deg, #047857, #059669);
      transform: translateY(-1px);
    }
    .btn-apply-fast:disabled {
      opacity: 0.5;
      cursor: not-allowed;
      transform: none;
    }

    .btn-icon-sm {
      background: #1e293b;
      border: 1px solid var(--border);
      color: var(--text-muted);
      width: 30px;
      height: 30px;
      border-radius: 6px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      text-decoration: none;
      transition: all 0.15s ease;
    }
    .btn-icon-sm:hover {
      color: white;
      background: #334155;
      border-color: var(--border-accent);
    }

    /* Scan Modal / Drawer */
    .scan-status-pill {
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      padding: 0.35rem 0.75rem;
      border-radius: 20px;
      font-size: 0.75rem;
      font-weight: 600;
      background: #1e293b;
      border: 1px solid var(--border);
      color: var(--text-muted);
    }
    .spinner {
      width: 12px;
      height: 12px;
      border: 2px solid rgba(255,255,255,0.2);
      border-top-color: var(--primary);
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }

    /* Toast Notification */
    #toast {
      position: fixed;
      bottom: 2rem;
      right: 2rem;
      background: #1e293b;
      color: white;
      padding: 0.9rem 1.4rem;
      border-radius: 10px;
      border: 1px solid var(--border-accent);
      box-shadow: 0 10px 30px rgba(0,0,0,0.5);
      display: flex;
      align-items: center;
      gap: 0.75rem;
      font-size: 0.88rem;
      font-weight: 600;
      z-index: 100;
      opacity: 0;
      pointer-events: none;
      transform: translateY(12px);
      transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
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
      padding: 1rem 0;
      font-size: 0.84rem;
      color: var(--text-muted);
    }
    .page-controls {
      display: flex;
      gap: 0.4rem;
    }
    .page-btn {
      background: var(--card-bg);
      border: 1px solid var(--border);
      color: var(--text-main);
      padding: 0.4rem 0.85rem;
      border-radius: 6px;
      font-weight: 600;
      cursor: pointer;
    }
    .page-btn:hover:not(:disabled) {
      background: #1e293b;
    }
    .page-btn:disabled {
      opacity: 0.4;
      cursor: not-allowed;
    }
  </style>
</head>
<body>

  <!-- Top Header -->
  <header>
    <div class="brand">
      <div class="brand-icon">⚡</div>
      <div>
        <h1>Career-Ops Dashboard</h1>
        <p>1-Click Playwright Auto-Apply & Job Pipeline Command Center</p>
      </div>
    </div>

    <div class="header-actions">
      <div id="scan-indicator" class="scan-status-pill" style="display:none;">
        <div class="spinner"></div>
        <span id="scan-status-text">Scanning web...</span>
      </div>

      <button class="btn btn-outline" onclick="triggerScan('apis')">
        🔍 Scan ATS APIs
      </button>

      <button class="btn btn-outline" onclick="triggerScan('startups')">
        🚀 Scan YC / HN
      </button>

      <button class="btn btn-primary" onclick="triggerScan('all')">
        ⚡ Run Full Sweep
      </button>

      <button class="btn btn-outline" onclick="loadOpportunities()" title="Reload list">
        🔄 Refresh
      </button>
    </div>
  </header>

  <!-- Main Content Area -->
  <main>
    <!-- Summary Metrics Grid -->
    <div class="metrics-grid">
      <div class="metric-card active-filter" onclick="filterCategory('All')">
        <div class="metric-label">📋 Total Jobs</div>
        <div class="metric-val" id="metric-total">...</div>
      </div>
      <div class="metric-card" onclick="filterCategory('AI / ML')">
        <div class="metric-label">🤖 AI / ML / Research</div>
        <div class="metric-val" id="metric-aiml">...</div>
      </div>
      <div class="metric-card" onclick="filterCategory('Internship')">
        <div class="metric-label">🎓 AI/ML Interns</div>
        <div class="metric-val" id="metric-intern">...</div>
      </div>
      <div class="metric-card" onclick="filterCategory('Python / Backend')">
        <div class="metric-label">🐍 Python & Backend</div>
        <div class="metric-val" id="metric-python">...</div>
      </div>
      <div class="metric-card" onclick="filterCategory('Contract')">
        <div class="metric-label">💼 Contract Roles</div>
        <div class="metric-val" id="metric-contract">...</div>
      </div>
      <div class="metric-card" onclick="filterCategory('Applied')">
        <div class="metric-label">✅ Applied</div>
        <div class="metric-val" id="metric-applied">...</div>
      </div>
    </div>

    <!-- Toolbar: Search & Chips -->
    <div class="toolbar">
      <div class="toolbar-row">
        <div class="search-box">
          <span class="search-icon">🔍</span>
          <input type="text" id="search-input" placeholder="Search by role, company, skills, or city..." onkeyup="handleSearch()">
        </div>

        <div style="display:flex; gap:0.5rem; align-items:center;">
          <select id="location-select" class="select-dropdown" onchange="handleSearch()">
            <option value="All">📍 All Locations</option>
            <option value="Bengaluru">Bengaluru</option>
            <option value="Remote">Remote / Worldwide</option>
            <option value="Pune">Pune</option>
            <option value="India">India</option>
          </select>

          <select id="pagesize-select" class="select-dropdown" onchange="changePageSize()">
            <option value="25">25 per page</option>
            <option value="50" selected>50 per page</option>
            <option value="100">100 per page</option>
            <option value="1000">Show All</option>
          </select>
        </div>
      </div>

      <div class="filter-chips">
        <div class="chip active" data-cat="All" onclick="filterCategory('All')">All Roles</div>
        <div class="chip" data-cat="AI / ML" onclick="filterCategory('AI / ML')">🤖 AI / ML</div>
        <div class="chip" data-cat="Internship" onclick="filterCategory('Internship')">🎓 Internships</div>
        <div class="chip" data-cat="Python / Backend" onclick="filterCategory('Python / Backend')">🐍 Python / Backend</div>
        <div class="chip" data-cat="Contract" onclick="filterCategory('Contract')">💼 Contract</div>
        <div class="chip" data-cat="Data Analytics" onclick="filterCategory('Data Analytics')">📊 Data Analytics</div>
        <div class="chip" data-cat="Applied" onclick="filterCategory('Applied')">✅ Applied Only</div>
      </div>
    </div>

    <!-- Opportunities Table -->
    <div class="table-container">
      <table>
        <thead>
          <tr>
            <th style="width: 50px;">#</th>
            <th style="width: 220px;">Company</th>
            <th>Role Title</th>
            <th style="width: 160px;">Location</th>
            <th style="width: 130px;">Platform</th>
            <th style="width: 200px;">Key Skills</th>
            <th style="width: 170px; text-align: right;">Action</th>
          </tr>
        </thead>
        <tbody id="opportunities-tbody">
          <tr>
            <td colspan="7" style="text-align:center; padding: 3rem; color: var(--text-muted);">
              Loading opportunities from spreadsheet...
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
    <span id="toast-icon">⚡</span>
    <span id="toast-msg">Notification message</span>
  </div>

  <script>
    let allOpportunities = [];
    let filteredList = [];
    let currentPage = 1;
    let pageSize = 50;
    let activeCategory = 'All';

    async function loadOpportunities() {
      try {
        const res = await fetch('/api/opportunities');
        allOpportunities = await res.json();
        
        // Update stats
        const statsRes = await fetch('/api/stats');
        const stats = await statsRes.json();
        document.getElementById('metric-total').innerText = stats.total;
        document.getElementById('metric-aiml').innerText = stats.aiml;
        document.getElementById('metric-intern').innerText = stats.internships;
        document.getElementById('metric-python').innerText = stats.python;
        document.getElementById('metric-contract').innerText = stats.contracts;
        document.getElementById('metric-applied').innerText = stats.applied;

        applyFilters();
      } catch (err) {
        showToast('⚠️ Error loading opportunities: ' + err.message);
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
        // Category filter
        if (activeCategory === 'Applied' && !o.is_applied) return false;
        if (activeCategory !== 'All' && activeCategory !== 'Applied') {
          if (!o.categories.includes(activeCategory)) return false;
        }

        // Location dropdown filter
        if (locFilter !== 'all') {
          if (!o.location.toLowerCase().includes(locFilter)) return false;
        }

        // Query search
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
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding: 3rem; color: var(--text-muted);">
          No matching opportunities found. Try adjusting your search or filters.
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
          tags += '<span class="badge badge-applied">✓ Applied</span> ';
        }
        if (o.categories.includes('Internship')) {
          tags += '<span class="badge badge-intern">🎓 Intern</span> ';
        }
        if (o.categories.includes('Contract')) {
          tags += '<span class="badge badge-contract">💼 Contract</span> ';
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
                <div style="margin-top: 0.25rem;">${tags}</div>
              </div>
            </td>
            <td>
              <span style="color: #cbd5e1; font-size: 0.8rem;">📍 ${escapeHtml(o.location || 'Bengaluru')}</span>
            </td>
            <td>
              <span class="badge badge-portal">${escapeHtml(o.portal)}</span>
            </td>
            <td>
              <span class="badge-skills" title="${escapeHtml(o.skills)}">${escapeHtml(o.skills || 'SQL, Python')}</span>
            </td>
            <td style="text-align: right;">
              <div class="action-group" style="justify-content: flex-end;">
                <button class="btn-apply-fast" onclick="launchAutoApply(${o.id}, '${escapeJs(o.company)}', '${escapeJs(o.role)}')">
                  ⚡ Auto-Apply
                </button>
                <a href="${escapeHtml(o.url)}" target="_blank" class="btn-icon-sm" title="Open Posting">
                  🌐
                </a>
                <button class="btn-icon-sm" onclick="markApplied('${escapeJs(o.company)}', '${escapeJs(o.role)}', '${escapeJs(o.url)}', ${o.id})" title="Mark as Applied">
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

    async function launchAutoApply(rowId, company, role) {
      showToast(`🚀 Opening Chromium Assistant for #${rowId} (${company})... Look at your screen!`);
      try {
        const res = await fetch('/api/apply', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ row: rowId })
        });
        const data = await res.json();
        if (data.status === 'launched') {
          showToast(`⚡ Browser opened! Review tailored answers and hit submit.`);
        }
      } catch (err) {
        showToast('⚠️ Error launching autofill: ' + err.message);
      }
    }

    async function markApplied(company, role, url, id) {
      try {
        const res = await fetch('/api/mark-applied', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ company, role, url })
        });
        const data = await res.json();
        showToast(`✅ Marked ${company} as Applied!`);
        
        // Update local object
        const item = allOpportunities.find(o => o.id === id);
        if (item) item.is_applied = true;
        applyFilters();
      } catch (err) {
        showToast('⚠️ Error marking applied: ' + err.message);
      }
    }

    async function triggerScan(channel) {
      showToast(`🔍 Starting ${channel.toUpperCase()} job scanner in background...`);
      try {
        const res = await fetch('/api/scan', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ channel })
        });
        const data = await res.json();
        if (data.error) {
          showToast(`⚠️ ${data.error}`);
        } else {
          pollScanStatus();
        }
      } catch (err) {
        showToast('⚠️ Scan request failed: ' + err.message);
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
            showToast('✓ Job scan completed! Refreshing opportunities...');
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
      setTimeout(() => toast.classList.remove('show'), 5000);
    }

    function escapeHtml(str) {
      if (!str) return '';
      return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }
    function escapeJs(str) {
      if (!str) return '';
      return String(str).replace(/'/g, "\\'").replace(/"/g, '\\"');
    }

    // Auto load on start
    window.addEventListener('DOMContentLoaded', () => {
      loadOpportunities();
    });
  </script>
</body>
</html>
"""

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
    print(f"⚡ Career-Ops 1-Click Auto-Apply Dashboard running at: {url}")
    print(f"📊 Serving 600+ opportunities from: {OPPORTUNITIES_CSV}")
    print("🚀 Opening dashboard in your default browser...")
    print("   Press Ctrl+C in this terminal to stop the server.")
    print("=" * 65)

    # Open browser automatically
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Career-Ops Dashboard server. Goodbye!")
        server.shutdown()

if __name__ == "__main__":
    main()
