import unittest
import pandas as pd
from idx.signals import composite_alpha_ranking

class TestSignalsQuantScoring(unittest.TestCase):

    def test_negative_roe_penalty(self):
        # Scenario: Stock with severe negative ROE and negative PER
        # Should receive a significant penalty in the composite alpha ranking

        # Mock data for a stock with negative ROE and PER
        mock_ratios_df = pd.DataFrame([
            {
                "code": "BADCO",
                "roe": -50.0,  # Severe negative ROE
                "per": -10.0,  # Negative PER
                "deRatio": 0.5, # Low debt (to isolate ROE/PER penalty)
                "PctFloat": 0.0, # Neutral foreign flow (from mock foreign_flow_radar)
                "profitAttrOwner": 100.0, # Dummy for DPR if needed elsewhere
                "fsDate": pd.to_datetime("2025-12-31"), # Dummy fsDate
                "opini": "WTP", # Dummy audit opinion
            }
        ])
        mock_stock_df = pd.DataFrame([
            {
                "StockCode": "BADCO",
                "Date": "2026-01-01",
                "Close": 100.0,
                "Previous": 100.0,
                "Value": 10000000000.0, # High turnover to pass min_turnover_rp
                "ForeignBuy": 0.0,
                "ForeignSell": 0.0,
                "NetForeignFlow": 0.0,
                "TradebleShares": 100_000_000, # Added to prevent KeyError in foreign_flow_radar
            }
        ])

        result_df = composite_alpha_ranking(stock=mock_stock_df, ratios=mock_ratios_df)

        # Based on the audit: ROE penalty: 15.0 + 10.0 = 25.0; PER penalty: 15.0
        # Total reduction: 40.0 from baseline.
        # If baseline is around 50 (neutral), then score should be 10.
        self.assertLessEqual(result_df.loc[0, 'AlphaScore'], 20.0, 
                             "Stock with severe negative ROE/PER should have a very low score")

    def test_neutral_stock_score(self):
        # Scenario: Neutral stock to verify baseline scoring

        mock_ratios_df = pd.DataFrame([
            {
                "code": "NEUTRAL",
                "roe": 15.0,  # Positive ROE
                "per": 10.0,  # Positive PER
                "deRatio": 0.5, # Low debt
                "PctFloat": 0.0, # Neutral foreign flow
                "profitAttrOwner": 100.0,
                "fsDate": pd.to_datetime("2025-12-31"), # Dummy fsDate
                "opini": "WTP", # Dummy audit opinion
            }
        ])
        mock_stock_df = pd.DataFrame([
            {
                "StockCode": "NEUTRAL",
                "Date": "2026-01-01",
                "Close": 100.0,
                "Previous": 100.0,
                "Value": 10000000000.0, # High turnover to pass min_turnover_rp
                "ForeignBuy": 0.0,
                "ForeignSell": 0.0,
                "NetForeignFlow": 0.0,
                "TradebleShares": 100_000_000, # Added to prevent KeyError in foreign_flow_radar
            }
        ])

        result_df = composite_alpha_ranking(stock=mock_stock_df, ratios=mock_ratios_df)
        # Baseline scores + ROE (15/30)*20 = 10.0 + PER (true)*15 = 15.0 - DER (0)*15 = 0
        # Total: 50 + 10 + 15 = 75
        self.assertGreaterEqual(result_df.loc[0, 'AlphaScore'], 70.0, 
                                "Neutral stock should have a reasonable score")

if __name__ == "__main__":
    unittest.main()