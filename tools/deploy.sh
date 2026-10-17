#!/usr/bin/env bash
# Update a systemd self-hosted box (the layout tools/install.sh creates: a git checkout the units
# run out of). It deploys what is on GitHub, so the repo and the box cannot drift apart:
#
#   1. refuses if your commits are not pushed yet (nothing to pull) or tracked files are dirty
#   2. on the box: git fetch + fast-forward to origin/<branch>
#   3. restarts only the units whose code changed (web-only edits need no restart)
#   4. checks /api/status, then fetches the changed pages back from the running server and
#      compares them with the repo, so "deployed" means "being served", not "a file landed"
#
#   ./tools/deploy.sh user@host                     # or set CARLINKO_HOST (an ssh alias works too)
#   CARLINKO_DIR=~/j5-ev-dashboard ./tools/deploy.sh host   # checkout path on the box (default)
#   CARLINKO_PORT=8088  CARLINKO_BRANCH=main  CARLINKO_SERVICES="carlinko-web carlinko-logger"
#
# Set CARLINKO_SERVICES to force-restart exactly those units instead of the automatic choice.
set -euo pipefail

HOST="${1:-${CARLINKO_HOST:-}}"
DIR="${CARLINKO_DIR:-~/j5-ev-dashboard}"
PORT="${CARLINKO_PORT:-8088}"
BRANCH="${CARLINKO_BRANCH:-main}"
FORCE_SERVICES="${CARLINKO_SERVICES:-}"

if [ -z "$HOST" ]; then
  echo "usage: $0 user@host   (or set CARLINKO_HOST)" >&2
  exit 2
fi

cd "$(dirname "$0")/.."

echo "==> local checks"
python -m py_compile tools/*.py
if ! git diff --quiet HEAD -- . ; then
  echo "!! tracked files have uncommitted changes; commit them first (the box deploys commits)" >&2
  exit 1
fi
git fetch -q origin "$BRANCH"
HEAD_SHA="$(git rev-parse HEAD)"
if ! git merge-base --is-ancestor "$HEAD_SHA" "origin/$BRANCH"; then
  echo "!! HEAD is not on origin/$BRANCH; run: git push origin $BRANCH" >&2
  exit 1
fi
echo "   deploying origin/$BRANCH ($(git rev-parse --short origin/$BRANCH))"

echo "==> updating $HOST:$DIR"
# the remote script prints OLD..NEW and the changed files; $DIR and $BRANCH expand locally
out="$(ssh "$HOST" "cd $DIR && \
  if [ -n \"\$(git status --porcelain --untracked-files=no)\" ]; then \
    echo 'REMOTE_DIRTY'; git status --short --untracked-files=no; exit 3; fi && \
  old=\$(git rev-parse HEAD) && git fetch -q origin $BRANCH && git merge --ff-only -q origin/$BRANCH && \
  new=\$(git rev-parse HEAD) && echo \"RANGE \$old \$new\" && \
  if [ \"\$old\" != \"\$new\" ]; then git diff --name-only \$old \$new; fi")" || {
  echo "$out" >&2
  echo "!! the box could not fast-forward (local edits or diverged history there)" >&2
  exit 1
}
range="$(printf '%s\n' "$out" | sed -n 's/^RANGE //p')"
changed="$(printf '%s\n' "$out" | grep -v '^RANGE ' || true)"
echo "   ${range:-unknown}"
if [ -z "$changed" ]; then echo "   already up to date"; else printf '%s\n' "$changed" | sed 's/^/   changed: /'; fi

# which units to restart. server.py imports auth + known_cars; logger.py imports auth. A logger
# restart drops its single CarLinko WebSocket session, so it is left alone unless it must change.
if [ -n "$FORCE_SERVICES" ]; then
  SERVICES="$FORCE_SERVICES"
else
  SERVICES=""
  grep -Eq '^tools/(server|auth|known_cars)\.py$' <<<"$changed" && SERVICES="carlinko-web"
  grep -Eq '^tools/(logger|auth)\.py$' <<<"$changed" && SERVICES="$SERVICES carlinko-logger"
  SERVICES="${SERVICES# }"
fi
if [ -n "$SERVICES" ]; then
  echo "==> restarting: $SERVICES"
  # shellcheck disable=SC2029  # $SERVICES is meant to expand locally
  ssh "$HOST" "sudo -n systemctl restart $SERVICES && sleep 3 && systemctl is-active $SERVICES"
else
  echo "==> no restart needed (no server/logger code changed)"
fi

echo "==> health"
status="$(ssh "$HOST" "curl -fsS -m 60 http://127.0.0.1:$PORT/api/status")"
echo "   $status"

echo "==> served pages"
rhead="$(ssh "$HOST" "cd $DIR && git rev-parse HEAD")"
[ "$rhead" = "$HEAD_SHA" ] || { echo "!! box is at ${rhead:0:7}, expected ${HEAD_SHA:0:7}" >&2; exit 1; }
if printf '%s' "$status" | grep -q '"gated": *true'; then
  # a dashboard password makes the box answer unauthenticated fetches with the login page
  echo "   dashboard is password-gated; skipped the served-page comparison (box is at ${rhead:0:7})"
  echo "==> done"; exit 0
fi
bad=0; n=0
for f in $(git ls-files 'web/*.html' 'web/*.js' 'web/*.css' 'web/*.svg' 'web/*.webmanifest'); do
  # only files this deploy touched, unless the box was already current (then check them all)
  if [ -n "$changed" ] && ! grep -qx "$f" <<<"$changed"; then continue; fi
  # strip CR so a CRLF working tree on Windows does not look like drift
  l="$(git show "HEAD:$f" | tr -d '\r' | sha256sum | cut -c1-16)"
  r="$(ssh "$HOST" "curl -fsS -m 30 http://127.0.0.1:$PORT/$(basename "$f") | tr -d '\r' | sha256sum | cut -c1-16" || true)"
  n=$((n + 1))
  if [ "$l" != "$r" ]; then echo "   NOT SERVED: $f"; bad=1; fi
done
if [ "$bad" -ne 0 ]; then
  echo "!! the running server is not serving the repo's version of the page(s) above" >&2; exit 1
elif [ "$n" -eq 0 ]; then echo "   no web pages changed in this deploy"
else echo "   $n page(s) match what the server is serving"; fi

echo "==> done"
