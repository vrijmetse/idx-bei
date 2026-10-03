import unittest
import pandas as pd
from idx.compounder import calculate_graham_number, evaluate_sector_valuation

class TestCompounderQuant(unittest.TestCase):

    def test_calculate_graham_number(self):
        # Test cases for calculate_graham_number
        self.assertIsNone(calculate_graham_number(eps=-10, bvps=100)) # Negative EPS
        self.assertIsNone(calculate_graham_number(eps=10, bvps=-100)) # Negative BVPS
        self.assertIsNone(calculate_graham_number(eps=0, bvps=100)) # Zero EPS
        self.assertIsNone(calculate_graham_number(eps=10, bvps=0)) # Zero BVPS
        
        # Example from Investopedia: EPS $10, BVPS $20 = sqrt(22.5 * 10 * 20) = sqrt(4500) = $67.08
        self.assertAlmostEqual(calculate_graham_number(eps=10, bvps=20), 67.08, delta=0.01)
        # Test with UNTR's actual numbers from financial_ratios.parquet. Function returns 55335.55.
        self.assertAlmostEqual(calculate_graham_number(eps=5590.87, bvps=24341.46), 55335.55, delta=0.1)

    def test_deep_value_per_guard(self):
        # Scenario: Stock with PBV < 1.0, ROE >= 8.0, but PER is negative or zero.
        # Should NOT be classified as DEEP_VALUE.

        mock_company_negative_per = {"pbv": 0.8, "roe": 10.0, "per": -5.0}
        mock_forensics = {"is_value_trap": False}
        result = evaluate_sector_valuation(mock_company_negative_per, mock_forensics)
        self.assertNotEqual(result["status"], "DEEP_VALUE", 
                            "Should not be DEEP_VALUE if PER is negative")

        mock_company_zero_per = {"pbv": 0.8, "roe": 10.0, "per": 0.0}
        result = evaluate_sector_valuation(mock_company_zero_per, mock_forensics)
        self.assertNotEqual(result["status"], "DEEP_VALUE", 
                            "Should not be DEEP_VALUE if PER is zero")

    def test_deep_value_positive_per(self):
        # Scenario: Stock with PBV < 1.0, ROE >= 8.0, and positive PER.
        # Should be classified as DEEP_VALUE.
        mock_company_positive_per = {"pbv": 0.8, "roe": 10.0, "per": 12.0}
        mock_forensics = {"is_value_trap": False}
        result = evaluate_sector_valuation(mock_company_positive_per, mock_forensics)
        self.assertEqual(result["status"], "DEEP_VALUE", 
                           "Should be DEEP_VALUE if PER is positive")

    def test_graham_number_in_valuation_output(self):
        # Test that graham_number is included in the output of evaluate_sector_valuation
        mock_company = {"pbv": 1.2, "roe": 15.0, "per": 10.0, "eps": 10.0, "bvps": 20.0}
        mock_forensics = {"is_value_trap": False}
        result = evaluate_sector_valuation(mock_company, mock_forensics)
        self.assertIn("graham_number", result)
        self.assertAlmostEqual(result["graham_number"], 67.08, delta=0.01)

    def test_distorted_leverage_roe_safe(self):
        """Verify that extreme leverage (e.g. SAFE with DER 99.8x and ROE 2212%) is classified as VALUE_TRAP."""
        from idx.compounder import evaluate_forensics, calculate_dca_compounder_score
        mock_safe = {
            "code": "SAFE",
            "assets": 213.61,
            "liabilities": 211.49,
            "equity": 2.12,
            "sales": 174.44,
            "profitPeriod": 40.36,
            "roe": 2212.2,
            "deRatio": 99.82,
            "sector": "Transportation & Logistic",
        }
        forensics = evaluate_forensics(mock_safe)
        self.assertTrue(forensics["is_value_trap"])
        self.assertIn("DISTORTED_LEVERAGE_ROE", forensics["flags"])
        dca = calculate_dca_compounder_score(mock_safe, forensics, {})
        self.assertEqual(dca["verdict"], "VALUE_TRAP")
        self.assertEqual(dca["dca_rating"], "🚨 HINDARI (Leverage Ekstrem)")

    def test_unvr_not_falsely_trapped(self):
        """Verify that a genuine blue chip compounder like UNVR with high dividend payout is NOT falsely flagged as a value trap."""
        from idx.compounder import evaluate_forensics
        mock_unvr = {
            "code": "UNVR",
            "assets": 16543.58,
            "equity": 3436.08,
            "sales": 27417.35,
            "ebt": 3864.2,
            "profitPeriod": 3009.7,
            "roe": 105.4,
            "deRatio": 3.81,
            "sector": "Consumer Non-Cyclicals",
        }
        forensics = evaluate_forensics(mock_unvr)
        self.assertFalse(forensics["is_value_trap"])
        self.assertNotIn("DISTORTED_LEVERAGE_ROE", forensics["flags"])


if __name__ == "__main__":
    unittest.main()