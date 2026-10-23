#!/usr/bin/env python3
"""HTTP contract checks for the public dashboard status endpoint."""

import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))
import server


class StatusTest(unittest.TestCase):
    def setUp(self):
        self.data = tempfile.TemporaryDirectory()
        self.addCleanup(self.data.cleanup)
        data_patch = patch.object(server, "_DATA", self.data.name)
        data_patch.start()
        self.addCleanup(data_patch.stop)
        demo_patch = patch.object(server, "DEMO", False)
        demo_patch.start()
        self.addCleanup(demo_patch.stop)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.H)
        thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join)
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)
        self.base_url = "http://127.0.0.1:%d" % self.httpd.server_port

    def get(self, path, cookie=None):
        headers = {"Cookie": cookie} if cookie else {}
        req = urllib.request.Request(self.base_url + path, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status, json.load(response)

    def test_status_is_public_and_metadata_is_identical_across_auth(self):
        server.set_dashboard_password("test-password")
        status, locked = self.get("/api/status")
        self.assertEqual(status, 200)
        self.assertEqual(locked["configured"], False)
        self.assertEqual(locked["gated"], True)
        self.assertEqual(locked["authed"], False)
        self.assertEqual(locked["api_version"], server.API_VERSION)
        self.assertEqual(locked["capabilities"], list(server.CAPABILITIES))

        with self.assertRaises(urllib.error.HTTPError) as blocked:
            self.get("/api/summary")
        self.assertEqual(blocked.exception.code, 401)
        blocked.exception.close()

        _, unlocked = self.get("/api/status", "sid=" + server.make_session())
        self.assertEqual(unlocked["authed"], True)
        self.assertEqual(
            {key: locked[key] for key in ("api_version", "capabilities")},
            {key: unlocked[key] for key in ("api_version", "capabilities")},
        )

    def test_demo_claims_only_implemented_maintenance_capabilities(self):
        with patch.object(server, "DEMO", True):
            status, demo = self.get("/api/status")
            _, summary = self.get("/api/summary")
        self.assertEqual(status, 200)
        self.assertEqual(demo, {
            "configured": True,
            "gated": False,
            "authed": True,
            "api_version": server.API_VERSION,
            "capabilities": ["maintenance_guide", "service_centres"],
        })
        self.assertEqual(demo["api_version"], summary["api_version"])


if __name__ == "__main__":
    unittest.main()
