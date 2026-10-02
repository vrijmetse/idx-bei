import unittest
import pandas as pd
from unittest.mock import patch
from idx.signals import detect_stealth_accumulation
from idx.core.query import query_dataset # Import original for correct patching

class TestSignalsQuant(unittest.TestCase):

    def test_stealth_accumulation_min_turnover_rp(self):
        # Scenario: Illiquid penny stock with broker activity but low total turnover
        # Should NOT be flagged as STEALTH_ACCUMULATION

        min_turnover_rp = 1_000_000_000 # Rp 1 Billion threshold

        # Mock broker_summary_df: Single small institutional trade, zero retail
        broker_summary_df = pd.DataFrame([
            {
                "StockCode": "PNY1", # Penny stock
                "IDFirm": "BB", # Institutional broker
                "Value": 500_000_000, # Rp 500 Million
                "Volume": 10_000_000
            },
            {
                "StockCode": "PNY1",
                "IDFirm": "CC", # Another institutional broker
                "Value": 200_000_000, # Rp 200 Million
                "Volume": 4_000_000
            }
            # No retail broker entries, so retail_val = 0
        ])

        # Mock stock_summary_df for price change
        stock_summary_df = pd.DataFrame([
            {
                "StockCode": "PNY1",
                "Close": 50,
                "Previous": 50,
                "Date": "2026-10-01"
            }
        ])

        # Mock query_dataset from its original location
        with patch("idx.core.query.query_dataset") as mock_query_dataset:
            # Mock query_dataset to return our prepared dataframes
            def mock_side_effect(dataset_name, **kwargs):
                if dataset_name == "broker_summary":
                    return broker_summary_df
                elif dataset_name == "stock_summary":
                    return stock_summary_df
                return pd.DataFrame() # Return empty for others

            mock_query_dataset.side_effect = mock_side_effect

            res = detect_stealth_accumulation(
                broker=broker_summary_df,
                stock=stock_summary_df,
                on_date="2026-10-01",
                min_turnover_rp=min_turnover_rp,
                min_smart_delta=1.0, # Low delta for easier triggering if turnover wasn't checked
                max_price_change_pct=0.1 # Very low price change
            )

            # The total turnover for PNY1 is 700M (500M + 200M), which is < min_turnover_rp (1B)
            # Therefore, PNY1 should NOT be in the results as a STEALTH_ACCUMULATION
            self.assertTrue(res["anomalies_df"].empty, "PNY1 should not be flagged as stealth accumulation due to low turnover")

if __name__ == "__main__":
    unittest.main()