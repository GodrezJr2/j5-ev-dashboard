# CI/CD

How a commit gets from the maintainer's laptop to the running dashboard and to GitHub. You do not
need any of this to use the project; it is documented because the repo carries
`.gitea/workflows/deploy.yml` and `tools/apply.sh`, and so you can copy the idea for your own box.

```
laptop ──git push──▶ Gitea (home server, "gitea")
                        │  Actions, act_runner on the same box
                        ▼
                     check ──▶ deploy ──▶ mirror ──▶ GitHub (public, "origin" on the box)
                  tools/ci_check.py   tools/apply.sh   git push
```

| Job | What it does | If it fails |
|---|---|---|
| `check` | `tools/ci_check.py` on a clean worktree of the pushed commit: every `tools/*.py` compiles, JSON parses, every inline `<script>` in `web/*.html` and every `web/*.js` parses (needs `node`). | Nothing is deployed or published. |
| `deploy` | Fast-forwards the checkout the systemd units run from (`~/j5-ev-dashboard`), then `tools/apply.sh --from <old>`: restarts only the units whose code changed, waits for `/api/status`, then fetches each changed page back from the running server and compares it with the repo. | The checkout is reset to the previous commit and `apply.sh` runs again to restart and re-verify it. |
| `mirror` | `git push origin main` to GitHub, from the box. | Deployed fine, GitHub just did not update (usually: GitHub has a commit Gitea does not; pull it, push to Gitea). |

Restart rules (`tools/apply.sh`): `server.py`, `auth.py` or `known_cars.py` changed → `carlinko-web`;
`logger.py` or `auth.py` changed → `carlinko-logger` (a logger restart drops its single CarLinko
WebSocket session, so it is left alone otherwise); web-only edits need no restart because the files
are served from disk.

## One-time setup on the box

- A Gitea repo `jay/j5-ev-dashboard` and an `act_runner` with label `homeserver` in host mode.
- The checkout's remotes: `gitea` → `http://127.0.0.1:3030/jay/j5-ev-dashboard.git` (fetched with the
  token in `~/.gitea_token`, so no secret lives in the repo), `origin` → GitHub over ssh.
- `jay` can run `sudo -n systemctl restart carlinko-web carlinko-logger`.

## Pushing from the laptop

```bash
git remote add gitea http://192.168.1.7:3030/jay/j5-ev-dashboard.git   # Git Credential Manager asks for
git push gitea main                                                    # the Gitea user + a token once
```

Keep `origin` as GitHub, so you can still pull contributors' pull requests from it. If a PR is
merged on GitHub, `git pull origin main && git push gitea main` before your next push, otherwise
the `mirror` job is rejected as non-fast-forward.

## Without the pipeline

`./tools/deploy.sh user@host` fast-forwards the box over ssh and runs the same `tools/apply.sh`
(`CARLINKO_REMOTE=gitea CARLINKO_TOKEN_FILE=~/.gitea_token` to fetch from Gitea). On the box itself,
`tools/apply.sh` alone fetches `origin/main` and does the same.
