# Dashboard release flow

The HTTP contract has one version: integer `API_VERSION` in `tools/server.py`.
It appears in both `/api/status` and `/api/summary` and changes only when a
summary field is removed, renamed, or changes type, units, or meaning. New
operations are listed in `/api/status` `capabilities` without a version bump.
Git `release-X.Y.Z` tags identify source releases and are not sent to clients.

## Prepare

Work on `feat/carlinko-device-endpoints`, with the intended changes present.
Choose a tag greater than all previous `release-*` tags:

```bash
python3 tools/release.py prepare release-X.Y.Z
```

This creates `docs/releases/X.Y.Z.md` with the current API contract and
capabilities. Complete its changes, client compatibility, and deployment
sections. Review `docs/api-map.md`; if `/api/summary` broke, raise
`API_VERSION` and document the exact change there. Verify every advertised
capability against the implemented route and check demo status separately.

Run the checks and review the diff:

```bash
python3 tools/ci_check.py
python3 tools/status_selftest.py
python3 tools/release_selftest.py
git diff --check
git diff
```

Commit the notes, API map, code, and tests together. The release script does
not commit or push.

## Tag

From a clean worktree on the same branch:

```bash
python3 tools/release.py tag release-X.Y.Z
```

The command checks the branch, notes, clean worktree, monotonic tag order,
static checks, and HTTP status tests, then creates an annotated local tag.
Inspect and push the reviewed branch and tag to the intended remote. Publish
and deploy separately.

For self-hosted deployments, follow the [README update instructions](../README.md#updating-a-self-hosted-box).
After deployment, check the running public contract against the tagged source:

```bash
python3 tools/release.py verify release-X.Y.Z https://your-dashboard.example
```

This compares `api_version` and capabilities. It cannot prove which commit is
running when two commits expose the same contract. Test a representative
feature operation when a capability changed.
