import os
import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

_TMP = tempfile.TemporaryDirectory()
os.environ["DATA_DIR"] = _TMP.name
os.environ["SECRET_KEY"] = "test-secret"
os.environ["ADMIN_USERNAME"] = "teacher"
os.environ["ADMIN_PASSWORD"] = "password123"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from fastapi.testclient import TestClient
    from PIL import Image
    import main
    HAVE_DEPS = True
except ImportError:  # fastapi / pytesseract not installed
    HAVE_DEPS = False


def png_bytes():
    buf = BytesIO()
    Image.new("RGB", (40, 40), "white").save(buf, "PNG")
    return buf.getvalue()


@unittest.skipUnless(HAVE_DEPS, "fastapi/pytesseract not installed")
class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        main.semantic_unavailable = True  # keyword-only, no model download
        cls.client = TestClient(main.app)
        cls.client.__enter__()  # runs lifespan -> creates tables + bootstrap user
        with main.db() as con:
            main.create_user(con, "other", "password456")
        cls.auth = cls.login("teacher", "password123")
        cls.other = cls.login("other", "password456")

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        _TMP.cleanup()

    @classmethod
    def login(cls, u, p):
        r = cls.client.post("/auth/login", json={"username": u, "password": p})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    def payload(self, **over):
        data = {
            "student_name": "A", "question_title": "Q", "model_answer": "m",
            "student_answer": "sunlight water",
            "rubric": [{"point": "p", "keywords": ["sunlight"], "semantic_reference": "", "marks": 1}],
            "ai_score": 1, "final_score": 1, "max_marks": 1, "image_path": None,
        }
        data.update(over)
        return data

    # --- auth ---
    def test_endpoints_require_login(self):
        for method, url in [("get", "/submissions"), ("post", "/grade"), ("post", "/ocr"),
                            ("get", "/uploads/1_x.png"), ("delete", "/submissions/1")]:
            self.assertEqual(getattr(self.client, method)(url).status_code, 401, url)

    def test_bad_login(self):
        r = self.client.post("/auth/login", json={"username": "teacher", "password": "nope"})
        self.assertEqual(r.status_code, 401)

    def test_health(self):
        self.assertEqual(self.client.get("/health").json(), {"status": "ok"})

    def test_frontend_origin_5174_is_allowed(self):
        response = self.client.options(
            "/auth/login",
            headers={
                "Origin": "http://127.0.0.1:5174",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("access-control-allow-origin"), "http://127.0.0.1:5174")

    # --- grading ---
    def test_grade(self):
        r = self.client.post("/grade", headers=self.auth, json={
            "student_answer": "sunlight and water",
            "rubric": [{"point": "a", "keywords": ["sunlight"], "marks": 1},
                       {"point": "b", "keywords": ["water"], "marks": 1}]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["score"], 2)

    def test_grade_requires_rubric(self):
        r = self.client.post("/grade", headers=self.auth, json={"student_answer": "x", "rubric": []})
        self.assertEqual(r.status_code, 400)

    # --- submissions ---
    def test_submission_crud_and_isolation(self):
        r = self.client.post("/submissions", headers=self.auth, json=self.payload())
        self.assertEqual(r.status_code, 200)
        sid = r.json()["submission_id"]
        mine = self.client.get("/submissions", headers=self.auth).json()
        self.assertTrue(any(s["id"] == sid for s in mine))
        # another teacher cannot see, edit or delete it
        self.assertFalse(any(s["id"] == sid for s in self.client.get("/submissions", headers=self.other).json()))
        self.assertEqual(self.client.put(f"/submissions/{sid}", headers=self.other, json={"final_score": 0}).status_code, 404)
        self.assertEqual(self.client.delete(f"/submissions/{sid}", headers=self.other).status_code, 404)
        # owner can
        self.assertEqual(self.client.put(f"/submissions/{sid}", headers=self.auth, json={"final_score": 0.5}).status_code, 200)
        self.assertEqual(self.client.put(f"/submissions/{sid}", headers=self.auth, json={"final_score": 9}).status_code, 400)
        self.assertEqual(self.client.delete(f"/submissions/{sid}", headers=self.auth).status_code, 200)
        self.assertEqual(self.client.delete(f"/submissions/{sid}", headers=self.auth).status_code, 404)

    def test_score_out_of_range_rejected(self):
        r = self.client.post("/submissions", headers=self.auth, json=self.payload(final_score=5))
        self.assertEqual(r.status_code, 400)

    def test_cannot_reference_foreign_image(self):
        r = self.client.post("/submissions", headers=self.auth, json=self.payload(image_path="/uploads/999_x.png"))
        self.assertEqual(r.status_code, 400)

    # --- uploads / ocr ---
    def test_ocr_rejects_non_image(self):
        r = self.client.post("/ocr", headers=self.auth, files={"file": ("a.txt", b"hi", "text/plain")})
        self.assertEqual(r.status_code, 400)

    def test_ocr_rejects_corrupt_image(self):
        r = self.client.post("/ocr", headers=self.auth, files={"file": ("a.png", b"notpng", "image/png")})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(list(main.UPLOAD_DIR.glob("*.png")), [])

    def test_model_answer_image_ocr_does_not_store_upload(self):
        with patch.object(main.pytesseract, "image_to_string", return_value="Model answer text"):
            r = self.client.post(
                "/ocr?store_image=false",
                headers=self.auth,
                files={"file": ("model.png", png_bytes(), "image/png")},
            )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["extracted_text"], "Model answer text")
        self.assertIsNone(r.json()["image_path"])
        self.assertEqual(list(main.UPLOAD_DIR.glob("*.png")), [])

    def test_upload_visible_only_to_owner(self):
        name = "1_" + "a" * 32 + ".png"
        (main.UPLOAD_DIR / name).write_bytes(png_bytes())
        with main.db() as con:
            uid = con.execute("SELECT id FROM users WHERE username='teacher'").fetchone()["id"]
        owned = f"{uid}_" + "b" * 32 + ".png"
        (main.UPLOAD_DIR / owned).write_bytes(png_bytes())
        self.assertEqual(self.client.get(f"/uploads/{owned}", headers=self.auth).status_code, 200)
        self.assertEqual(self.client.get(f"/uploads/{owned}", headers=self.other).status_code, 404)
        self.assertEqual(self.client.get("/uploads/..%2Fgrader.db", headers=self.auth).status_code, 404)

    # --- accounts ---
    def test_change_password(self):
        with main.db() as con:
            main.create_user(con, "pwuser", "oldpassword1")
        h = self.login("pwuser", "oldpassword1")
        bad = self.client.post("/auth/change-password", headers=h,
                               json={"current_password": "wrong", "new_password": "newpassword1"})
        self.assertEqual(bad.status_code, 400)
        short = self.client.post("/auth/change-password", headers=h,
                                 json={"current_password": "oldpassword1", "new_password": "short"})
        self.assertEqual(short.status_code, 422)
        ok = self.client.post("/auth/change-password", headers=h,
                              json={"current_password": "oldpassword1", "new_password": "newpassword1"})
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(self.client.post("/auth/login", json={"username": "pwuser", "password": "oldpassword1"}).status_code, 401)
        self.assertEqual(self.client.post("/auth/login", json={"username": "pwuser", "password": "newpassword1"}).status_code, 200)

    def test_admin_user_management(self):
        self.assertTrue(self.client.get("/auth/me", headers=self.auth).json()["is_admin"])
        self.assertEqual(self.client.get("/admin/users", headers=self.other).status_code, 403)
        self.assertEqual(self.client.post("/admin/users", headers=self.other,
                         json={"username": "x", "password": "password789"}).status_code, 403)
        r = self.client.post("/admin/users", headers=self.auth, json={"username": "newbie", "password": "password789"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.post("/admin/users", headers=self.auth,
                         json={"username": "newbie", "password": "password789"}).status_code, 409)
        uid = r.json()["user_id"]
        self.assertEqual(self.client.post(f"/admin/users/{uid}/reset-password", headers=self.auth,
                         json={"new_password": "freshpassword1"}).status_code, 200)
        self.assertEqual(self.client.post("/auth/login", json={"username": "newbie", "password": "freshpassword1"}).status_code, 200)
        self.assertEqual(self.client.post("/admin/users/9999/reset-password", headers=self.auth,
                         json={"new_password": "freshpassword1"}).status_code, 404)
        names = [u["username"] for u in self.client.get("/admin/users", headers=self.auth).json()]
        self.assertIn("newbie", names)

    def test_ocr_returns_sections(self):
        # Needs a real Tesseract; only checks the response shape for a blank image.
        import shutil
        if not shutil.which("tesseract"):
            self.skipTest("tesseract not installed")
        r = self.client.post("/ocr", headers=self.auth, files={"file": ("a.png", png_bytes(), "image/png")})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["sections"], [])


if __name__ == "__main__":
    unittest.main()
