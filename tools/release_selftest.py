#!/usr/bin/env python3
"""Exercise release preparation and tagging in an isolated Git checkout."""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SOURCE = Path(__file__).resolve().parent / "release.py"


class ReleaseFlowTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "tools").mkdir()
        (self.root / "docs").mkdir()
        shutil.copy2(SOURCE, self.root / "tools" / "release.py")
        (self.root / "tools" / "server.py").write_text(
            'API_VERSION = 1\nCAPABILITIES = ("settings_read",)\n', encoding="utf-8"
        )
        for name in ("ci_check.py", "status_selftest.py", "release_selftest.py"):
            (self.root / "tools" / name).write_text("pass\n", encoding="utf-8")
        (self.root / "docs" / "api-map.md").write_text(
            "### Dashboard release and capabilities\n\n"
            "| Release | Capability IDs first advertised | Notes |\n"
            "|---|---|---|\n",
            encoding="utf-8",
        )
        self.git("init", "-q")
        self.git("checkout", "-q", "-b", "feat/carlinko-device-endpoints")
        self.git("config", "user.name", "Release Test")
        self.git("config", "user.email", "release-test@example.invalid")
        self.git("add", ".")
        self.git("commit", "-qm", "initial")

    def git(self, *args):
        return subprocess.run(
            ["git", *args], cwd=self.root, check=True, capture_output=True, text=True
        ).stdout.strip()

    def release(self, *args, success=True):
        result = subprocess.run(
            [sys.executable, "tools/release.py", *args],
            cwd=self.root, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def test_prepare_requires_notes_and_api_map_before_tagging(self):
        self.release("prepare", "release-1.2.3")
        self.assertIn(
            'API_VERSION = 1',
            (self.root / "tools" / "server.py").read_text(encoding="utf-8"),
        )
        self.release("tag", "release-1.2.3", success=False)

        notes = self.root / "docs" / "releases" / "1.2.3.md"
        notes.write_text(notes.read_text(encoding="utf-8").replace("TODO:", "Done:"), encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-qm", "prepare release")
        self.release("tag", "release-1.2.3")
        self.assertEqual(self.git("tag", "--list", "release-*"), "release-1.2.3")
        self.release("prepare", "release-1.2.3", success=False)
        self.release("prepare", "release-1.2.2", success=False)

    def test_rejects_invalid_tag_and_wrong_branch(self):
        self.release("prepare", "release-v1.2.3", success=False)
        self.git("checkout", "-q", "-b", "unrelated")
        self.release("prepare", "release-1.2.3", success=False)


if __name__ == "__main__":
    unittest.main()
