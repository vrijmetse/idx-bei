"""
Tests for API Security Guardrails: DuckDB isolation and Input Validation.
"""

import unittest
from fastapi.testclient import TestClient

from idx.api import app


class TestAPISecurity(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_sql_external_file_read_blocked(self):
        # Attempt to read filesystem via DuckDB built-in read_csv
        resp = self.client.post(
            "/api/query/sql",
            json={"sql": "SELECT * FROM read_csv('/etc/passwd')"},
        )
        self.assertEqual(resp.status_code, 400)
        detail = resp.json()["detail"].lower()
        self.assertTrue(
            "disabled by configuration" in detail
            or "permission error" in detail
            or "not allowed" in detail
        )

    def test_sql_copy_command_blocked(self):
        # Attempt to write to host filesystem via COPY
        resp = self.client.post(
            "/api/query/sql",
            json={"sql": "COPY (SELECT 'pwn') TO '/tmp/exploit.txt' (FORMAT CSV)"},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Only read-only SELECT queries are allowed", resp.json()["detail"])

    def test_ticker_input_validation(self):
        # Path parameter SQL injection or malformed characters must return 400, not 500
        bad_tickers = ["BBCA'", "BBCA;DROP", "BBCA OR 1=1", "INVALID$#", "A", "TOOLONGTICKERNAME"]
        for bad in bad_tickers:
            resp = self.client.get(f"/api/stock/{bad}")
            self.assertEqual(
                resp.status_code,
                400,
                f"Expected 400 for bad ticker '{bad}', got {resp.status_code}",
            )


if __name__ == "__main__":
    unittest.main()
