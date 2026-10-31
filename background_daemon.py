#!/usr/bin/env python3
"""
background_daemon.py — Continuous Job Discovery & Email Alert Daemon
Runs 24/7 in the background, periodically executing job discovery scans,
deduplicating new opportunities, and dispatching instant email alerts.

Usage:
  python background_daemon.py             # Runs daemon in current terminal (interactive)
  python background_daemon.py --start     # Launches daemon in background (detached process)
  python background_daemon.py --stop      # Cleanly terminates running background daemon
  python background_daemon.py --status    # Checks daemon health, PID, and last scan time
  python background_daemon.py --run-once  # Executes a single scan + alert cycle and exits
  python background_daemon.py --interval 30 # Run every 30 minutes (default: 60)
"""

import os
import sys
import time
import json
import signal
import subprocess
import argparse
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
PID_FILE = os.path.join(DATA_DIR, "daemon.pid")
STATUS_FILE = os.path.join(DATA_DIR, "daemon_status.json")
LOG_FILE = os.path.join(DATA_DIR, "daemon.log")

PYTHON_BIN = sys.executable

# Graceful shutdown flag
RUNNING = True


def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] [Daemon] {msg}"
    try:
        if sys.stdout is not None:
            print(formatted, flush=True)
    except Exception:
        pass
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except Exception:
        pass


def signal_handler(signum, frame):
    global RUNNING
    log("Received shutdown signal. Stopping daemon cleanly...")
    RUNNING = False


def update_status(is_running, last_scan=None, next_scan=None, stats=None, error=None):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        data = {
            "is_running": is_running,
            "pid": os.getpid() if is_running else None,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_scan": last_scan,
            "next_scan": next_scan,
            "stats": stats or {},
            "last_error": error
        }
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def is_pid_running(pid):
    """Check if process with given PID is still running on Windows/Linux."""
    if not pid or pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes
            kernel32 = ctypes.windll.kernel32
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not handle:
                return False
            exit_code = wintypes.DWORD()
            success = kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            kernel32.CloseHandle(handle)
            # STILL_ACTIVE is 259 (0x103)
            return bool(success and exit_code.value == 259)
        except Exception:
            try:
                cmd = f'tasklist /FI "PID eq {pid}" /NH'
                out = subprocess.check_output(cmd, shell=True).decode(errors="ignore")
                return str(pid) in out and "No tasks" not in out
            except Exception:
                return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def get_active_daemon_pid():
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                pid = int(f.read().strip())
                if is_pid_running(pid):
                    return pid
        except Exception:
            pass
    return None


