"""
Tests for Corporate Action Split Adjustment Engine.
"""

import unittest
import pandas as pd
from idx.core.adjustments import adjust_stock_splits, get_all_splits_cache


class TestSplitAdjustment(unittest.TestCase):
    def test_bbca_split_cache_detected(self):
        splits = get_all_splits_cache()
        self.assertIn("BBCA", splits)
        bbca_splits = splits["BBCA"]
        self.assertTrue(len(bbca_splits) >= 1)
        # Check ratio is 5.0
        ratios = [r for d, r in bbca_splits]
        self.assertTrue(any(abs(r - 5.0) < 0.1 for r in ratios))

    def test_bbca_historical_price_adjustment(self):
        # Create unadjusted test df before and after Oct 13, 2021
        df = pd.DataFrame([
            {"Date": "2021-10-12", "Close": 36600.0, "OpenPrice": 36275.0, "High": 36600.0, "Low": 36225.0, "Previous": 36275.0, "Volume": 1000000.0},
            {"Date": "2021-10-13", "Close": 7525.0, "OpenPrice": 7400.0, "High": 8250.0, "Low": 7400.0, "Previous": 7325.0, "Volume": 5000000.0},
        ])
        
        adj_df = adjust_stock_splits(df, "BBCA")
        
        # Row 0 (2021-10-12) must be divided by 5
        self.assertAlmostEqual(adj_df.iloc[0]["Close"], 7320.0, places=1)
        self.assertAlmostEqual(adj_df.iloc[0]["High"], 7320.0, places=1)
        self.assertAlmostEqual(adj_df.iloc[0]["Volume"], 5000000.0, places=1)
        
        # Row 1 (2021-10-13) must remain unadjusted (7525)
        self.assertAlmostEqual(adj_df.iloc[1]["Close"], 7525.0, places=1)


if __name__ == "__main__":
    unittest.main()
