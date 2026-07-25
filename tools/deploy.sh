#!/usr/bin/env bash
# Push the working tree to a self-hosted instance, restart it, and verify it came back.
#
#   ./tools/deploy.sh                    # uses $CARLINKO_HOST
#   ./tools/deploy.sh jay@192.168.1.7    # or pass the host
#   CARLINKO_REMOTE=~/carlinko CARLINKO_WEB=~/web ./tools/deploy.sh user@host
#
# Deployment here is plain scp, not a git checkout, so it is easy for the box to drift behind the
# repo. This script also runs a drift check afterwards and prints any file that still differs.
set -euo pipefail

HOST="${1:-${CARLINKO_HOST:-}}"
REMOTE="${CARLINKO_REMOTE:-~/carlinko}"
WEB="${CARLINKO_WEB:-~/web}"
SERVICES="${CARLINKO_SERVICES:-carlinko-web carlinko-logger}"

if [ -z "$HOST" ]; then
  echo "usage: $0 user@host   (or set CARLINKO_HOST)" >&2
  exit 2
fi

cd "$(dirname "$0")/.."
PY_FILES=(tools/server.py tools/logger.py tools/auth.py tools/setup.py tools/query_service.py
          tools/report.py tools/known_cars.py)
WEB_FILES=(web/index.html web/login.html web/slot-text.js web/manifest.webmanifest web/icon.svg
           web/car-front.png web/car-generic.svg web/leaflet.js web/leaflet.css)

echo "==> syntax check"
python -m py_compile "${PY_FILES[@]}"

echo "==> copying to $HOST"
scp -q "${PY_FILES[@]}" "$HOST:$REMOTE/"
scp -q "${WEB_FILES[@]}" "$HOST:$WEB/"

echo "==> restarting: $SERVICES"
# shellcheck disable=SC2029  # $SERVICES is meant to expand locally
ssh "$HOST" "sudo systemctl restart $SERVICES && sleep 3 && systemctl is-active $SERVICES"

echo "==> health"
ssh "$HOST" "curl -fsS -m 60 http://127.0.0.1:8088/api/status" && echo

echo "==> drift check"
drift=0
for f in "${PY_FILES[@]}" "${WEB_FILES[@]}"; do
  case "$f" in web/*) dir="$WEB" ;; *) dir="$REMOTE" ;; esac
  b="$(basename "$f")"
  # strip CR so a CRLF working tree on Windows doesn't look like drift
  l="$(tr -d '\r' < "$f" | sha256sum | cut -c1-16)"
  r="$(ssh "$HOST" "tr -d '\r' < $dir/$b 2>/dev/null | sha256sum | cut -c1-16" || true)"
  if [ "$l" != "$r" ]; then echo "   DRIFT: $f"; drift=1; fi
done
[ "$drift" -eq 0 ] && echo "   all files match" || { echo "!! some files differ" >&2; exit 1; }

echo "==> done"
