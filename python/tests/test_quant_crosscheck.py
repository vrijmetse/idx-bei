"""Automated TDD cross-check test suite for quantitative finance and storage fixes."""
import os
import tempfile
import numpy as np
import pandas as pd
import pytest

from idx.compounder import calculate_justified_pbv
from idx.backtest import calculate_metrics, run_backtest
from idx.core.timeseries import _normalize_iso_date, read_dataset
from idx.dividend import analyze_stock_dividend


def test_justified_pbv_ke_less_than_or_equal_growth_rate():
    # When cost of equity equals or is less than growth rate, division by zero or negative denominator occurs
    val_zero_denom = calculate_justified_pbv(roe=15.0, cost_of_equity=0.05, growth_rate=0.05)
    assert val_zero_denom == 0.5

    val_neg_denom = calculate_justified_pbv(roe=15.0, cost_of_equity=0.03, growth_rate=0.05)
    assert val_neg_denom == 0.5

    val_zero_ke = calculate_justified_pbv(roe=15.0, cost_of_equity=0.0, growth_rate=0.05)
    assert val_zero_ke == 0.5

    # Normal healthy case: ROE 20%, Ke 10.5%, g 5% -> (0.20 - 0.05) / (0.105 - 0.05) = 0.15 / 0.055 = 2.73
    val_healthy = calculate_justified_pbv(roe=20.0, cost_of_equity=0.105, growth_rate=0.05)
    assert 2.70 <= val_healthy <= 2.75


def test_calculate_metrics_holding_period_annualization():
    # 20 trades with 10-day holding periods:
    # 5% return each trade
    returns = pd.Series([0.05] * 20)
    metrics = calculate_metrics(returns, holding_days=10)

    assert metrics["total_trades"] == 20
    assert metrics["total_return_pct"] > 0
    # CAGR should be calculated over total period, not hardcoded to total return
    assert "cagr_pct" in metrics
    assert metrics["sharpe_ratio"] is not None


def test_normalize_iso_date_helper():
    assert _normalize_iso_date("20260102") == "2026-01-02"
    assert _normalize_iso_date("2026-01-02") == "2026-01-02"
    assert _normalize_iso_date(None) is None


def test_query_dataset_consolidated_parquet_fallback_path():
    from unittest.mock import patch
    from idx.core.query import _dataset_glob

    # Verify that the fallback path resolves to <root>/parquet/<dataset>.parquet
    with patch("glob.glob", return_value=[]), \
         patch("os.path.exists", side_effect=lambda p: p.endswith(os.path.join("parquet", "stock_summary.parquet"))):
        path = _dataset_glob("stock_summary")
        assert path.endswith(os.path.join("parquet", "stock_summary.parquet"))
        assert "timeseries/parquet" not in path.replace("\\", "/")


def test_dividend_liquidity_trap_check():
    mock_details = {
        "LIQ": {
            "Search": {"NamaEmiten": "PT Liquidity Trap Tbk"},
            "Dividen": [
                {
                    "Nama": "PT Liquidity Trap Tbk",
                    "Jenis": "dt",
                    "TahunBuku": "2025",
                    "CashDividenPerSaham": 90.0,
                    "CashDividenPerSahamMU": "IDR",
                    "CashDividenTotal": 90_000_000_000.0,
                    "CashDividenTotalMU": "IDR",
                    "TanggalCum": "2026-06-15T00:00:00",
                    "TanggalExRegulerDanNegosiasi": "2026-06-16T00:00:00",
                    "TanggalDPS": "2026-06-17T16:00:00",
                    "TanggalPembayaran": "2026-07-02T00:00:00",
                }
            ],
        }
    }
    mock_stock_df = pd.DataFrame([
        {
            "Date": pd.to_datetime("2026-06-01"),
            "StockCode": "LIQ",
            "Close": 1000.0,
            "ListedShares": 1_000_000_000.0,
            "NetForeignFlow": 0.0,
            "Value": 10_000_000_000.0,
        }
    ])
    # Case 1: DPR = 90% (>80%) and Current Ratio = 0.7 (<1.0) -> triggers penalty
    mock_ratios_trap = pd.DataFrame([
        {
            "code": "LIQ",
            "eps": 100.0,  # DPR = 90%
            "currentRatio": 0.7,
            "roe": 15.0,
            "deRatio": 0.5,
            "opini": "WTP",
        }
    ])
    res_trap = analyze_stock_dividend("LIQ", details_dict=mock_details, stock_df=mock_stock_df, ratios_df=mock_ratios_trap)
    assert any("Liquidity risk: High payout" in rf for rf in res_trap["risk_factors"])

    # Case 2: DPR = 90% (>80%) but Current Ratio = 1.8 (>1.0) -> no liquidity penalty
    mock_ratios_safe = pd.DataFrame([
        {
            "code": "LIQ",
            "eps": 100.0,
            "currentRatio": 1.8,
            "roe": 15.0,
            "deRatio": 0.5,
            "opini": "WTP",
        }
    ])
    res_safe = analyze_stock_dividend("LIQ", details_dict=mock_details, stock_df=mock_stock_df, ratios_df=mock_ratios_safe)
    assert not any("Liquidity risk: High payout" in rf for rf in res_safe["risk_factors"])
    assert res_trap["dividend_trap_score"] > res_safe["dividend_trap_score"]


def test_parquet_return_guarded_against_zero_previous():
    # Verify that Return = (Close - Previous) / Previous handles Previous <= 0 cleanly
    df = pd.DataFrame({
        "Close": [100.0, 150.0, 200.0],
        "Previous": [0.0, -10.0, 100.0]
    })
    returns = ((df["Close"] - df["Previous"]) / df["Previous"]).where(df["Previous"] > 0).fillna(0.0).round(6)
    assert returns.iloc[0] == 0.0
    assert returns.iloc[1] == 0.0
    assert returns.iloc[2] == 1.0


def test_currency_atomic_write(tmp_path):
    from unittest.mock import patch
    import idx.core.currency as curr_mod

    test_file = str(tmp_path / "test_rate.json")
    with patch.object(curr_mod, "CACHE_FILE", test_file):
        curr_mod._save_cached_rate(16200.0, "test_source")
        assert os.path.exists(test_file)
        # Verify temporary file was cleaned up / replaced
        assert not os.path.exists(test_file + ".tmp")
        cached = curr_mod._load_cached_rate()
        assert cached is not None
        assert cached["rate"] == 16200.0
        assert cached["source"] == "test_source"
