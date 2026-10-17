#!/usr/bin/env python3
"""Static checks run before anything is deployed (CI) and by tools/deploy.sh.

No dependencies, nothing is executed: Python files must compile, JSON must parse, and every
script the dashboard ships to a browser must parse (inline <script> blocks in web/*.html and the
web/*.js files; vendored leaflet is skipped). Needs `node` for the JS part and says so loudly
when it is missing instead of silently passing.

Run from the repo root:  python tools/ci_check.py
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.chdir(ROOT)

SCRIPT_RE = re.compile(r"<script\b([^>]*)>(.*?)</script>", re.S | re.I)
NOT_JS = re.compile(r"type\s*=\s*[\"'](?:application/(?:ld\+)?json|importmap|speculationrules)", re.I)

problems = []


def tracked(*patterns):
    out = subprocess.run(["git", "ls-files", *patterns], capture_output=True, text=True, check=True)
    return [p for p in out.stdout.splitlines() if p]


def bad(path, msg):
    problems.append(f"{path}: {msg}")
    print(f"  FAIL {path}: {msg}")


def check_python():
    files = tracked("tools/*.py")
    for f in files:
        try:
            with open(f, encoding="utf-8") as fh:
                compile(fh.read(), f, "exec")
        except SyntaxError as e:
            bad(f, f"line {e.lineno}: {e.msg}")
    print(f"python: {len(files)} files")


def check_json():
    files = tracked("web/*.json")
    for f in files:
        try:
            with open(f, encoding="utf-8") as fh:
                json.load(fh)
        except ValueError as e:
            bad(f, str(e))
    print(f"json: {len(files)} files")


def node_check(node, tmp, name, source):
    # parsed as an ES module so `import`, `import()` and top-level await are all accepted
    path = os.path.join(tmp, name)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(source)
    r = subprocess.run([node, "--check", path], capture_output=True, text=True)
    return None if r.returncode == 0 else (r.stderr.strip().splitlines() or ["syntax error"])[:3]


def check_js():
    node = shutil.which("node")
    if not node:
        print("js: SKIPPED, node not found (install Node to check the web scripts)")
        return
    n = 0
    with tempfile.TemporaryDirectory() as tmp:
        for f in tracked("web/*.html"):
            with open(f, encoding="utf-8") as fh:
                html = fh.read()
            for i, m in enumerate(SCRIPT_RE.finditer(html)):
                attrs, body = m.group(1), m.group(2)
                if re.search(r"\bsrc\s*=", attrs) or NOT_JS.search(attrs) or not body.strip():
                    continue
                n += 1
                err = node_check(node, tmp, f"{os.path.basename(f)}.{i}.mjs", body)
                if err:
                    bad(f, f"inline script #{i}: " + " | ".join(err))
        for f in tracked("web/*.js"):
            if os.path.basename(f).startswith("leaflet"):
                continue
            n += 1
            with open(f, encoding="utf-8") as fh:
                err = node_check(node, tmp, os.path.basename(f) + ".mjs", fh.read())
            if err:
                bad(f, " | ".join(err))
    print(f"js: {n} scripts")


if __name__ == "__main__":
    check_python()
    check_json()
    check_js()
    if problems:
        print(f"\n{len(problems)} problem(s)", file=sys.stderr)
        sys.exit(1)
    print("all checks passed")
