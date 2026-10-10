from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app


class WebLoginTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.htpasswd_path = Path(self.temporary_directory.name) / "users.htpasswd"
        self.htpasswd_path.write_text("guochu:test-hash\n", encoding="utf-8")
        self.environment = patch.dict(
            os.environ,
            {
                "GUOCHU_AUTH_ENABLED": "true",
                "GUOCHU_HTPASSWD_PATH": str(self.htpasswd_path),
                "GUOCHU_AUTH_USERNAME": "guochu",
                "GUOCHU_SESSION_SECRET": "test-session-secret-that-is-at-least-32-bytes",
                "GUOCHU_SESSION_MAX_AGE_SECONDS": "3600",
            },
        )
        self.environment.start()
        self.client = TestClient(app, base_url="https://testserver")

    def tearDown(self) -> None:
        self.client.close()
        self.environment.stop()
        self.temporary_directory.cleanup()

    def test_login_page_replaces_browser_password_popup(self) -> None:
        protected = self.client.get("/", follow_redirects=False)
        self.assertEqual(protected.status_code, 303)
        self.assertEqual(protected.headers["location"], "/login?next=%2F")

        page = self.client.get("/login")
        self.assertEqual(page.status_code, 200)
        self.assertIn("果初内部测试", page.text)
        self.assertIn("访问密码", page.text)

        api_response = self.client.get("/foods", follow_redirects=False)
        self.assertEqual(api_response.status_code, 401)
        self.assertEqual(api_response.json()["detail"], "请先登录内部测试环境")

    def test_successful_login_sets_secure_cookie_and_password_change_revokes_it(self) -> None:
        with patch("api.main.verify_platform_password", return_value=False):
            denied = self.client.post(
                "/auth/login",
                json={"password": "wrong", "next": "/"},
            )
        self.assertEqual(denied.status_code, 401)

        with patch("api.main.verify_platform_password", return_value=True):
            accepted = self.client.post(
                "/auth/login",
                json={"password": "correct", "next": "/"},
            )
        self.assertEqual(accepted.status_code, 200)
        cookie = accepted.headers["set-cookie"].lower()
        self.assertIn("httponly", cookie)
        self.assertIn("secure", cookie)
        self.assertIn("samesite=lax", cookie)

        home = self.client.get("/")
        self.assertEqual(home.status_code, 200)
        self.assertIn("果初", home.text)

        self.htpasswd_path.write_text("guochu:changed-hash\n", encoding="utf-8")
        revoked = self.client.get("/", follow_redirects=False)
        self.assertEqual(revoked.status_code, 303)

    def test_external_next_destination_is_rejected(self) -> None:
        with patch("api.main.verify_platform_password", return_value=True):
            response = self.client.post(
                "/auth/login",
                json={"password": "correct", "next": "https://example.com"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["redirect"], "/")


if __name__ == "__main__":
    unittest.main()
