#!/usr/bin/env bash
# Optional entrypoint for single-service hosts: one service runs both the dashboard
# and the logger, sharing the /data volume (Railway volumes attach to a single
# service only). It is NOT the image's default command -- point the host's start
# command at it (Railway: Settings -> Deploy -> Custom Start Command,
# `bash railway_start.sh`), so that a plain `docker run` still starts the dashboard
# alone and never opens a second CarLinko session behind the owner's back.
#
# creds.json never ships in the image (.dockerignore excludes it). Instead the
# CREDS_JSON service variable is written into the volume on every boot, so
# updating the variable + redeploying is how you rotate credentials.
set -e

DATA="${CARLINKO_DATA:-/data}"
mkdir -p "$DATA"

if [ -n "$CREDS_JSON" ]; then
  printf '%s' "$CREDS_JSON" > "$DATA/creds.json"
  chmod 600 "$DATA/creds.json"          # same mode server.py gives it when it writes
  echo "railway_start: wrote $DATA/creds.json from CREDS_JSON"
elif [ ! -f "$DATA/creds.json" ]; then
  echo "railway_start: WARNING — no CREDS_JSON variable and no $DATA/creds.json in the volume" >&2
fi

python logger.py --adaptive &
exec python server.py "${PORT:-8088}"
