#!/usr/bin/env bash
# Runs ON the box, inside the git checkout the systemd units run from. Brings that checkout to the
# wanted commit, restarts only the units whose code changed, and proves the running server is
# serving it. Used by the CI/CD pipeline (.gitea/workflows/deploy.yml) and by tools/deploy.sh.
#
#   tools/apply.sh                   fetch <remote>/<branch>, fast-forward to it, then restart + verify
#   tools/apply.sh --from <sha>      the caller already moved HEAD (CI does, so this script is always
#                                    the NEW version); treat <sha>..HEAD as what changed
#
#   CARLINKO_REMOTE=origin  CARLINKO_BRANCH=main  CARLINKO_PORT=8088
#   CARLINKO_TOKEN_FILE=~/.gitea_token   file with an access token, sent as an Authorization header
#                                        for http(s) remotes (leave unset for ssh remotes)
#   CARLINKO_SERVICES="carlinko-web carlinko-logger"   force-restart exactly these units
#
# server.py imports auth + known_cars; logger.py imports auth. A logger restart drops its single
# CarLinko WebSocket session, so it is left alone unless it has to change. Web-only edits are served
# from disk and need no restart.
set -euo pipefail

# Everything lives in main() and the file ends with `exit`: `git merge` below can replace this very
# file mid-run, and bash would otherwise read the next command from the new bytes.
main() {
  cd "$(dirname "${BASH_SOURCE[0]}")/.."
  local remote="${CARLINKO_REMOTE:-origin}" branch="${CARLINKO_BRANCH:-main}"
  local port="${CARLINKO_PORT:-8088}" token_file="${CARLINKO_TOKEN_FILE:-}"
  local from="" old new changed services status f l r n=0 bad=0

  while [ $# -gt 0 ]; do
    case "$1" in
      --from) from="${2:?--from needs a sha}"; shift 2 ;;
      *) echo "usage: $0 [--from <sha>]" >&2; return 2 ;;
    esac
  done

  git_remote() {   # git with the token header when the remote is http(s)
    if [ -n "$token_file" ]; then
      git -c http.extraHeader="Authorization: token $(cat "${token_file/#\~/$HOME}")" "$@"
    else
      git "$@"
    fi
  }

  if [ -z "$from" ]; then
    echo "==> updating $(basename "$PWD") from $remote/$branch"
    if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
      echo "!! tracked files are modified here; refusing to overwrite them:" >&2
      git status --short --untracked-files=no >&2
      return 1
    fi
    old="$(git rev-parse HEAD)"
    git_remote fetch -q "$remote" "$branch"
    git merge --ff-only -q FETCH_HEAD || { echo "!! cannot fast-forward (diverged history)" >&2; return 1; }
  else
    old="$from"
  fi
  new="$(git rev-parse HEAD)"
  echo "   ${old:0:7} -> ${new:0:7}"
  changed=""
  [ "$old" != "$new" ] && changed="$(git diff --name-only "$old" "$new")"
  if [ -z "$changed" ]; then echo "   nothing changed"; else sed 's/^/   changed: /' <<<"$changed"; fi

  if [ -n "${CARLINKO_SERVICES:-}" ]; then
    services="$CARLINKO_SERVICES"
  else
    services=""
    grep -Eq '^tools/(server|auth|known_cars)\.py$' <<<"$changed" && services="carlinko-web"
    grep -Eq '^tools/(logger|auth)\.py$' <<<"$changed" && services="$services carlinko-logger"
    services="${services# }"
  fi
  if [ -n "$services" ]; then
    echo "==> restarting: $services"
    # shellcheck disable=SC2086  # the unit list is meant to word-split
    sudo -n systemctl restart $services
    # shellcheck disable=SC2086
    sleep 3; systemctl is-active $services
  else
    echo "==> no restart needed (no server/logger code changed)"
  fi

  echo "==> health"
  for n in $(seq 1 20); do
    status="$(curl -fsS -m 5 "http://127.0.0.1:$port/api/status" 2>/dev/null)" && break
    sleep 2
  done
  [ -n "${status:-}" ] || { echo "!! /api/status did not answer on :$port" >&2; return 1; }
  echo "   $status"

  echo "==> served pages"
  if grep -q '"gated": *true' <<<"$status"; then
    # a dashboard password makes the server answer unauthenticated fetches with the login page
    echo "   password-gated; skipped the served-page comparison"
    return 0
  fi
  n=0
  for f in $(git ls-files 'web/*.html' 'web/*.js' 'web/*.css' 'web/*.svg' 'web/*.webmanifest'); do
    # only the files this run touched, unless nothing changed (then check them all)
    if [ -n "$changed" ] && ! grep -qx "$f" <<<"$changed"; then continue; fi
    # strip CR so a CRLF checkout on Windows does not look like a difference
    l="$(git show "HEAD:$f" | tr -d '\r' | sha256sum | cut -c1-16)"
    r="$(curl -fsS -m 30 "http://127.0.0.1:$port/$(basename "$f")" | tr -d '\r' | sha256sum | cut -c1-16 || true)"
    n=$((n + 1))
    if [ "$l" != "$r" ]; then echo "   NOT SERVED: $f"; bad=1; fi
  done
  if [ "$bad" -ne 0 ]; then
    echo "!! the running server is not serving the repo's version of the page(s) above" >&2
    return 1
  elif [ "$n" -eq 0 ]; then echo "   no web pages changed"
  else echo "   $n page(s) match what the server is serving"; fi
}

main "$@"
exit $?