def run_cycle():
    """Executes a full discovery and clean cycle."""
    log("▶ Starting scheduled job scan cycle...")
    cycle_start = datetime.now()

    # 1. Run direct ATS and remote job discovery (triggers email alerts automatically)
    try:
        res = subprocess.run(
            [PYTHON_BIN, "daily_job_scanner.py", "--no-jobspy"],
            cwd=PROJECT_ROOT,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        if res.returncode == 0:
            log("✓ Direct ATS scan finished successfully.")
        else:
            log(f"⚠️ ATS scanner returned non-zero ({res.returncode}): {res.stderr[:200]}")
    except Exception as e:
        log(f"❌ Error running daily_job_scanner: {e}")

    # 2. Run Startup & VC network scanner
    try:
        res_vc = subprocess.run(
            [PYTHON_BIN, "startup_vc_scanner.py"],
            cwd=PROJECT_ROOT,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        if res_vc.returncode == 0:
            log("✓ Startup/VC scan finished successfully.")
    except Exception as e:
        log(f"❌ Error running startup_vc_scanner: {e}")

    duration = (datetime.now() - cycle_start).total_seconds()
    log(f"🏁 Scan cycle completed in {duration:.1f}s.")
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def daemon_loop(interval_minutes=60):
    global RUNNING
    pid = os.getpid()
    log(f"🚀 AutoJobHunt Daemon started (PID: {pid}). Polling every {interval_minutes} minutes.")

    # Write PID file
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(PID_FILE, "w") as f:
        f.write(str(pid))

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        while RUNNING:
            try:
                last_scan = run_cycle()
                next_scan_dt = datetime.fromtimestamp(time.time() + (interval_minutes * 60))
                next_scan = next_scan_dt.strftime("%Y-%m-%d %H:%M:%S")
                log(f"💤 Sleeping until next scan at: {next_scan}")

                update_status(
                    is_running=True,
                    last_scan=last_scan,
                    next_scan=next_scan,
                    stats={"interval_minutes": interval_minutes}
                )
            except Exception as loop_err:
                import traceback
                log(f"⚠️ Error during scan cycle: {loop_err}\n{traceback.format_exc()}")
                update_status(is_running=True, error=str(loop_err))

            # Sleep in 1-second chunks to respond quickly to shutdown signals
            sleep_seconds = interval_minutes * 60
            elapsed = 0
            while RUNNING and elapsed < sleep_seconds:
                time.sleep(1)
                elapsed += 1

    finally:
        log("AutoJobHunt Daemon stopped.")
        update_status(is_running=False)
        if os.path.exists(PID_FILE):
            try:
                os.remove(PID_FILE)
            except Exception:
                pass


def start_detached(interval_minutes=60):
    """Starts the daemon process in the background detached from the current shell."""
    existing_pid = get_active_daemon_pid()
    if existing_pid:
        print(f"⚠️ AutoJobHunt Daemon is ALREADY running (PID: {existing_pid}).")
        return

    log_path = os.path.join(DATA_DIR, "daemon_stdout.log")
    os.makedirs(DATA_DIR, exist_ok=True)
    script_path = os.path.abspath(__file__)

    if os.name == "nt":
        # Launch fully detached background process via PowerShell Start-Process
        ps_cmd = (
            f"Start-Process -FilePath '{PYTHON_BIN}' "
            f"-ArgumentList @('{script_path}', '--interval', '{interval_minutes}') "
            f"-WorkingDirectory '{PROJECT_ROOT}' "
            f"-RedirectStandardOutput '{log_path}' "
            f"-RedirectStandardError '{log_path}' "
            f"-WindowStyle Hidden -PassThru"
        )
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                capture_output=True,
                check=True
            )
        except Exception:
            # Fallback to direct subprocess.Popen
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
            out_file = open(log_path, "a", encoding="utf-8")
            subprocess.Popen(
                [PYTHON_BIN, script_path, "--interval", str(interval_minutes)],
                cwd=PROJECT_ROOT,
                stdout=out_file,
                stderr=out_file,
                creationflags=creationflags,
                close_fds=False
            )
    else:
        out_file = open(log_path, "a", encoding="utf-8")
        subprocess.Popen(
            [PYTHON_BIN, script_path, "--interval", str(interval_minutes)],
            cwd=PROJECT_ROOT,
            stdout=out_file,
            stderr=out_file,
            close_fds=True
        )

    # Wait for process to write PID
    pid = None
    for _ in range(8):
        time.sleep(0.5)
        pid = get_active_daemon_pid()
        if pid:
            break

    pid_str = str(pid) if pid else "Active"
    print(f"🚀 AutoJobHunt Daemon launched in the background (PID: {pid_str}).")
    print(f"   • Polling Interval: Every {interval_minutes} minutes")
    print(f"   • Daemon Log:       {LOG_FILE}")
    print(f"   • Process Log:      {log_path}")
    print(f"   • Stop command:     python background_daemon.py --stop")


def stop_daemon():
    pid = get_active_daemon_pid()
    if not pid:
        print("No active AutoJobHunt Daemon found running.")
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
        return

    print(f"Stopping AutoJobHunt Daemon (PID: {pid})...")
    try:
        if os.name == "nt":
            subprocess.run(f"taskkill /F /PID {pid}", shell=True, check=False)
        else:
            os.kill(pid, signal.SIGTERM)
        time.sleep(1)
        print("✓ Daemon stopped successfully.")
    except Exception as e:
        print(f"Error stopping daemon: {e}")
    finally:
        if os.path.exists(PID_FILE):
            try:
                os.remove(PID_FILE)
            except Exception:
                pass
        update_status(is_running=False)


def print_status():
    pid = get_active_daemon_pid()
    status_data = {}
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                status_data = json.load(f)
        except Exception:
            pass

    print("=" * 60)
    print("           AUTOJOBHUNT BACKGROUND DAEMON STATUS")
    print("=" * 60)
    if pid:
        print(f"🟢 State:            ACTIVE / RUNNING (PID: {pid})")
        print(f"⏱️  Last Scan:        {status_data.get('last_scan', 'Running first cycle...')}")
        print(f"⏰ Next Scan:        {status_data.get('next_scan', 'Calculating...')}")
        interval = status_data.get('stats', {}).get('interval_minutes', 60)
        print(f"🔄 Check Frequency:  Every {interval} minutes")
    else:
        print("🔴 State:            STOPPED / INACTIVE")
        if status_data.get("last_scan"):
            print(f"⏱️  Previous Scan:   {status_data.get('last_scan')}")
        print("💡 Start with:       python background_daemon.py --start")
    print(f"📄 Log File:         {LOG_FILE}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="AutoJobHunt Continuous Background Daemon")
    parser.add_argument("--start", action="store_true", help="Launch daemon in background")
    parser.add_argument("--stop", action="store_true", help="Stop running daemon")
    parser.add_argument("--status", action="store_true", help="Show daemon status")
    parser.add_argument("--run-once", action="store_true", help="Execute single scan cycle and exit")
    parser.add_argument("--interval", type=int, default=60, help="Interval between scans in minutes (default: 60)")
    args = parser.parse_args()

    if args.start:
        start_detached(args.interval)
    elif args.stop:
        stop_daemon()
    elif args.status:
        print_status()
    elif args.run_once:
        print("Running single discovery and alert cycle...")
        run_cycle()
    else:
        daemon_loop(args.interval)


if __name__ == "__main__":
    main()
