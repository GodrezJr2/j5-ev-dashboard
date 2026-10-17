#!/usr/bin/env bash
# Manual / break-glass deploy from your own machine over ssh. The normal path is the CI/CD
# pipeline (docs/ci-cd.md): push, and the box checks and deploys it by itself. This runs the same
# tools/apply.sh on the box, so both paths restart and verify identically.
#
#   ./tools/deploy.sh user@host                       # or set CARLINKO_HOST (an ssh alias works too)
#
#   CARLINKO_DIR           checkout the units run from, on the box   (default ~/j5-ev-dashboard)
#   CARLINKO_LOCAL_REMOTE  remote your commit must already be on     (default origin)
#   CARLINKO_REMOTE / CARLINKO_BRANCH / CARLINKO_PORT / CARLINKO_TOKEN_FILE / CARLINKO_SERVICES
#                          as in tools/apply.sh; the box fetches from CARLINKO_REMOTE (default origin)
#
# It refuses unpushed commits and dirty tracked files, because the box deploys commits, not your
# working tree.
set -euo pipefail

HOST="${1:-${CARLINKO_HOST:-}}"
DIR="${CARLINKO_DIR:-~/j5-ev-dashboard}"
LOCAL_REMOTE="${CARLINKO_LOCAL_REMOTE:-origin}"
REMOTE="${CARLINKO_REMOTE:-origin}"
BRANCH="${CARLINKO_BRANCH:-main}"
TOKEN_FILE="${CARLINKO_TOKEN_FILE:-}"

if [ -z "$HOST" ]; then
  echo "usage: $0 user@host   (or set CARLINKO_HOST)" >&2
  exit 2
fi

cd "$(dirname "$0")/.."

echo "==> local checks"
python tools/ci_check.py
if ! git diff --quiet HEAD -- . ; then
  echo "!! tracked files have uncommitted changes; commit them first (the box deploys commits)" >&2
  exit 1
fi
git fetch -q "$LOCAL_REMOTE" "$BRANCH"
HEAD_SHA="$(git rev-parse HEAD)"
if ! git merge-base --is-ancestor "$HEAD_SHA" "$LOCAL_REMOTE/$BRANCH"; then
  echo "!! HEAD is not on $LOCAL_REMOTE/$BRANCH; run: git push $LOCAL_REMOTE $BRANCH" >&2
  exit 1
fi

# settings apply.sh reads, forwarded only when you set them
fwd="CARLINKO_REMOTE=$REMOTE CARLINKO_BRANCH=$BRANCH"
[ -n "$TOKEN_FILE" ] && fwd="$fwd CARLINKO_TOKEN_FILE=$TOKEN_FILE"
[ -n "${CARLINKO_PORT:-}" ] && fwd="$fwd CARLINKO_PORT=$CARLINKO_PORT"
[ -n "${CARLINKO_SERVICES:-}" ] && fwd="$fwd CARLINKO_SERVICES='$CARLINKO_SERVICES'"
auth=""
[ -n "$TOKEN_FILE" ] && auth="-c http.extraHeader=\"Authorization: token \$(cat $TOKEN_FILE)\""

echo "==> deploying ${HEAD_SHA:0:7} to $HOST:$DIR"
# Move HEAD here, then run apply.sh with --from: that way apply.sh is always the version that was
# just pulled (it does not exist yet on a box that predates it), same as the CI workflow.
# $DIR, $auth, $fwd, $REMOTE and $BRANCH expand locally on purpose.
ssh "$HOST" "cd $DIR && old=\$(git rev-parse HEAD) && git $auth fetch -q $REMOTE $BRANCH && \
  git merge --ff-only -q FETCH_HEAD && env $fwd tools/apply.sh --from \$old"

echo "==> done"
