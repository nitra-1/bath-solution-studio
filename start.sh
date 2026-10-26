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
# Updated copies may need a package the old setup did not install (PDF export).
.venv/bin/python -c "import reportlab" 2>/dev/null || .venv/bin/pip install -r requirements.txt
PORT="${PORT:-8010}"
while .venv/bin/python -c "import socket,sys; s=socket.socket(); sys.exit(0 if s.connect_ex(('127.0.0.1', $PORT)) == 0 else 1)"; do
  echo "Port $PORT is already used by another program. Trying the next one…"
  PORT=$((PORT + 1))
done
IP=$( (ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}') || true )
echo ""
echo "Bath Solution Studio is starting."
echo "  On this computer:        http://localhost:$PORT"
[ -n "$IP" ] && echo "  For the sales team:      http://$IP:$PORT"
echo "Keep this window open. Press Ctrl+C to stop."
echo ""
exec .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
