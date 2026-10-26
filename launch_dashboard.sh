#!/usr/bin/env bash
# launch_dashboard.sh — 1-Click Launcher for AutoJobHunt Browser Dashboard (based on career-ops)

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# Prioritize .venv python if available
if [ -f "$DIR/.venv/bin/python" ]; then
    PYTHON_EXEC="$DIR/.venv/bin/python"
else
    PYTHON_EXEC="python3"
fi

echo "=========================================================="
echo "⚡ Starting AutoJobHunt Dashboard (based on career-ops)..."
echo "🌐 URL: http://localhost:5000"
echo "=========================================================="

"$PYTHON_EXEC" "$DIR/web_dashboard.py"
