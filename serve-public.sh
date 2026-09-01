#!/usr/bin/env bash
# Share Carriage from this Mac. Run in Terminal.app and leave the window open.
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -x .venv/bin/python ]]; then
  echo "Missing .venv. From this folder run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared is not installed. Run: brew install cloudflared"
  exit 1
fi

echo "Keeping this Mac awake. Plug it in. Do not close the lid."
echo "Copy the trycloudflare.com URL when it appears. Leave this window open."
echo

keep_awake=(caffeinate -is)
if ! command -v caffeinate >/dev/null 2>&1; then
  keep_awake=()
fi

cleanup() {
  if [[ -n "${FLASK_PID:-}" ]]; then
    kill "${FLASK_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT

if curl -sf --max-time 2 "http://127.0.0.1:5001/health" >/dev/null 2>&1; then
  echo "Carriage is already running on port 5001."
else
  .venv/bin/python app.py &
  FLASK_PID=$!
  for _ in {1..20}; do
    if curl -sf --max-time 1 "http://127.0.0.1:5001/health" >/dev/null 2>&1; then
      break
    fi
    sleep 0.25
  done
fi

exec "${keep_awake[@]}" cloudflared tunnel --url "http://127.0.0.1:5001"
