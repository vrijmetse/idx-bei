import os
import pytest
from idx.ingestion import (
    calculate_backfill_recommendations,
    detect_timeseries_gaps,
    get_idx_holidays,
)


def test_2025_holidays_present():
    holidays_2025 = get_idx_holidays(year=2025)
    assert len(holidays_2025) >= 15
    assert "2025-01-01" in holidays_2025
    assert "2025-12-25" in holidays_2025

    # Multi-year coverage test (2021-2024)
    for yr in [2021, 2022, 2023, 2024]:
        yr_holidays = get_idx_holidays(year=yr)
        assert len(yr_holidays) >= 15, f"Year {yr} should have at least 15 recognized exchange holidays"


def test_dynamic_tier_backfill_calculation(tmp_path):
    # Test calculate_backfill_recommendations returns dynamic trading_days_to_fetch
    recs = calculate_backfill_recommendations(current_date="2026-10-02")
    tiers = {t["tier"]: t for t in recs["tiers"]}

    # Tier 2 (2025) should dynamically calculate based on actual ingested dates
    tier_2 = tiers[2]
    assert "trading_days_to_fetch" in tier_2
    assert "coverage_pct" in tier_2
    # In our environment, 2025 has 236 ingested sessions (>= 95% coverage)
    # so trading_days_to_fetch must NOT be hardcoded to 246
    assert tier_2["trading_days_to_fetch"] < 246
    assert tier_2["priority"] in ["COMPLETED (100% UP TO DATE)", "OPTIMAL BASELINE AVAILABLE", "RECOMMENDED (BEST VALUE)"]
