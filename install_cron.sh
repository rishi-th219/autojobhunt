#!/usr/bin/env bash
# install_cron.sh — Installs the daily job scanner into the user's crontab
# Runs automatically every day at 09:00 AM IST.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -x "${SCRIPT_DIR}/.venv/bin/python" ]; then
    PYTHON_BIN="${SCRIPT_DIR}/.venv/bin/python"
elif [ -n "${VIRTUAL_ENV:-}" ] && [ -x "${VIRTUAL_ENV}/bin/python" ]; then
    PYTHON_BIN="${VIRTUAL_ENV}/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
else
    PYTHON_BIN="$(command -v python)"
fi
SCANNER_SCRIPT="${SCRIPT_DIR}/run_autonomous_pipeline.py"
LOG_FILE="${SCRIPT_DIR}/data/autonomous_cron.log"

chmod +x "${SCANNER_SCRIPT}"
mkdir -p "${SCRIPT_DIR}/data"

CRON_CMD="0 9 * * * cd ${SCRIPT_DIR} && ${PYTHON_BIN} ${SCANNER_SCRIPT} >> ${LOG_FILE} 2>&1"

# Check if already installed
if crontab -l 2>/dev/null | grep -Fq "${SCANNER_SCRIPT}"; then
    echo "✓ Daily job scanner is already registered in crontab."
    echo "Current schedule:"
    crontab -l | grep -F "${SCANNER_SCRIPT}"
    exit 0
fi

# Append to existing crontab
(crontab -l 2>/dev/null || true; echo "# Career-Ops daily job scanner (09:00 AM IST)"; echo "${CRON_CMD}") | crontab -

echo "✓ Successfully installed daily job scanner to crontab!"
echo "Schedule: Every day at 09:00 AM IST"
echo "Command: ${CRON_CMD}"
echo "Log file: ${LOG_FILE}"
