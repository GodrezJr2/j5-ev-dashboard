#!/usr/bin/env bash
# One-command self-hosted install: venv + deps + login + systemd services (+ optional Tailscale).
#
#   git clone https://github.com/GodrezJr2/j5-ev-dashboard.git
#   cd j5-ev-dashboard && ./tools/install.sh
#
# Flags:
#   --tailscale     also install Tailscale, so you can reach the dashboard from your phone
#                   anywhere without exposing anything to the public internet
#   --port N        dashboard port (default 8088)
#   --no-service    set up the venv and log in, but don't install systemd units
#
# Everything is scoped to the current user and this checkout -- no paths are assumed.
set -euo pipefail

PORT=8088
WANT_TAILSCALE=0
WANT_SERVICE=1
for arg in "$@"; do
  case "$arg" in
    --tailscale)  WANT_TAILSCALE=1 ;;
    --no-service) WANT_SERVICE=0 ;;
    --port)       shift ;;
    --port=*)     PORT="${arg#*=}" ;;
    -h|--help)    sed -n '2,13p' "$0"; exit 0 ;;
    *) echo "unknown flag: $arg (try --help)" >&2; exit 2 ;;
  esac
done

REPO="$(cd "$(dirname "$0")/.." && pwd)"
TOOLS="$REPO/tools"
VENV="$REPO/venv"
USER_NAME="$(id -un)"

say() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
die() { printf '\033[31m!! %s\033[0m\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------- prerequisites
say "Checking prerequisites"
command -v python3 >/dev/null || die "python3 not found. Install Python 3.10+ and re-run."
PYV="$(python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])')"
python3 -c 'import sys;sys.exit(0 if sys.version_info>=(3,10) else 1)' \
  || die "Python $PYV is too old — this needs 3.10+."
echo "    python3 $PYV"

if ! python3 -c 'import venv' 2>/dev/null; then
  die "python3-venv is missing. On Debian/Ubuntu: sudo apt install python3-venv"
fi

# ---------------------------------------------------------------- venv + deps
say "Creating the virtualenv"
[ -d "$VENV" ] || python3 -m venv "$VENV"
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -r "$REPO/requirements.txt"
echo "    $VENV"

# ---------------------------------------------------------------- account setup
CREDS="$TOOLS/creds.json"
if [ -f "$CREDS" ]; then
  say "Found an existing creds.json — leaving it alone"
  echo "    re-run '$VENV/bin/python $TOOLS/setup.py' yourself to change anything"
else
  say "Logging in to CarLinko"
  echo "    Use a SECOND account linked to your car, not your daily one (see README)."
  ( cd "$TOOLS" && "$VENV/bin/python" setup.py )
fi
[ -f "$CREDS" ] || die "setup.py didn't produce creds.json — fix the login and re-run."

# ---------------------------------------------------------------- systemd
if [ "$WANT_SERVICE" = 1 ]; then
  if ! command -v systemctl >/dev/null; then
    echo "    no systemd here — skipping services."
    WANT_SERVICE=0
  else
    say "Installing systemd services (as $USER_NAME)"
    for svc in web logger; do
      case "$svc" in
        web)    desc="CarLinko dashboard"; cmd="$VENV/bin/python $TOOLS/server.py $PORT" ;;
        logger) desc="CarLinko telemetry logger"; cmd="$VENV/bin/python -u $TOOLS/logger.py --adaptive" ;;
      esac
      sudo tee "/etc/systemd/system/carlinko-$svc.service" >/dev/null <<UNIT
[Unit]
Description=$desc
After=network-online.target
Wants=network-online.target

[Service]
User=$USER_NAME
WorkingDirectory=$TOOLS
ExecStart=$cmd
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
UNIT
    done
    sudo systemctl daemon-reload
    sudo systemctl enable --now carlinko-web carlinko-logger
    sleep 3
    systemctl is-active carlinko-web carlinko-logger || die "a service failed — check: journalctl -u carlinko-web -n 50"
  fi
fi

# ---------------------------------------------------------------- tailscale
if [ "$WANT_TAILSCALE" = 1 ]; then
  say "Setting up Tailscale"
  if ! command -v tailscale >/dev/null; then
    curl -fsSL https://tailscale.com/install.sh | sh
  fi
  sudo tailscale up
  TSIP="$(tailscale ip -4 2>/dev/null | head -1 || true)"
  [ -n "$TSIP" ] && echo "    reachable at http://$TSIP:$PORT from any device on your tailnet"
fi

# ---------------------------------------------------------------- verify
say "Checking it's up"
if [ "$WANT_SERVICE" = 1 ]; then
  for _ in $(seq 1 10); do
    if curl -fsS -m 5 "http://127.0.0.1:$PORT/api/status" >/dev/null 2>&1; then break; fi
    sleep 1
  done
  curl -fsS -m 10 "http://127.0.0.1:$PORT/api/status" && echo
else
  echo "    services skipped — start it yourself with:"
  echo "      $VENV/bin/python $TOOLS/server.py $PORT"
fi

LANIP="$(hostname -I 2>/dev/null | awk '{print $1}')"
say "Done"
echo "  Dashboard:  http://${LANIP:-localhost}:$PORT"
[ "$WANT_TAILSCALE" = 1 ] && echo "  Tailnet:    http://$(tailscale ip -4 2>/dev/null | head -1):$PORT"
cat <<NEXT

  The logger polls your car continuously to build trends, charge history and
  cost, so leave this machine on. It backs off while the car is parked.

  Useful:
    systemctl status carlinko-web carlinko-logger
    journalctl -u carlinko-logger -f
    $VENV/bin/python $TOOLS/setup.py      # change account, currency, units

  Not in Indonesia, or not driving a Jaecoo? setup.py already asked for your
  currency and tyre unit, and reads your car's tyre scale and photo from the
  API. See the creds.json reference in the README for the rest.
NEXT
