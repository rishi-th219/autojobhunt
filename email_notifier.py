#!/usr/bin/env python3
"""
email_notifier.py — Automated Email Alert Engine for New Job Opportunities
Sends formatted HTML & plain-text email alerts when new tech opportunities are discovered.

Configuration via .env or environment variables:
  ALERT_RECIPIENT_EMAIL=rishi_th219@proton.me
  SMTP_HOST=smtp.gmail.com
  SMTP_PORT=587
  SMTP_USER=your_email@gmail.com
  SMTP_PASSWORD=your_app_password
  SMTP_USE_TLS=true
  EMAIL_ALERTS_ENABLED=true

Usage:
  python email_notifier.py --test            # Sends a test email alert
  python email_notifier.py --preview         # Generates and prints preview HTML
"""

import os
import sys
import re
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(PROJECT_ROOT, ".env")
ALERTS_DIR = os.path.join(PROJECT_ROOT, "data", "email_alerts")
os.makedirs(ALERTS_DIR, exist_ok=True)


def load_env_vars():
    """Lightweight .env loader without requiring external packages."""
    env = dict(os.environ)
    if os.path.exists(ENV_FILE):
        try:
            with open(ENV_FILE, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k and k not in env:
                            env[k] = v
        except Exception:
            pass
    return env


def get_email_config():
    """Retrieves SMTP and alert configuration with sensible defaults."""
    env = load_env_vars()
    
    # Candidate profile fallback
    default_recipient = "rishi_th219@proton.me"
    candidate_name = "Rishi Thakur"
    try:
        import config_loader
        cand = config_loader.get_candidate_profile()
        default_recipient = cand.get("email") or default_recipient
        candidate_name = cand.get("full_name") or candidate_name
    except Exception:
        pass

    recipient = env.get("ALERT_RECIPIENT_EMAIL") or env.get("ALERT_EMAIL") or default_recipient
    smtp_host = env.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(env.get("SMTP_PORT", 587))
    smtp_user = env.get("SMTP_USER", "")
    smtp_pass = env.get("SMTP_PASSWORD") or env.get("SMTP_PASS", "")
    smtp_tls = env.get("SMTP_USE_TLS", "true").lower() in ["1", "true", "yes"]
    smtp_ssl = env.get("SMTP_USE_SSL", "false").lower() in ["1", "true", "yes"] or smtp_port == 465
    alerts_enabled = env.get("EMAIL_ALERTS_ENABLED", "true").lower() in ["1", "true", "yes"]
    sender = env.get("SMTP_FROM") or smtp_user or "AutoJobHunt Alerts <bot@autojobhunt.local>"

    return {
        "enabled": alerts_enabled,
        "recipient": recipient,
        "sender": sender,
        "smtp_host": smtp_host,
        "smtp_port": smtp_port,
        "smtp_user": smtp_user,
        "smtp_pass": smtp_pass,
        "smtp_tls": smtp_tls,
        "smtp_ssl": smtp_ssl,
        "candidate_name": candidate_name
    }


def format_jobs_html(jobs, candidate_name="Rishi"):
    """Creates a modern, responsive HTML email template for new opportunities."""
    job_cards = []
    for i, j in enumerate(jobs, 1):
        title = j.get("title", "Opportunity")
        company = j.get("company", "Company")
        location = j.get("location", "Bengaluru / Remote")
        portal = j.get("portal", "direct-ats").upper()
        date_str = j.get("date", datetime.now().strftime("%Y-%m-%d"))
        url = j.get("url", "#")
        pay = j.get("pay", "Competitive / Open")

        # Color-coded badge for portal
        badge_color = "#3b82f6"
        if "greenhouse" in portal.lower():
            badge_color = "#10b981"
        elif "lever" in portal.lower():
            badge_color = "#8b5cf6"
        elif "smartrecruiters" in portal.lower():
            badge_color = "#f59e0b"
        elif "ashby" in portal.lower():
            badge_color = "#06b6d4"
        elif "hacker" in portal.lower() or "yc" in portal.lower():
            badge_color = "#ec4899"

        card = f"""
        <tr style="border-bottom: 1px solid #e2e8f0;">
          <td style="padding: 16px 20px;">
            <div style="display: flex; align-items: baseline; margin-bottom: 6px;">
              <span style="background-color: {badge_color}; color: #ffffff; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 9999px; text-transform: uppercase; margin-right: 8px;">{portal}</span>
              <span style="color: #64748b; font-size: 12px;">Found {date_str}</span>
            </div>
            <h3 style="margin: 0 0 4px 0; color: #0f172a; font-size: 16px; font-weight: 700; line-height: 1.3;">
              {title}
            </h3>
            <p style="margin: 0 0 10px 0; color: #334155; font-size: 14px;">
              <strong style="color: #0284c7;">{company}</strong> &bull; {location}
            </p>
            <div style="margin-top: 8px;">
              <a href="{url}" style="display: inline-block; background-color: #0284c7; color: #ffffff; text-decoration: none; font-size: 13px; font-weight: 600; padding: 6px 14px; border-radius: 6px;" target="_blank">
                View &amp; Apply &rarr;
              </a>
            </div>
          </td>
        </tr>
        """
        job_cards.append(card)

    cards_html = "\n".join(job_cards)
    count = len(jobs)
    word = "Opportunity" if count == 1 else "Opportunities"

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AutoJobHunt Alert</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 24px; color: #1e293b;">
  <table width="100%" border="0" cellspacing="0" cellpadding="0" style="max-width: 640px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1); border: 1px solid #e2e8f0;">
    <!-- Header -->
    <tr>
      <td style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); padding: 28px 24px; text-align: left; color: #ffffff;">
        <div style="font-size: 12px; font-weight: 700; letter-spacing: 0.1em; color: #38bdf8; text-transform: uppercase; margin-bottom: 6px;">
          AutoJobHunt &bull; Autonomous Radar
        </div>
        <h1 style="margin: 0; font-size: 22px; font-weight: 800; color: #ffffff; line-height: 1.25;">
          🚀 {count} New Qualified Tech {word} Detected!
        </h1>
        <p style="margin: 8px 0 0 0; color: #94a3b8; font-size: 14px;">
          Fresh roles matching your career tracks in Bengaluru &amp; Remote.
        </p>
      </td>
    </tr>

    <!-- Summary Box -->
    <tr>
      <td style="background-color: #f0f9ff; padding: 12px 24px; border-bottom: 1px solid #bae6fd;">
        <p style="margin: 0; font-size: 13px; color: #0369a1;">
          <strong>Target Profile:</strong> {candidate_name} &bull; Synced automatically to <code style="background-color: #e0f2fe; padding: 2px 5px; border-radius: 4px;">opportunities.xlsx</code>
        </p>
      </td>
    </tr>

    <!-- Jobs List -->
    <tr>
      <td style="padding: 0;">
        <table width="100%" border="0" cellspacing="0" cellpadding="0">
          {cards_html}
        </table>
      </td>
    </tr>

    <!-- Footer -->
    <tr>
      <td style="padding: 24px; background-color: #f8fafc; border-top: 1px solid #e2e8f0; text-align: center; color: #64748b; font-size: 12px; line-height: 1.5;">
        <p style="margin: 0 0 8px 0;">
          💡 <em>Tip: You can 1-click apply or autofill these roles via the local Web Dashboard: <a href="http://localhost:5000" style="color: #0284c7; text-decoration: none;">http://localhost:5000</a></em>
        </p>
        <p style="margin: 0;">
          AutoJobHunt Autonomous Daemon &bull; 100% Local-First &bull; Zero Cloud Leakage
        </p>
      </td>
    </tr>
  </table>
