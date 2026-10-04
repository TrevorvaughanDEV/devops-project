"""Tests for the DevOps Monitor app. Run with `pytest` or `python -m unittest`."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_TMP = tempfile.mkdtemp()
os.environ.update(
    APP_ENV="development",
    DATABASE_PATH=os.path.join(_TMP, "data", "test.db"),
    ALLOW_SIGNUP="true",
    SECRET_KEY="test-secret",
)
sys.path.insert(0, str(ROOT))

import app as app_module  # noqa: E402


class AppTestCase(unittest.TestCase):
    def setUp(self):
        app_module.app.config["TESTING"] = True
        self.client = app_module.app.test_client()

    def signup(self, username="alice", password="correct-horse"):
        return self.client.post("/signup", data={"username": username, "password": password})

    # Health and public endpoints -------------------------------------------
    def test_healthz_reports_ok(self):
        res = self.client.get("/healthz")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json(), {"status": "ok"})

    def test_home_records_a_visit(self):
        before = self.client.get("/api/visits").get_json()["total_visits"]
        self.assertEqual(self.client.get("/").status_code, 200)
        after = self.client.get("/api/visits").get_json()["total_visits"]
        self.assertEqual(after, before + 1)

    def test_system_info_returns_metrics(self):
        data = self.client.get("/api/system_info?server=server1").get_json()
        for key in ("cpu", "memory", "disk"):
            self.assertGreaterEqual(data[key], 0)
            self.assertLessEqual(data[key], 100)
        self.assertEqual(data["server"], "Production")
        self.assertIsInstance(data["alerts"], list)

    def test_system_info_rejects_unknown_server(self):
        res = self.client.get("/api/system_info?server=nope")
        self.assertEqual(res.status_code, 400)

    # Alerts ----------------------------------------------------------------
    def test_alerts_fire_only_above_thresholds(self):
        self.assertEqual(app_module.build_alerts(10, 10, 10), [])
        alerts = app_module.build_alerts(95, 50, 95)
        self.assertEqual(len(alerts), 2)
        self.assertTrue(any("CPU" in a for a in alerts))
        self.assertTrue(any("Disk" in a for a in alerts))

    # Auth ------------------------------------------------------------------
    def test_protected_pages_redirect_to_login(self):
        for path in ("/dashboard", "/metrics", "/servers", "/logs", "/projects", "/about"):
            res = self.client.get(path)
            self.assertEqual(res.status_code, 302, path)
            self.assertIn("/login", res.headers["Location"])

    def test_signup_then_login_flow(self):
        self.assertEqual(self.signup("bob", "s3cure-pass").status_code, 302)
        self.client.get("/logout")
        res = self.client.post("/login", data={"username": "bob", "password": "s3cure-pass"})
        self.assertEqual(res.status_code, 302)
        self.assertIn("/dashboard", res.headers["Location"])
        self.assertEqual(self.client.get("/dashboard").status_code, 200)

    def test_wrong_password_is_rejected(self):
        self.signup("carol", "s3cure-pass")
        self.client.get("/logout")
        res = self.client.post("/login", data={"username": "carol", "password": "wrong-pass"})
        self.assertEqual(res.status_code, 401)

    def test_short_password_is_rejected(self):
        self.assertEqual(self.signup("dave", "short").status_code, 400)

    def test_duplicate_username_is_rejected(self):
        self.signup("erin", "s3cure-pass")
        self.client.get("/logout")
        self.assertEqual(self.signup("erin", "another-pass").status_code, 409)

    def test_passwords_are_stored_hashed(self):
        self.signup("frank", "plain-text-pw")
        with app_module.get_db_connection() as conn:
            stored = conn.execute("SELECT password FROM users WHERE username = 'frank'").fetchone()[
                "password"
            ]
        self.assertNotEqual(stored, "plain-text-pw")

    def test_signup_can_be_disabled(self):
        original = app_module.ALLOW_SIGNUP
        app_module.ALLOW_SIGNUP = False
        try:
            self.assertEqual(self.client.get("/signup").status_code, 403)
        finally:
            app_module.ALLOW_SIGNUP = original


class ProductionConfigTest(unittest.TestCase):
    def test_production_refuses_to_start_without_secret_key(self):
        env = {k: v for k, v in os.environ.items() if k != "SECRET_KEY"}
        env.update(APP_ENV="production", DATABASE_PATH=os.path.join(_TMP, "prod.db"))
        result = subprocess.run(
            [sys.executable, "-c", "import app"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SECRET_KEY must be set", result.stderr)


if __name__ == "__main__":
    unittest.main()
