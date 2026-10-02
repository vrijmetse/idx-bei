import unittest
import pandas as pd
from unittest.mock import patch
from idx.dividend import analyze_stock_dividend
from datetime import datetime

class TestDividendQuant(unittest.TestCase):

    def setUp(self):
        # Mock USD rate
        self.usd_rate = 15000.0

        # Mock company profile with two dividend tranches
        self.mock_details_dict = {
            "UNTR": {
                "Profiles": [{
                    "NamaEmiten": "United Tractors Tbk.",
                    "ListedShares": 3726500000
                }],
                "Dividen": [
                    { # Latest dividend (Final)
                        "CashDividenPerSaham": 1500.0, # Rp 1500
                        "CashDividenPerSahamMU": "IDR",
                        "CashDividenTotal": 5589750000000.0,
                        "CashDividenTotalMU": "IDR",
                        "TahunBuku": "2025",
                        "CumDate": "2026-06-01",
                        "ExDate": "2026-06-02",
                    },
                    { # Earlier dividend (Interim)
                        "CashDividenPerSaham": 500.0, # Rp 500
                        "CashDividenPerSahamMU": "IDR",
                        "CashDividenTotal": 1863250000000.0,
                        "CashDividenTotalMU": "IDR",
                        "TahunBuku": "2025",
                        "CumDate": "2025-11-01",
                        "ExDate": "2025-11-02",
                    },
                ]
            }
        }

        # Mock stock data
        self.mock_stock_df = pd.DataFrame([
            {
                "StockCode": "UNTR",
                "Date": datetime(2026, 10, 2),
                "Close": 26350.0, # Current price
                "Previous": 26000.0,
                "ListedShares": 3726500000
            }
        ])

        # Mock financial ratios
        self.mock_ratios_df = pd.DataFrame([
            {
                "code": "UNTR",
                "fsDate": datetime(2025, 12, 31),
                "eps": 6000.0, # Full year EPS for 2025
                "profitAttrOwner": 22359000000000.0
            }
        ])

    def test_annualized_dividend_yield_calculation(self):
        # Test that the dividend yield correctly annualizes across multiple tranches
        # Total DPS for 2025 = 1500 (final) + 500 (interim) = 2000 Rp
        # Expected Yield = (2000 / 26350) * 100% = 7.59% (approx)

        with patch("idx.dividend.get_usd_idr_rate", return_value=self.usd_rate):
            result = analyze_stock_dividend(
                ticker="UNTR",
                details_dict=self.mock_details_dict,
                stock_df=self.mock_stock_df,
                ratios_df=self.mock_ratios_df
            )

            self.assertTrue(result["has_dividend"])
            self.assertAlmostEqual(result["annualized_dps"], 2000.0, delta=0.1) # Expect sum of tranches
            self.assertAlmostEqual(result["dividend_yield_pct"], (2000.0 / 26350.0) * 100.0, delta=0.01)
            # Ensure DPR calculation is also based on annualized DPS
            self.assertAlmostEqual(result["fundamentals"]["dpr_pct"], (2000.0 / 6000.0) * 100.0, delta=0.1)

    def test_dividend_dps_raw_heuristic(self):
        # Test the original heuristic for raw DPS (division by 1000 or 100) is removed/corrected
        mock_details_dict_heuristic = {
            "HEURISTIC": {
                "Profiles": [{
                    "NamaEmiten": "Heuristic Co.",
                    "ListedShares": 100000000
                }],
                "Dividen": [
                    { # DPS that would trigger heuristic
                        "CashDividenPerSaham": 20000.0, # Say actual DPS is 20, but it gets parsed as 20000
                        "CashDividenPerSahamMU": "IDR",
                        "TahunBuku": "2026",
                        "CumDate": "2026-06-01",
                        "ExDate": "2026-06-02",
                    },
                ]
            }
        }
        mock_stock_df_heuristic = pd.DataFrame([
            {
                "StockCode": "HEURISTIC",
                "Date": datetime(2026, 10, 2),
                "Close": 100.0, # Low price
                "Previous": 90.0,
                "ListedShares": 100000000
            }
        ])
        mock_ratios_df_heuristic = pd.DataFrame([
            {
                "code": "HEURISTIC",
                "fsDate": datetime(2025, 12, 31),
                "eps": 100.0,
                "profitAttrOwner": 10000000000.0
            }
        ])

        with patch("idx.dividend.get_usd_idr_rate", return_value=self.usd_rate):
            result = analyze_stock_dividend(
                ticker="HEURISTIC",
                details_dict=mock_details_dict_heuristic,
                stock_df=mock_stock_df_heuristic,
                ratios_df=mock_ratios_df_heuristic
            )
            # The price is 100, if dps_raw=20000 was divided by 1000 (heuristic), it becomes 20
            # If heuristic is removed, it should remain 20000 (wrong, but demonstrates heuristic removal)
            # The goal of this test is to ensure the heuristic of dividing by 1000 is GONE
            # So it should NOT be ~20.0 (20000/1000). It should be the raw 20000.0 (which is bad data).
            # The heuristic has been removed in the `api.py` clean_record. So this will pass if `dps_idr` returns the raw value
            # We expect the `dps_idr` to be the raw value, not heuristically divided.
            self.assertNotAlmostEqual(result["annualized_dps"], 20.0, delta=0.1) # Should not be 20.0 (if heuristic was applied)
            self.assertAlmostEqual(result["annualized_dps"], 20000.0, delta=0.1) # Should be the raw value, for now


if __name__ == "__main__":
    unittest.main()
