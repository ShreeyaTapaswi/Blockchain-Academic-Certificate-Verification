"""Access-control tests: verification is public, everything else needs the admin login."""
import os
import tempfile
import unittest

_tmp = tempfile.mkdtemp()
os.environ["CERTCHAIN_DATA"] = os.path.join(_tmp, "data.json")
os.environ["ADMIN_USER"] = "admin"
os.environ["ADMIN_PASSWORD"] = "correct-horse"

import app as certapp  # noqa: E402  (must come after the env vars)

@certapp.app.get("/api/_new_feature")      # a route someone forgets to protect
def _new_feature():
    return "secret"


PROTECTED_POST = ["/api/issue", "/api/bulk", "/api/mine", "/api/revoke", "/api/reset",
                  "/api/seed", "/api/tamper", "/api/undo_tamper", "/api/attack",
                  "/api/institution", "/api/difficulty", "/api/sha256"]
PROTECTED_GET = ["/api/state", "/api/ledger", "/api/registry"]


class AuthTests(unittest.TestCase):
    def setUp(self):
        certapp.app.config["TESTING"] = True
        certapp.FAILS.clear()
        certapp.time.sleep = lambda *_: None      # no delay in tests
        self.c = certapp.app.test_client()

    def login(self, client=None, pw="correct-horse"):
        return (client or self.c).post("/login", data={"username": "admin", "password": pw})

    def test_anonymous_cannot_use_protected_api(self):
        for p in PROTECTED_GET:
            self.assertEqual(self.c.get(p).status_code, 401, p)
        for p in PROTECTED_POST:
            self.assertEqual(self.c.post(p, json={}).status_code, 401, p)

    def test_anonymous_cannot_reset_or_tamper_the_ledger(self):
        before = certapp.state["chain"].to_dict()
        self.c.post("/api/reset", json={}); self.c.post("/api/tamper", json={"block": 1})
        self.assertEqual(before, certapp.state["chain"].to_dict())

    def test_home_is_public_page_when_logged_out(self):
        body = self.c.get("/").get_data(as_text=True)
        self.assertIn("Verify an academic certificate", body)
        self.assertNotIn("Security lab", body)

    def test_public_verification_works_without_login(self):
        r = self.c.post("/api/verify", json={"cert_hash": "ab" * 32})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.get_json()["valid"])
        self.assertEqual(self.c.get("/verify/" + "ab" * 32).status_code, 200)
        self.assertEqual(self.c.get("/qr/" + "ab" * 32).status_code, 200)

    def test_public_verify_does_not_write_to_the_log(self):
        n = len(certapp.state["log"])
        self.c.post("/api/verify", json={"cert_hash": "cd" * 32})
        self.assertEqual(n, len(certapp.state["log"]))

    def test_short_urls_redirect(self):
        self.assertEqual(self.c.get("/verify").headers["Location"], "/")
        self.assertEqual(self.c.get("/admin").headers["Location"], "/login")

    def test_wrong_password_rejected(self):
        self.assertEqual(self.login(pw="nope").status_code, 401)
        self.assertEqual(self.c.get("/api/state").status_code, 401)

    def test_login_then_access_then_logout(self):
        self.assertEqual(self.login().status_code, 302)
        self.assertEqual(self.c.get("/api/state").status_code, 200)
        self.assertIn("Security lab", self.c.get("/").get_data(as_text=True))
        self.c.post("/logout")
        self.assertEqual(self.c.get("/api/state").status_code, 401)

    def test_lockout_after_repeated_failures(self):
        for _ in range(certapp.MAX_FAILS):
            self.login(pw="bad")
        self.assertIn("Too many", self.login().get_data(as_text=True))   # even the right password is refused
        self.assertEqual(self.c.get("/api/state").status_code, 401)

    def test_unknown_routes_default_to_protected(self):
        self.assertEqual(self.c.get("/api/_new_feature").status_code, 401)

    def test_security_headers_and_cookie_flags(self):
        r = self.c.get("/")
        self.assertEqual(r.headers["X-Frame-Options"], "DENY")
        self.assertEqual(r.headers["X-Content-Type-Options"], "nosniff")
        self.assertTrue(certapp.app.config["SESSION_COOKIE_HTTPONLY"])


if __name__ == "__main__":
    unittest.main()
