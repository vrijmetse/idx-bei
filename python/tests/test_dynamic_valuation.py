"""
Tests for Dynamic Market Valuation Multiples (PER & PBV Hydration)
Strict TDD suite ensuring real-time prices dynamically update PBV and PER.
"""
import unittest
from idx.compounder import compute_dynamic_multiples, hydrate_company_market_data


class TestDynamicValuation(unittest.TestCase):
    def test_bbca_dynamic_valuation(self):
        # BBCA at current market price 6100 vs historical Q3 2024 filing
        # Book value: 2076.34, EPS (9M): 432.31, fs_date: 2024-09-30
        res = compute_dynamic_multiples(
            price=6100.0,
            book_value=2076.34,
            eps=432.31,
            fs_date="2024-09-30",
        )
        self.assertIsNotNone(res["price_bv"])
        self.assertAlmostEqual(res["price_bv"], 2.94, places=2)
        # Annualized EPS for 9M = 432.31 * 4/3 = 576.4133
        # Dynamic PER = 6100 / 576.4133 = 10.58
        self.assertIsNotNone(res["per"])
        self.assertAlmostEqual(res["per"], 10.58, places=2)

    def test_pipa_dynamic_valuation(self):
        # PIPA at current market price 137 vs historical Q3 2024 filing
        # Book value: 42.5, EPS: -0.25
        res = compute_dynamic_multiples(
            price=137.0,
            book_value=42.5,
            eps=-0.25,
            fs_date="2024-09-30",
        )
        # PBV must reflect current price 137 / 42.5 = 3.22x, NOT obsolete 0.26x!
        self.assertIsNotNone(res["price_bv"])
        self.assertAlmostEqual(res["price_bv"], 3.22, places=2)
        # Unprofitable company: PER is negative
        self.assertIsNotNone(res["per"])
        self.assertLess(res["per"], 0)

    def test_edge_cases(self):
        # Zero price
        res_zero_price = compute_dynamic_multiples(
            price=0.0,
            book_value=100.0,
            eps=10.0,
        )
        self.assertIsNone(res_zero_price["price_bv"])
        self.assertIsNone(res_zero_price["per"])

        # Negative equity / capital deficiency (negative book value)
        res_neg_bv = compute_dynamic_multiples(
            price=50.0,
            book_value=-25.0,
            eps=5.0,
        )
        self.assertEqual(res_neg_bv["price_bv"], -2.0)

        # Zero book value (avoid division by zero)
        res_zero_bv = compute_dynamic_multiples(
            price=100.0,
            book_value=0.0,
            eps=10.0,
        )
        self.assertIsNone(res_zero_bv["price_bv"])

    def test_company_hydration(self):
        company = {
            "code": "BBCA",
            "name": "Bank Central Asia Tbk.",
            "sector": "Financials",
            "sub_sector": "Banks",
            "price": 6625.0,
            "roe": 20.8206,
            "book_value": 2076.34,
            "eps": 432.31,
            "fs_date": "2024-09-30",
            "price_bv": 4.66,
            "per": 22.38,
            "valuation_status": "PREMIUM_VALUATION",
            "is_undervalued": False,
        }
        prices_map = {
            "BBCA": {
                "price": 6100.0,
                "previous_price": 6000.0,
                "daily_change": 100.0,
                "daily_change_pct": 1.67,
            }
        }
        hydrated = hydrate_company_market_data(company, prices_map=prices_map)
        self.assertEqual(hydrated["price"], 6100.0)
        self.assertEqual(hydrated["price_bv"], 2.94)
        self.assertEqual(hydrated["per"], 10.58)
        # With lower dynamic PBV (2.94x vs justified ~3.16x), BBCA is no longer PREMIUM_VALUATION!
        self.assertNotEqual(hydrated["valuation_status"], "PREMIUM_VALUATION")


if __name__ == "__main__":
    unittest.main()
