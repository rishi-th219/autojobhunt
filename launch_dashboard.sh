#!/usr/bin/env bash
# launch_dashboard.sh — 1-Click Launcher for Career-Ops Browser Dashboard

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# Prioritize .venv python if available
if [ -f "$DIR/.venv/bin/python" ]; then
    PYTHON_EXEC="$DIR/.venv/bin/python"
else
    PYTHON_EXEC="python3"
fi

echo "=========================================================="
echo "⚡ Starting Career-Ops Auto-Apply Dashboard..."
echo "🌐 URL: http://localhost:5000"
echo "=========================================================="

"$PYTHON_EXEC" "$DIR/web_dashboard.py"
