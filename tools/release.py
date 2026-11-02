#!/usr/bin/env python3
"""Prepare, tag, and check a dashboard release from the CarLinko branch.

The release tag identifies source code. The HTTP API exposes only API_VERSION
and capabilities. Tagging never pushes or deploys anything.
"""

import argparse
import ast
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
NOTES = ROOT / "docs" / "releases"
BRANCH = "feat/carlinko-device-endpoints"
TAG_PATTERN = re.compile(r"^release-(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def git(*args):
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def version_from_tag(tag):
    match = TAG_PATTERN.fullmatch(tag)
    if not match:
        raise ValueError("expected release-X.Y.Z with a stable SemVer version")
    return ".".join(match.groups()), tuple(map(int, match.groups()))


def contract_from_source(source):
    tree = ast.parse(source)
    values = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {"API_VERSION", "CAPABILITIES"}:
                    values[target.id] = ast.literal_eval(node.value)
    api_version = values.get("API_VERSION")
    capabilities = values.get("CAPABILITIES")
    if type(api_version) is not int or not isinstance(capabilities, tuple):
        raise ValueError("tools/server.py must declare literal API_VERSION and CAPABILITIES")
    if not all(isinstance(item, str) for item in capabilities):
        raise ValueError("CAPABILITIES must contain only strings")
    return api_version, list(capabilities)


def require_branch():
    current = git("branch", "--show-current")
    if current != BRANCH:
        raise ValueError(f"switch to {BRANCH} first (currently {current or 'detached'})")


def require_fresh_tag(tag, number):
    existing = git("tag", "--list", "release-*").splitlines()
    versions = [version_from_tag(item)[1] for item in existing if TAG_PATTERN.fullmatch(item)]
    if tag in existing:
        raise ValueError(f"{tag} already exists")
    if versions and number <= max(versions):
        raise ValueError("release version must be higher than every existing release tag")


def prepare(tag):
    require_branch()
    version, number = version_from_tag(tag)
    require_fresh_tag(tag, number)
    api_version, capabilities = contract_from_source(
        (ROOT / "tools" / "server.py").read_text(encoding="utf-8")
    )
    path = NOTES / f"{version}.md"
    if path.exists():
        raise ValueError(f"release notes already exist: {path.relative_to(ROOT)}")
    NOTES.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"# Dashboard {version}\n\n"
        "## Changes\n\nTODO: describe owner-visible changes.\n\n"
        f"## Client compatibility\n\nAPI contract: {api_version}. "
        f"Advertised capabilities: {', '.join(capabilities) or 'none'}.\n\n"
        "TODO: describe capability additions and any breaking /api/summary change; "
        "write 'none' when unchanged.\n\n"
        "## Deployment\n\nTODO: note any data migration or configuration action; "
        "write 'none' when unnecessary.\n",
        encoding="utf-8",
    )
    print(f"Prepared {tag}. Fill {path.relative_to(ROOT)}, review and commit the changes.")


def tag_release(tag):
    require_branch()
    version, number = version_from_tag(tag)
    require_fresh_tag(tag, number)
    notes = NOTES / f"{version}.md"
    if not notes.is_file() or "TODO" in notes.read_text(encoding="utf-8"):
        raise ValueError(f"complete and commit {notes.relative_to(ROOT)} before tagging")
    contract_from_source((ROOT / "tools" / "server.py").read_text(encoding="utf-8"))
    if git("status", "--porcelain"):
        raise ValueError("commit all release changes before tagging")
    for check in ("ci_check.py", "status_selftest.py", "release_selftest.py"):
        subprocess.run([sys.executable, str(ROOT / "tools" / check)], cwd=ROOT, check=True)
    subprocess.run(
        ["git", "tag", "-a", tag, "-m", f"Dashboard {version}"], cwd=ROOT, check=True
    )
    print(f"Created local annotated tag {tag}. Review deployment and push separately.")


def verify_running(tag, base_url):
    version_from_tag(tag)
    if not base_url.startswith(("https://", "http://")):
        raise ValueError("server URL must start with http:// or https://")
    expected_version, expected_capabilities = contract_from_source(
        git("show", f"{tag}:tools/server.py")
    )
    request = urllib.request.Request(base_url.rstrip("/") + "/api/status")
    with urllib.request.urlopen(request, timeout=10) as response:
        status = json.load(response)
    if status.get("api_version") != expected_version:
        raise ValueError(
            f"running API reports {status.get('api_version')!r}, expected {expected_version!r}"
        )
    capabilities = status.get("capabilities")
    if capabilities != expected_capabilities:
        raise ValueError(
            f"running capabilities {capabilities!r} differ from {tag} {expected_capabilities!r}"
        )
    print(
        f"Running API matches {tag}: contract {expected_version}, "
        f"{len(capabilities)} capabilities. This does not prove the deployed commit."
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare", "tag"):
        command = commands.add_parser(name)
        command.add_argument("release_tag")
    verify = commands.add_parser("verify")
    verify.add_argument("release_tag")
    verify.add_argument("server_url")
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            prepare(args.release_tag)
        elif args.command == "tag":
            tag_release(args.release_tag)
        else:
            verify_running(args.release_tag, args.server_url)
    except (ValueError, SyntaxError, subprocess.CalledProcessError, OSError) as error:
        parser.exit(1, f"release: {error}\n")


if __name__ == "__main__":
    main()
