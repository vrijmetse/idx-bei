"""TDD Test Suite for Global ETF & Pluang Radar Engine.

Verifies:
1. ETF Universe and metadata structure
2. Quantitative calculations: 52-week pullback, after-tax net yield (15% W-8BEN)
3. NAV Decay risk classification (detecting capital destruction traps)
4. Beginner verdict assignments
5. API endpoints (/api/etfs and /api/etf/{ticker})
"""

import unittest
from fastapi.testclient import TestClient
from idx.api import app
from idx.core.etf import (
    GLOBAL_ETF_UNIVERSE,
    calculate_etf_metrics,
    classify_nav_decay_risk,
    assign_beginner_verdict,
    get_all_global_etfs,
    get_etf_detail,
)


class TestGlobalETFRadar(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_etf_universe_completeness(self):
        """Ensure all primary Pluang ETFs are defined with required attributes."""
        expected_tickers = ["SMH", "QQQ", "VOO", "JEPQ", "QQQI", "SCHD", "AMDY", "MSTY", "GLD"]
        for ticker in expected_tickers:
            self.assertIn(ticker, GLOBAL_ETF_UNIVERSE, f"{ticker} must be in GLOBAL_ETF_UNIVERSE")
            item = GLOBAL_ETF_UNIVERSE[ticker]
            self.assertIn("name", item)
            self.assertIn("category", item)
            self.assertIn("asset_class", item)
            self.assertIn("is_pluang_available", item)
            self.assertTrue(item["is_pluang_available"])

    def test_after_tax_net_yield_calculation(self):
        """Test that 15% US withholding tax (W-8BEN treaty) is mathematically deducted."""
        # 12.0% gross yield -> 15% tax deduction -> 10.2% net yield
        metrics = calculate_etf_metrics(
            current_price=60.0,
            high_52w=61.0,
            low_52w=50.0,
            gross_yield_pct=12.0,
            price_return_1y=15.0,
            total_return_1y=27.0,
            price_return_3y=20.0,
            total_return_3y=82.0,
        )
        self.assertAlmostEqual(metrics["net_after_tax_yield_pct"], 10.2, places=1)
        self.assertEqual(metrics["tax_rate_pct"], 15.0)

    def test_52w_pullback_calculation(self):
        """Test percentage below 52-week high calculation."""
        # High 100, current 90 -> -10.0%
        metrics = calculate_etf_metrics(
            current_price=90.0,
            high_52w=100.0,
            low_52w=70.0,
            gross_yield_pct=1.0,
            price_return_1y=10.0,
            total_return_1y=11.0,
            price_return_3y=30.0,
            total_return_3y=33.0,
        )
        self.assertAlmostEqual(metrics["pullback_52w_pct"], -10.0, places=1)

    def test_nav_decay_risk_classification(self):
        """Verify strict classification of NAV decay to protect beginners from value traps."""
        # MSTY / ULTY style: massive 1-year price destruction > -40%
        risk_critical = classify_nav_decay_risk(price_return_1y=-75.0, gross_yield=75.0)
        self.assertEqual(risk_critical, "CRITICAL_TRAP")

        # AMDY style: high yield but negative capital price erosion
        risk_high = classify_nav_decay_risk(price_return_1y=-20.0, gross_yield=65.0)
        self.assertEqual(risk_high, "HIGH_RISK")

        # JEPQ / QQQI style: solid double digit yield with POSITIVE price appreciation
        risk_healthy_income = classify_nav_decay_risk(price_return_1y=15.0, gross_yield=12.0)
        self.assertEqual(risk_healthy_income, "LOW_RISK_INCOME")

        # SMH / QQQ style: pure growth
        risk_growth = classify_nav_decay_risk(price_return_1y=60.0, gross_yield=0.3)
        self.assertEqual(risk_growth, "PRIME_GROWTH")

    def test_beginner_verdict_assignment(self):
        """Ensure clear, dumbed-down actionable verdicts for beginners."""
        # SMH -> Growth Champion
        verdict_smh = assign_beginner_verdict(category="growth", nav_risk="PRIME_GROWTH")
        self.assertEqual(verdict_smh["badge"], "GROWTH CHAMPION")
        self.assertEqual(verdict_smh["action"], "BUY / DCA")

        # JEPQ -> Monthly Cashflow
        verdict_jepq = assign_beginner_verdict(category="income", nav_risk="LOW_RISK_INCOME")
        self.assertEqual(verdict_jepq["badge"], "MONTHLY CASHFLOW")
        self.assertEqual(verdict_jepq["action"], "BUY FOR INCOME")

        # MSTY -> Capital Decay Trap
        verdict_msty = assign_beginner_verdict(category="speculative", nav_risk="CRITICAL_TRAP")
        self.assertEqual(verdict_msty["badge"], "CAPITAL DECAY TRAP")
        self.assertEqual(verdict_msty["action"], "AVOID / TRADING ONLY")

    def test_api_get_etfs_endpoint(self):
        """Test /api/etfs endpoint returns 200 with structured list."""
        resp = self.client.get("/api/etfs")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("etfs", data)
        self.assertIn("total", data)
        self.assertGreaterEqual(data["total"], 8)
        
        tickers = [e["ticker"] for e in data["etfs"]]
        self.assertIn("SMH", tickers)
        self.assertIn("QQQ", tickers)
        self.assertIn("JEPQ", tickers)
        self.assertIn("AMDY", tickers)

    def test_api_get_etf_detail_endpoint(self):
        """Test /api/etf/{ticker} endpoint returns 200 and handles invalid ticker."""
        # Valid ticker
        resp = self.client.get("/api/etf/SMH")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["ticker"], "SMH")
        self.assertIn("metrics", data)
        self.assertIn("verdict", data)

        # Invalid ticker
        resp_invalid = self.client.get("/api/etf/XYZUNKNOWN")
        self.assertEqual(resp_invalid.status_code, 404)

    def test_stock_endpoint_supports_global_etfs(self):
        """Test unified /api/stock/{ticker} and blocks endpoint support global ETFs like SMH."""
        resp = self.client.get("/api/stock/SMH")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["ticker"], "SMH")
        self.assertTrue(data.get("is_etf", False))
        self.assertEqual(data.get("currency"), "USD")
        self.assertIn("records", data)
        self.assertGreater(len(data["records"]), 0)
        self.assertIn("latest", data)
        self.assertIn("profile", data)
        self.assertIn("VanEck", data["profile"]["name"])

        # Blocks endpoint returns graceful empty response for ETFs without 404
        resp_blocks = self.client.get("/api/stock/SMH/blocks")
        self.assertEqual(resp_blocks.status_code, 200)
        data_blocks = resp_blocks.json()
        self.assertEqual(data_blocks["ticker"], "SMH")
        self.assertEqual(data_blocks["blocks"], [])


if __name__ == "__main__":
    unittest.main()
