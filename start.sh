#!/usr/bin/env bash
# J5 EV Dashboard - start it locally on macOS or Linux (the counterpart of start.bat).
#
#   ./start.sh                 dashboard + telemetry logger on http://localhost:8088
#   ./start.sh --demo          fake data: no account, no car, no logger
#   ./start.sh --no-logger     dashboard only, serving whatever carlinko.db already holds
#   ./start.sh --port 9000     a different port
#   ./start.sh --open          also open the dashboard in the browser
#
# First run creates ./venv and installs the two libraries it needs. Ctrl+C stops everything.
#
# Real mode reads tools/creds.json (or $CARLINKO_DATA/creds.json). With none yet, the dashboard
# shows its login page and the logger starts as soon as that login has found the car.
# CarLinko keeps one session per account: if another instance (Railway, a home server) uses the
# same account, the two keep signing each other out. Use --demo, or give this one its own account.
set -euo pipefail
cd "$(dirname "$0")"

PORT=8088
DEMO=0
LOGGER=1
OPEN=0
while [ $# -gt 0 ]; do
  case "$1" in
    --demo) DEMO=1 ;;
    --no-logger) LOGGER=0 ;;
    --open) OPEN=1 ;;
    --port) shift; PORT="${1:-}" ;;
    --port=*) PORT="${1#--port=}" ;;
    [0-9]*) PORT="$1" ;;
    -h|--help) sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $1 (try --help)" >&2; exit 2 ;;
  esac
  shift
done
case "$PORT" in
  '' | *[!0-9]*) echo "--port needs a number" >&2; exit 2 ;;
esac

PY="$PWD/venv/bin/python"
if [ ! -x "$PY" ]; then
  if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3.10+ is required (macOS: brew install python)." >&2
    exit 1
  fi
  if ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))'; then
    echo "Python 3.10+ is required; found $(python3 --version)." >&2
    exit 1
  fi
  echo "First run: creating ./venv ..."
  python3 -m venv venv
fi
if ! "$PY" -c 'import requests, websocket' 2>/dev/null; then
  echo "Installing requests + websocket-client ..."
  "$PY" -m pip install --quiet requests websocket-client
fi

if command -v lsof >/dev/null 2>&1 && lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port $PORT is already in use:" >&2
  lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >&2
  echo "Stop that process or pass --port <n>." >&2
  exit 1
fi

cd tools
CREDS="${CARLINKO_DATA:-.}/creds.json"

has_car() {
  "$PY" -c 'import json, sys
c = json.load(open(sys.argv[1]))
sys.exit(not (c.get("vehicle_id") and c.get("device_sn")))' "$CREDS" 2>/dev/null
}

# Background jobs ignore Ctrl+C in a script, so the loop forwards the TERM that cleanup sends.
logger_loop() {
  local child=
  trap '[ -n "$child" ] && kill "$child" 2>/dev/null; exit 0' TERM
  if ! has_car; then
    echo "[start] no car in $CREDS yet - log in on the dashboard and the logger starts by itself"
    until has_car; do sleep 3 & wait $!; done
  fi
  while :; do
    echo "[start] starting logger"
    "$PY" -u logger.py --adaptive & child=$!
    wait "$child" || true
    child=
    echo "[start] logger exited, restarting in 15 s"
    sleep 15 & wait $!
  done
}

lan_ip() {
  local ip i
  if command -v ipconfig >/dev/null 2>&1; then
    for i in en0 en1; do
      ip=$(ipconfig getifaddr "$i" 2>/dev/null) && [ -n "$ip" ] && { echo "$ip"; return; }
    done
  fi
  hostname -I 2>/dev/null | awk '{print $1}'
}

LOGGER_PID=
cleanup() {
  if [ -n "$LOGGER_PID" ]; then
    kill "$LOGGER_PID" 2>/dev/null || true
  fi
  wait 2>/dev/null || true
}
trap cleanup EXIT

ARGS=("$PORT")
if [ "$DEMO" = 1 ]; then
  ARGS+=(--demo)
  LOGGER=0
fi
if [ "$LOGGER" = 1 ]; then
  logger_loop & LOGGER_PID=$!
fi

IP=$(lan_ip)
echo
if [ "$DEMO" = 1 ]; then echo "  J5 EV Dashboard - demo data"; else echo "  J5 EV Dashboard"; fi
echo "  In Voltmoss, type the address with http:// (the app assumes https otherwise):"
echo "    This Mac / iOS Simulator   http://localhost:$PORT"
echo "    Android emulator           http://10.0.2.2:$PORT"
if [ -n "$IP" ]; then
  echo "    Phone on the same Wi-Fi    http://$IP:$PORT"
fi
echo "  Ctrl+C stops it."
echo

if [ "$OPEN" = 1 ]; then
  opener=$(command -v open || command -v xdg-open || true)
  if [ -n "$opener" ]; then
    (sleep 2; "$opener" "http://localhost:$PORT" >/dev/null 2>&1) &
  fi
fi

"$PY" -u server.py "${ARGS[@]}"
