import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from security import (RateLimiter, create_token, hash_password,  # noqa: E402
                      verify_password, verify_token)


class SecurityTests(unittest.TestCase):
    def test_password_roundtrip(self):
        h = hash_password("s3cret-pass")
        self.assertTrue(verify_password("s3cret-pass", h))
        self.assertFalse(verify_password("wrong", h))
        self.assertNotEqual(h, hash_password("s3cret-pass"))  # unique salt

    def test_bad_hash_is_rejected(self):
        self.assertFalse(verify_password("x", "garbage"))

    def test_token_roundtrip(self):
        self.assertEqual(verify_token(create_token(7, "k", 60), "k"), 7)

    def test_token_wrong_secret_expired_tampered(self):
        t = create_token(7, "k", 60, now=1000)
        self.assertIsNone(verify_token(t, "other", now=1010))
        self.assertIsNone(verify_token(t, "k", now=2000))
        self.assertIsNone(verify_token(t[:-2] + "xx", "k", now=1010))
        self.assertIsNone(verify_token("nonsense", "k"))
        self.assertIsNone(verify_token("", "k"))

    def test_rate_limiter(self):
        rl = RateLimiter(3, 60)
        self.assertTrue(all(rl.allow("ip", now=100 + i) for i in range(3)))
        self.assertFalse(rl.allow("ip", now=110))
        self.assertTrue(rl.allow("ip", now=200))
        self.assertTrue(rl.allow("other", now=110))


if __name__ == "__main__":
    unittest.main()
