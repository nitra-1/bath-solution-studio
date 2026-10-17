#!/usr/bin/env bash
# Start Bath Solution Studio without Docker (macOS / Linux). Needs Python 3.10 or newer.
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  echo "First run: setting up (takes a minute)…"
  python3 -m venv .venv
  .venv/bin/pip install --upgrade pip >/dev/null
  .venv/bin/pip install -r requirements.txt
fi
PORT="${PORT:-8000}"
IP=$( (ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}') )
echo ""
echo "Bath Solution Studio is running."
echo "  On this computer:        http://localhost:$PORT"
[ -n "$IP" ] && echo "  For the sales team:      http://$IP:$PORT"
echo "Keep this window open. Press Ctrl+C to stop."
echo ""
exec .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