</body>
</html>
"""
    return html


def format_jobs_text(jobs, candidate_name="Rishi"):
    """Plain-text fallback email format."""
    count = len(jobs)
    lines = [
        f"AutoJobHunt: {count} New Tech Opportunities Detected",
        "=" * 60,
        f"Target Profile: {candidate_name}",
        f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 60,
        ""
    ]
    for i, j in enumerate(jobs, 1):
        lines.append(f"{i}. {j.get('title')} at {j.get('company')}")
        lines.append(f"   Location: {j.get('location')}")
        lines.append(f"   Portal:   {j.get('portal', 'Direct ATS')}")
        lines.append(f"   Apply:    {j.get('url')}")
        lines.append("-" * 40)
    lines.append("")
    lines.append("Open your local command center to review & autofill: http://localhost:5000")
    return "\n".join(lines)


def send_job_alert(jobs, recipient=None, subject=None):
    """
    Main entrypoint: sends an email alert containing the provided job opportunities.
    Returns (success: bool, message: str).
    """
    if not jobs:
        return False, "No jobs provided."

    cfg = get_email_config()
    if not cfg["enabled"]:
        return False, "Email alerts are disabled in configuration."

    recip = recipient or cfg["recipient"]
    count = len(jobs)
    plural = "s" if count != 1 else ""
    subj = subject or f"🚀 AutoJobHunt: {count} New Tech Role{plural} Found ({datetime.now().strftime('%d %b')})"

    html_content = format_jobs_html(jobs, cfg["candidate_name"])
    text_content = format_jobs_text(jobs, cfg["candidate_name"])

    # Always persist the latest alert HTML locally for audit and web preview
    latest_html_path = os.path.join(ALERTS_DIR, "latest_alert.html")
    latest_txt_path = os.path.join(ALERTS_DIR, "latest_alert.txt")
    try:
        with open(latest_html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        with open(latest_txt_path, "w", encoding="utf-8") as f:
            f.write(text_content)
    except Exception as e:
        print(f"Warning: Could not save local alert preview: {e}", file=sys.stderr)

    # Check if SMTP credentials are provided
    if not cfg["smtp_user"] or not cfg["smtp_pass"]:
        msg = (
            f"📧 Alert generated with {count} new role{plural}. "
            f"SMTP credentials not configured in .env; saved preview to {latest_html_path}."
        )
        print(f"[Email Alert] {msg}")
        return False, msg

    # Build MIME message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subj
    msg["From"] = cfg["sender"]
    msg["To"] = recip
    msg["Date"] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0530")

    part1 = MIMEText(text_content, "plain", "utf-8")
    part2 = MIMEText(html_content, "html", "utf-8")
    msg.attach(part1)
    msg.attach(part2)

    try:
        if cfg["smtp_ssl"]:
            server = smtplib.SMTP_SSL(cfg["smtp_host"], cfg["smtp_port"], timeout=15)
        else:
            server = smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"], timeout=15)
            if cfg["smtp_tls"]:
                server.starttls()

        server.login(cfg["smtp_user"], cfg["smtp_pass"])
        server.sendmail(cfg["smtp_user"], [recip], msg.as_string())
        server.quit()
        success_msg = f"✓ Successfully sent job alert with {count} roles to {recip} via {cfg['smtp_host']}."
        print(f"[Email Alert] {success_msg}")
        return True, success_msg
    except Exception as e:
        err_msg = f"Failed to send email alert to {recip}: {e}"
        print(f"[Email Alert] ❌ {err_msg}", file=sys.stderr)
        return False, err_msg


def send_test_email():
    """Sends a sample test email alert verifying SMTP configuration."""
    test_jobs = [
        {
            "title": "Machine Learning Engineer (NLP & Generative AI)",
            "company": "Level AI",
            "location": "Bengaluru, India (Hybrid)",
            "portal": "ashby-api",
            "url": "https://jobs.ashbyhq.com/level-ai",
            "date": datetime.now().strftime("%Y-%m-%d")
        },
        {
            "title": "Data Analyst (Supply Chain & Logistics Analytics)",
            "company": "Portcast",
            "location": "Bengaluru, India",
            "portal": "lever-api",
            "url": "https://jobs.lever.co/portcast",
            "date": datetime.now().strftime("%Y-%m-%d")
        },
        {
            "title": "Business Intelligence & Systems Analyst",
            "company": "Eurofins",
            "location": "Bengaluru, India",
            "portal": "smartrecruiters-api",
            "url": "https://jobs.smartrecruiters.com/Eurofins",
            "date": datetime.now().strftime("%Y-%m-%d")
        }
    ]
    print("Testing AutoJobHunt email notification system...")
    cfg = get_email_config()
    print(f"  • Recipient: {cfg['recipient']}")
    print(f"  • SMTP Host: {cfg['smtp_host']}:{cfg['smtp_port']}")
    print(f"  • SMTP User: {cfg['smtp_user'] or '(not configured)'}")
    print(f"  • SMTP TLS:  {cfg['smtp_tls']}")

    success, msg = send_job_alert(test_jobs, subject="[TEST] AutoJobHunt Email Notification Setup")
    return success, msg


if __name__ == "__main__":
    if "--test" in sys.argv:
        send_test_email()
    elif "--preview" in sys.argv:
        html = format_jobs_html([{"title": "Sample Role", "company": "Test Co", "location": "Bengaluru", "url": "https://example.com"}])
        print(html)
    else:
        print("Usage:")
        print("  python email_notifier.py --test      # Send a test alert email")
        print("  python email_notifier.py --preview   # Print HTML preview")
