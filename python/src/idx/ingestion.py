"""
Data Ingestion Status, Timeseries Gap Detection, and Backfill Recommendation Engine.
"""

from __future__ import annotations

import datetime
import glob
import os
from typing import Any

from idx.core import timeseries as ts
from idx.core.utils import DATA_DIR, get_logger, load_json
from idx.scrapers.historical import _trading_days

log = get_logger("idx.ingestion")

# Official IDX Public Holidays / Non-trading Weekdays (2021-2026)
KNOWN_IDX_HOLIDAYS_2021 = {
    "2021-01-01": "Tahun Baru 2021 Masehi",
    "2021-02-12": "Tahun Baru Imlek 2572",
    "2021-03-11": "Isra Mi'raj Nabi Muhammad SAW",
    "2021-03-14": "Hari Suci Nyepi Saka 1943",
    "2021-04-02": "Wafat Isa Al Masih",
    "2021-05-01": "Hari Buruh Internasional",
    "2021-05-12": "Cuti Bersama Idul Fitri 1442 H",
    "2021-05-13": "Kenaikan Isa Al Masih & Hari Raya Idul Fitri 1442 H",
    "2021-05-14": "Hari Raya Idul Fitri 1442 H",
    "2021-05-17": "Cuti Bersama Idul Fitri",
    "2021-05-18": "Cuti Bersama Idul Fitri",
    "2021-05-19": "Cuti Bersama Idul Fitri",
    "2021-05-26": "Hari Raya Waisak 2565 BE",
    "2021-06-01": "Hari Lahir Pancasila",
    "2021-07-20": "Hari Raya Idul Adha 1442 H",
    "2021-08-10": "Tahun Baru Islam 1443 H",
    "2021-08-11": "Libur Tahun Baru Islam (Penggeseran Libur)",
    "2021-08-17": "Hari Kemerdekaan RI Ke-76",
    "2021-10-19": "Maulid Nabi Muhammad SAW",
    "2021-10-20": "Libur Maulid Nabi Muhammad SAW (Penggeseran Libur)",
    "2021-12-24": "Cuti Bersama Hari Raya Natal",
    "2021-12-25": "Hari Raya Natal",
    "2021-12-31": "Libur Akhir Tahun BEI",
}

KNOWN_IDX_HOLIDAYS_2022 = {
    "2022-01-01": "Tahun Baru 2022 Masehi",
    "2022-02-01": "Tahun Baru Imlek 2573",
    "2022-02-28": "Isra Mi'raj Nabi Muhammad SAW",
    "2022-03-03": "Hari Suci Nyepi Saka 1944",
    "2022-04-15": "Wafat Isa Al Masih",
    "2022-04-29": "Cuti Bersama Idul Fitri 1443 H",
    "2022-05-01": "Hari Buruh Internasional",
    "2022-05-02": "Hari Raya Idul Fitri 1443 H",
    "2022-05-03": "Hari Raya Idul Fitri 1443 H",
    "2022-05-04": "Cuti Bersama Idul Fitri",
    "2022-05-05": "Cuti Bersama Idul Fitri",
    "2022-05-06": "Cuti Bersama Idul Fitri",
    "2022-05-16": "Hari Raya Waisak 2566 BE",
    "2022-05-26": "Kenaikan Isa Al Masih",
    "2022-06-01": "Hari Lahir Pancasila",
    "2022-07-09": "Hari Raya Idul Adha 1443 H",
    "2022-07-30": "Tahun Baru Islam 1444 H",
    "2022-08-17": "Hari Kemerdekaan RI Ke-77",
    "2022-10-08": "Maulid Nabi Muhammad SAW",
    "2022-12-25": "Hari Raya Natal",
    "2022-12-30": "Libur Akhir Tahun BEI",
}

KNOWN_IDX_HOLIDAYS_2023 = {
    "2023-01-01": "Tahun Baru 2023 Masehi",
    "2023-01-22": "Tahun Baru Imlek 2574",
    "2023-01-23": "Cuti Bersama Tahun Baru Imlek",
    "2023-02-18": "Isra Mi'raj Nabi Muhammad SAW",
    "2023-03-22": "Hari Suci Nyepi Saka 1945",
    "2023-03-23": "Cuti Bersama Hari Suci Nyepi",
    "2023-04-07": "Wafat Isa Al Masih",
    "2023-04-19": "Cuti Bersama Idul Fitri 1444 H",
    "2023-04-20": "Cuti Bersama Idul Fitri 1444 H",
    "2023-04-21": "Cuti Bersama Idul Fitri 1444 H",
    "2023-04-22": "Hari Raya Idul Fitri 1444 H",
    "2023-04-23": "Hari Raya Idul Fitri 1444 H",
    "2023-04-24": "Cuti Bersama Idul Fitri 1444 H",
    "2023-04-25": "Cuti Bersama Idul Fitri 1444 H",
    "2023-05-01": "Hari Buruh Internasional",
    "2023-05-18": "Kenaikan Isa Al Masih",
    "2023-06-01": "Hari Lahir Pancasila",
    "2023-06-02": "Cuti Bersama Hari Raya Waisak",
    "2023-06-04": "Hari Raya Waisak 2567 BE",
    "2023-06-28": "Cuti Bersama Idul Adha 1444 H",
    "2023-06-29": "Hari Raya Idul Adha 1444 H",
    "2023-06-30": "Cuti Bersama Idul Adha",
    "2023-07-19": "Tahun Baru Islam 1445 H",
    "2023-08-17": "Hari Kemerdekaan RI Ke-78",
    "2023-09-28": "Maulid Nabi Muhammad SAW",
    "2023-12-25": "Hari Raya Natal",
    "2023-12-26": "Cuti Bersama Hari Raya Natal",
    "2023-12-29": "Hari Libur Bursa Efek Indonesia",
}

KNOWN_IDX_HOLIDAYS_2024 = {
    "2024-01-01": "Tahun Baru 2024 Masehi",
    "2024-02-08": "Isra Mi'raj Nabi Muhammad SAW",
    "2024-02-09": "Cuti Bersama Tahun Baru Imlek 2575 Kongzili",
    "2024-02-14": "Pemilihan Umum 2024",
    "2024-03-11": "Hari Suci Nyepi Tahun Baru Saka 1946",
    "2024-03-12": "Cuti Bersama Hari Suci Nyepi",
    "2024-03-29": "Wafat Isa Al Masih",
    "2024-03-31": "Hari Paskah",
    "2024-04-08": "Cuti Bersama Idul Fitri 1445 H",
    "2024-04-09": "Cuti Bersama Idul Fitri 1445 H",
    "2024-04-10": "Hari Raya Idul Fitri 1445 H",
    "2024-04-11": "Hari Raya Idul Fitri 1445 H",
    "2024-04-12": "Cuti Bersama Idul Fitri 1445 H",
    "2024-04-15": "Cuti Bersama Idul Fitri 1445 H",
    "2024-05-01": "Hari Buruh Internasional",
    "2024-05-09": "Kenaikan Isa Al Masih",
    "2024-05-10": "Cuti Bersama Kenaikan Isa Al Masih",
    "2024-05-23": "Hari Raya Waisak 2568 BE",
    "2024-05-24": "Cuti Bersama Hari Raya Waisak",
    "2024-06-01": "Hari Lahir Pancasila",
    "2024-06-17": "Hari Raya Idul Adha 1445 H",
    "2024-06-18": "Cuti Bersama Idul Adha",
    "2024-07-07": "Tahun Baru Islam 1446 H",
    "2024-08-17": "Hari Kemerdekaan RI Ke-79",
    "2024-09-16": "Maulid Nabi Muhammad SAW",
    "2024-11-27": "Libur Pilkada Serentak 2024",
    "2024-12-25": "Hari Raya Natal",
    "2024-12-26": "Cuti Bersama Hari Raya Natal",
    "2024-12-31": "Libur Akhir Tahun BEI",
}

# Official IDX Public Holidays / Non-trading Weekdays
KNOWN_IDX_HOLIDAYS_2025 = {
    "2025-01-01": "Tahun Baru 2025 Masehi",
    "2025-01-27": "Isra Mi'raj Nabi Muhammad SAW",
    "2025-01-28": "Cuti Bersama Tahun Baru Imlek 2576",
    "2025-01-29": "Tahun Baru Imlek 2576 Kongzili",
    "2025-03-28": "Cuti Bersama Hari Suci Nyepi",
    "2025-03-29": "Hari Suci Nyepi Saka 1947",
    "2025-03-31": "Hari Raya Idul Fitri 1446 H",
    "2025-04-01": "Hari Raya Idul Fitri 1446 H",
    "2025-04-02": "Cuti Bersama Hari Raya Idul Fitri 1446 H",
    "2025-04-03": "Cuti Bersama Hari Raya Idul Fitri 1446 H",
    "2025-04-04": "Cuti Bersama Hari Raya Idul Fitri 1446 H",
    "2025-04-07": "Cuti Bersama Hari Raya Idul Fitri 1446 H",
    "2025-04-18": "Wafat Isa Al Masih (Good Friday)",
    "2025-05-01": "Hari Buruh Internasional",
    "2025-05-12": "Hari Raya Waisak 2569 BE",
    "2025-05-13": "Cuti Bersama Hari Raya Waisak",
    "2025-05-29": "Kenaikan Isa Al Masih",
    "2025-05-30": "Cuti Bersama Kenaikan Isa Al Masih",
    "2025-06-01": "Hari Lahir Pancasila",
    "2025-06-06": "Hari Raya Idul Adha 1446 H",
    "2025-06-09": "Cuti Bersama Hari Raya Idul Adha",
    "2025-06-27": "Tahun Baru Islam 1447 H",
    "2025-08-17": "Hari Kemerdekaan RI Ke-80",
    "2025-08-18": "Cuti Bersama Hari Kemerdekaan RI",
    "2025-09-05": "Maulid Nabi Muhammad SAW",
    "2025-12-25": "Hari Raya Natal",
    "2025-12-26": "Cuti Bersama Hari Raya Natal",
    "2025-12-31": "Libur Akhir Tahun Bursa Efek Indonesia",
}

# Official IDX Public Holidays / Non-trading Weekdays for 2026
KNOWN_IDX_HOLIDAYS_2026 = {
    "2026-01-01": "Tahun Baru 2026 Masehi",
    "2026-01-16": "Isra Mi'raj Nabi Muhammad SAW",
    "2026-02-16": "Cuti Bersama Tahun Baru Imlek 2577",
    "2026-02-17": "Tahun Baru Imlek 2577 Kongzili",
    "2026-03-18": "Cuti Bersama Hari Suci Nyepi",
    "2026-03-19": "Hari Suci Nyepi Tahun Baru Saka 1948",
    "2026-03-20": "Cuti Bersama Hari Raya Idul Fitri 1447 H",
    "2026-03-23": "Hari Raya Idul Fitri 1447 H",
    "2026-03-24": "Hari Raya Idul Fitri 1447 H",
    "2026-04-03": "Wafat Isa Al Masih (Good Friday)",
    "2026-05-01": "Hari Buruh Internasional",
    "2026-05-14": "Kenaikan Isa Al Masih",
    "2026-05-15": "Cuti Bersama Kenaikan Isa Al Masih",
    "2026-05-27": "Cuti Bersama Hari Raya Idul Adha 1447 H",
    "2026-05-28": "Hari Raya Idul Adha 1447 H",
    "2026-06-01": "Hari Lahir Pancasila",
    "2026-06-16": "Tahun Baru Islam 1448 H",
    "2026-08-17": "Hari Kemerdekaan RI Ke-81",
    "2026-08-25": "Maulid Nabi Muhammad SAW (12 Rabi'ul Awwal 1448 H)",
    "2026-12-24": "Cuti Bersama Hari Raya Natal",
    "2026-12-25": "Hari Raya Natal",
}


def get_idx_holidays(year: int | None = None, base_dir: str | None = None) -> dict[str, str]:
    """Retrieves IDX public holidays and non-trading days with local cache support.

    Merges static 2021-2026 holiday calendars with any custom or cached entries in data/idx_holidays.json.
    """
    root = base_dir or DATA_DIR
    holidays = dict(KNOWN_IDX_HOLIDAYS_2021)
    holidays.update(KNOWN_IDX_HOLIDAYS_2022)
    holidays.update(KNOWN_IDX_HOLIDAYS_2023)
    holidays.update(KNOWN_IDX_HOLIDAYS_2024)
    holidays.update(KNOWN_IDX_HOLIDAYS_2025)
    holidays.update(KNOWN_IDX_HOLIDAYS_2026)
    cache_path = os.path.join(root, "idx_holidays.json")
    if os.path.exists(cache_path):
        try:
            cached = load_json(cache_path)
            if isinstance(cached, dict):
                holidays.update(cached)
        except Exception as e:
            log.warning("Failed to load custom holiday cache %s: %s", cache_path, e)

    if year is not None:
        prefix = f"{year:04d}-"
        return {d: name for d, name in holidays.items() if d.startswith(prefix)}
    return holidays


def _file_info(path: str) -> dict[str, Any]:
    """Helper to get file size and last modified time."""
    if not os.path.exists(path):
        return {"exists": False, "size_bytes": 0, "size_mb": 0.0, "modified_iso": None}
    stat = os.stat(path)
    return {
        "exists": True,
        "size_bytes": stat.st_size,
        "size_mb": round(stat.st_size / (1024 * 1024), 2),
        "modified_iso": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(),
    }


def get_dataset_inventory(base_dir: str | None = None) -> dict[str, Any]:
    """Inspects all local storage partitions, Parquet exports, and snapshots.

    Returns:
        Structured dictionary of dataset statistics.
    """
    root = base_dir or DATA_DIR
    ts_root = os.path.join(root, "timeseries")
    parquet_root = os.path.join(root, "parquet")

    inventory: dict[str, Any] = {
        "timeseries": {},
        "parquet_exports": {},
        "fundamental_snapshots": {},
        "ksei_drift": {},
        "system": {},
    }

    # 1. Timeseries Partitioned Datasets
    for ds in ts.DATASETS:
        dates_map = ts.existing_dates(ds, base_dir=ts_root)
        sorted_dates = sorted(dates_map.keys())

        # Calculate partition files size
        ds_dir = os.path.join(ts_root, ds)
        part_files = glob.glob(os.path.join(ds_dir, "date=*.parquet"))
        compacted_files = glob.glob(os.path.join(ds_dir, "year=*", "month=*.parquet"))
        total_size = sum(
            os.path.getsize(f) for f in part_files + compacted_files if os.path.exists(f)
        )

        inventory["timeseries"][ds] = {
            "total_dates": len(sorted_dates),
            "start_date": sorted_dates[0] if sorted_dates else None,
            "end_date": sorted_dates[-1] if sorted_dates else None,
            "daily_partitions_count": len(part_files),
            "compacted_partitions_count": len(compacted_files),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
        }

    # 2. Consolidated Parquet Datasets
    for ds in [
        "stock_summary",
        "broker_summary",
        "index_summary",
        "financial_ratios",
        "corporate_actions",
    ]:
        p_path = os.path.join(parquet_root, f"{ds}.parquet")
        finfo = _file_info(p_path)
        row_count = 0
        if finfo["exists"]:
            try:
                import pyarrow.parquet as pq

                meta = pq.read_metadata(p_path)
                row_count = meta.num_rows
            except Exception:
                row_count = 0

        inventory["parquet_exports"][ds] = {
            "exists": finfo["exists"],
            "row_count": row_count,
            "size_mb": finfo["size_mb"],
            "modified_iso": finfo["modified_iso"],
        }

    # 3. Fundamental & Governance Snapshots
    all_comp_file = os.path.join(root, "allCompanies.json")
    comp_details_file = os.path.join(root, "companyDetailsByKodeEmiten.json")
    fin_ratio_file = os.path.join(root, "financial_ratio.json")
    corp_act_file = os.path.join(root, "corporateActions.json")
    broker_file = os.path.join(root, "brokerSearch.json")

    total_listed = 0
    if os.path.exists(all_comp_file):
        try:
            data = load_json(all_comp_file)
            total_listed = len(data) if isinstance(data, list) else len(data.get("data", []))
        except Exception:
            pass

    detailed_profiles = 0
    if os.path.exists(comp_details_file):
        try:
            d_data = load_json(comp_details_file)
            detailed_profiles = len(d_data) if isinstance(d_data, dict) else 0
        except Exception:
            pass

    inventory["fundamental_snapshots"] = {
        "total_listed_companies": total_listed,
        "detailed_profiles_scraped": detailed_profiles,
        "profile_coverage_pct": (
            round((detailed_profiles / total_listed * 100), 1) if total_listed else 0.0
        ),
        "financial_ratios": _file_info(fin_ratio_file),
        "corporate_actions": _file_info(corp_act_file),
        "broker_directory": _file_info(broker_file),
    }

    # 4. KSEI 1%+ Shareholder Drift & Ownership
    ksei_files = glob.glob(os.path.join(root, "*ownership*.csv"))
    ksei_meta = []
    for kf in sorted(ksei_files):
        ksei_meta.append({"file": os.path.basename(kf), **_file_info(kf)})
    inventory["ksei_drift"] = {
        "files_count": len(ksei_files),
        "files": ksei_meta,
    }

    # 5. Currency & Rates
    usd_file = os.path.join(root, "usd_idr_rate.json")
    rate_info = {"rate": 16200.0, "last_updated": None}
    if os.path.exists(usd_file):
        try:
            rdata = load_json(usd_file)
            rate_info["rate"] = rdata.get("rate", 16200.0)
            rate_info["last_updated"] = rdata.get("last_updated")
        except Exception:
            pass
    inventory["system"]["usd_idr"] = rate_info

    return inventory


def detect_timeseries_gaps(
    dataset: str = "stock_summary",
    start_date: str = "2026-01-01",
    end_date: str | None = None,
    base_dir: str | None = None,
) -> dict[str, Any]:
    """Detects missing dates in the timeseries against expected weekday trading sessions.

    Separates official Indonesian holidays from true missing trading days.
    """
    if end_date is None:
        end_date = datetime.date.today().strftime("%Y-%m-%d")

    ts_root = os.path.join(base_dir or DATA_DIR, "timeseries")
    existing = ts.existing_dates(dataset, base_dir=ts_root)

    expected_weekdays = [d.strftime("%Y-%m-%d") for d in _trading_days(start_date, end_date)]
    all_missing = [d for d in expected_weekdays if d not in existing]

    holidays_map = get_idx_holidays(base_dir=base_dir)
    holidays = []
    true_missing = []

    for d in all_missing:
        if d in holidays_map:
            holidays.append({"date": d, "holiday_name": holidays_map[d]})
        else:
            true_missing.append(d)

    total_weekdays = len(expected_weekdays)
    ingested_days = len(expected_weekdays) - len(all_missing)
    expected_active_trading_days = total_weekdays - len(holidays)
    coverage_pct = (
        round((ingested_days / expected_active_trading_days * 100.0), 1)
        if expected_active_trading_days > 0
        else 100.0
    )

    return {
        "dataset": dataset,
        "start_date": start_date,
        "end_date": end_date,
        "total_calendar_weekdays": total_weekdays,
        "ingested_days": ingested_days,
        "official_holidays_count": len(holidays),
        "official_holidays": holidays,
        "true_missing_trading_days_count": len(true_missing),
        "true_missing_trading_days": true_missing,
        "coverage_percentage": min(coverage_pct, 100.0),
    }


def calculate_backfill_recommendations(
    base_dir: str | None = None,
    current_date: str | None = None,
) -> dict[str, Any]:
    """Generates rigorous quantitative recommendations on how much historical data to backfill.

    Evaluates:
    - Tier 1: Immediate Gap Repair & Daily Ingestion (late August to current date)
    - Tier 2: 1-Year Baseline (2025-01-01 to 2025-12-31) -> ~248 trading days
    - Tier 3: 3-Year Multi-Cycle (2023-01-01 to 2024-12-31) -> ~496 trading days
    - Tier 4: 5-Year Deep Macro History (2021-01-01 to 2022-12-31) -> ~500 trading days
    """
    if current_date is None:
        current_date = datetime.date.today().strftime("%Y-%m-%d")

    # Inspect current gaps in 2026
    gap_info = detect_timeseries_gaps(
        dataset="stock_summary",
        start_date="2026-01-01",
        end_date=current_date,
        base_dir=base_dir,
    )

    missing_recent = gap_info["true_missing_trading_days"]
    has_gaps = len(missing_recent) > 0
    coverage_2026 = gap_info["coverage_percentage"]

    # Inspect historical tiers dynamically against existing partition dates
    gap_2025 = detect_timeseries_gaps(
        dataset="stock_summary",
        start_date="2025-01-01",
        end_date="2025-12-31",
        base_dir=base_dir,
    )
    missing_2025 = gap_2025["true_missing_trading_days"]
    t2_missing_count = len(missing_2025)
    t2_coverage = gap_2025["coverage_percentage"]
    t2_completed = t2_missing_count == 0

    gap_t3 = detect_timeseries_gaps(
        dataset="stock_summary",
        start_date="2023-01-01",
        end_date="2024-12-31",
        base_dir=base_dir,
    )
    missing_t3 = gap_t3["true_missing_trading_days"]
    t3_missing_count = len(missing_t3)
    t3_coverage = gap_t3["coverage_percentage"]
    t3_completed = t3_missing_count == 0

    gap_t4 = detect_timeseries_gaps(
        dataset="stock_summary",
        start_date="2021-01-01",
        end_date="2022-12-31",
        base_dir=base_dir,
    )
    missing_t4 = gap_t4["true_missing_trading_days"]
    t4_missing_count = len(missing_t4)
    t4_coverage = gap_t4["coverage_percentage"]
    t4_completed = t4_missing_count == 0

    tiers = [
        {
            "tier": 1,
            "id": "tier_1_immediate_gap_repair",
            "name": "2026 YTD Gap Repair & Latest Market Close",
            "priority": "HIGH (CRITICAL)" if has_gaps else "COMPLETED (100% UP TO DATE)",
            "coverage_pct": coverage_2026,
            "description": (
                f"Fills {len(missing_recent)} un-ingested 2026 trading sessions."
                if has_gaps
                else "All 2026 weekday trading sessions are fully ingested with 0 gaps! Run daily ingestion at market close."
            ),
            "target_range": {
                "start": missing_recent[0] if has_gaps else current_date,
                "end": current_date,
            },
            "trading_days_to_fetch": len(missing_recent),
            "estimated_payload_mb": round(len(missing_recent) * 0.45, 1),
            "estimated_runtime_seconds_c8": max(5, int(len(missing_recent) * 1.5)),
            "unlocked_capabilities": [
                "Real-time Bandarmology broker dominance for recent sessions",
                "Accurate technical indicators (RSI-14, MACD, Bollinger Bands) up to latest close",
                "Current net foreign institutional flow alignment",
            ],
            "recommended_cli_commands": (
                [
                    f"uv run idx backfill --start {missing_recent[0].replace('-', '')} --end {current_date.replace('-', '')} --concurrency 4",
                    "uv run idx daily",
                ]
                if has_gaps
                else ["uv run idx daily"]
            ),
        },
        {
            "tier": 2,
            "id": "tier_2_one_year_baseline",
            "name": "1-Year Baseline Historical Backfill (2025 Full Year)",
            "priority": "COMPLETED (100% UP TO DATE)" if t2_completed else "RECOMMENDED (BEST VALUE)",
            "coverage_pct": t2_coverage,
            "description": (
                f"Full calendar year 2025 data is fully ingested ({gap_2025['ingested_days']} trading sessions, {t2_coverage}% coverage)."
                if t2_completed
                else f"Ingests full calendar year 2025 data ({t2_missing_count} sessions to fetch). This is the optimal quant baseline."
            ),
            "target_range": {
                "start": missing_2025[0] if not t2_completed and missing_2025 else "2025-01-02",
                "end": missing_2025[-1] if not t2_completed and missing_2025 else "2025-12-30",
            },
            "trading_days_to_fetch": 0 if t2_completed else t2_missing_count,
            "estimated_payload_mb": 0.0 if t2_completed else round(t2_missing_count * 0.45, 1),
            "estimated_runtime_seconds_c8": 0 if t2_completed else max(5, int(t2_missing_count * 1.5)),
            "unlocked_capabilities": [
                "200-day Simple & Exponential Moving Averages (SMA-200 / EMA-200)",
                "Full 52-week High/Low price channel breakouts",
                "12-month trailing foreign institutional accumulation cycles",
                "Authentic 1-year backtesting of Foreign Flow and Bandarmology strategies",
            ],
            "recommended_cli_commands": [
                "uv run idx backfill --start 20250101 --end 20251231 --concurrency 4",
                "uv run idx parquet",
                "uv run idx compact",
            ],
        },
        {
            "tier": 3,
            "id": "tier_3_three_year_multicycle",
            "name": "3-Year Multi-Cycle Strategy Simulator Dataset (2023–2024)",
            "priority": "COMPLETED (100% UP TO DATE)" if t3_completed else "HIGH VALUE FOR BACKTESTING",
            "coverage_pct": t3_coverage,
            "description": (
                f"2023–2024 dataset is fully ingested ({gap_t3['ingested_days']} trading sessions, {t3_coverage}% coverage)."
                if t3_completed
                else f"Extends history across 2023–2024 monetary tightening ({t3_missing_count} sessions to fetch)."
            ),
            "target_range": {
                "start": missing_t3[0] if not t3_completed and missing_t3 else "2023-01-02",
                "end": missing_t3[-1] if not t3_completed and missing_t3 else "2024-12-30",
            },
            "trading_days_to_fetch": 0 if t3_completed else t3_missing_count,
            "estimated_payload_mb": 0.0 if t3_completed else round(t3_missing_count * 0.45, 1),
            "estimated_runtime_seconds_c8": 0 if t3_completed else max(5, int(t3_missing_count * 1.5)),
            "unlocked_capabilities": [
                "Statistically rigorous Sharpe and Sortino ratios (>500 trades)",
                "Cross-regime validation: Bull (2023 H2), Sideways (2024 H1), and Volatility regimes",
                "Dividend Arbitrage multi-year seasonality: Pre-Cum exit vs Post-Ex rebuy performance",
                "Tycoon conglomerate power shifts and long-horizon accumulation arcs",
            ],
            "recommended_cli_commands": [
                "uv run idx backfill --start 20230101 --end 20241231 --concurrency 4",
                "uv run idx parquet",
                "uv run idx compact",
            ],
        },
        {
            "tier": 4,
            "id": "tier_4_five_year_macro",
            "name": "5-Year Deep Macro History (2021–2022)",
            "priority": "COMPLETED (100% UP TO DATE)" if t4_completed else "OPTIONAL / RESEARCH ONLY",
            "coverage_pct": t4_coverage,
            "description": (
                f"2021–2022 macro dataset is fully ingested ({gap_t4['ingested_days']} trading sessions, {t4_coverage}% coverage)."
                if t4_completed
                else f"Complete post-COVID economic recovery cycle ({t4_missing_count} sessions to fetch)."
            ),
            "target_range": {
                "start": missing_t4[0] if not t4_completed and missing_t4 else "2021-01-04",
                "end": missing_t4[-1] if not t4_completed and missing_t4 else "2022-12-30",
            },
            "trading_days_to_fetch": 0 if t4_completed else t4_missing_count,
            "estimated_payload_mb": 0.0 if t4_completed else round(t4_missing_count * 0.45, 1),
            "estimated_runtime_seconds_c8": 0 if t4_completed else max(5, int(t4_missing_count * 1.5)),
            "unlocked_capabilities": [
                "5-year dividend CAGR and dividend trap historical resilience",
                "Long-term UBO and conglomerate restructuring tracking",
                "Full post-pandemic recovery macro backtesting",
            ],
            "recommended_cli_commands": [
                "uv run idx backfill --start 20210101 --end 20221231 --concurrency 4",
                "uv run idx parquet",
                "uv run idx compact",
            ],
        },
    ]

    return {
        "as_of_date": current_date,
        "summary": {
            "current_status": (
                f"2026 YTD partially ingested ({len(missing_recent)} missing sessions)"
                if has_gaps
                else f"2026 YTD is 100% complete ({gap_info['ingested_days']} trading sessions ingested, 0 gaps)"
            ),
            "immediate_gaps_count": len(missing_recent),
            "immediate_gaps": missing_recent,
            "recommended_action": (
                "Backfill Tier 1 (immediate 2026 gaps) first, followed by Tier 2 (2025 1-Year Baseline) for 200-day moving averages and full backtesting power."
                if has_gaps
                else (
                    "2026 YTD and 2025 Baseline are fully ingested with 100% coverage! Historical dataset is ready for 200-day moving averages and full backtesting."
                    if t2_completed
                    else "2026 YTD has zero gaps! Proceed to Tier 2 (2025 1-Year Baseline) to unlock 200-day moving averages (SMA-200 / EMA-200) and full 52-week channels."
                )
            ),
        },
        "tiers": tiers,
    }


def get_full_ingestion_status(base_dir: str | None = None) -> dict[str, Any]:
    """Unified status payload combining inventory, gap detection, and backfill recommendations."""
    inventory = get_dataset_inventory(base_dir=base_dir)
    gaps = detect_timeseries_gaps(dataset="stock_summary", base_dir=base_dir)
    recommendations = calculate_backfill_recommendations(base_dir=base_dir)

    # Health score calculation (0 - 100)
    health_score = 100
    if gaps["true_missing_trading_days_count"] > 0:
        health_score -= min(30, gaps["true_missing_trading_days_count"] * 3)

    stock_ts = inventory["timeseries"].get("stock_summary", {})
    if stock_ts.get("total_dates", 0) < 200:
        health_score -= 15  # lacks 1-year history

    profile_pct = inventory["fundamental_snapshots"].get("profile_coverage_pct", 0)
    if profile_pct < 80.0:
        health_score -= 10

    return {
        "status": "healthy"
        if health_score >= 75
        else ("warning" if health_score >= 50 else "critical"),
        "health_score": max(0, health_score),
        "inventory": inventory,
        "gaps": gaps,
        "recommendations": recommendations,
        "generated_at": datetime.datetime.now().isoformat(),
    }


# Track active and recent background ingestion jobs
_INGESTION_JOBS: dict[str, dict[str, Any]] = {}


def get_job_status(job_id: str) -> dict[str, Any] | None:
    """Return status of a specific ingestion task."""
    return _INGESTION_JOBS.get(job_id)


def list_recent_jobs(limit: int = 10) -> list[dict[str, Any]]:
    """List recent ingestion background tasks."""
    return sorted(
        _INGESTION_JOBS.values(),
        key=lambda j: j.get("created_at", ""),
        reverse=True,
    )[:limit]


async def run_async_ingestion_job(
    job_id: str,
    job_type: str,
    params: dict[str, Any],
    broadcast_callback: Any | None = None,
) -> dict[str, Any]:
    """Runs a daily ingestion or backfill task asynchronously with status updates."""
    import asyncio

    job_record: dict[str, Any] = {
        "job_id": job_id,
        "type": job_type,
        "params": params,
        "status": "running",
        "progress_pct": 0,
        "message": "Starting ingestion task...",
        "created_at": datetime.datetime.now().isoformat(),
        "completed_at": None,
        "results": None,
    }
    _INGESTION_JOBS[job_id] = job_record

    async def _notify(progress: int, msg: str):
        job_record["progress_pct"] = progress
        job_record["message"] = msg
        if broadcast_callback:
            try:
                await broadcast_callback(
                    {
                        "type": "ingestion_progress",
                        "job_id": job_id,
                        "progress": progress,
                        "message": msg,
                    }
                )
            except Exception:
                pass

    try:
        await _notify(10, f"Initializing {job_type} task...")

        if job_type == "daily":
            from idx.pipelines.daily import ingest_daily

            await _notify(30, "Ingesting today's market-close sessions...")
            # Run blocking ingest_daily in threadpool
            date_arg = params.get("date")
            res = await asyncio.to_thread(ingest_daily, date=date_arg)
            await _notify(90, "Rebuilding consolidated Parquet datasets...")
            job_record["results"] = res

        elif job_type == "backfill":
            from idx.pipelines.parquet import export_all
            from idx.scrapers.historical import (
                async_backfill_broker_summary,
                async_backfill_index_summary,
                async_backfill_stock_summary,
            )

            start = params.get("start_date", "20260825")
            end = params.get("end_date", datetime.date.today().strftime("%Y%m%d"))
            concurrency = int(params.get("concurrency", 4))

            await _notify(20, f"Backfilling stock summaries ({start} to {end})...")
            res_stock = await async_backfill_stock_summary(start, end, concurrency=concurrency)

            await _notify(50, f"Backfilling broker summaries ({start} to {end})...")
            res_broker = await async_backfill_broker_summary(start, end, concurrency=concurrency)

            await _notify(75, f"Backfilling index summaries ({start} to {end})...")
            res_index = await async_backfill_index_summary(start, end, concurrency=concurrency)

            await _notify(85, "Rebuilding consolidated Parquet datasets...")
            parquet_res = await asyncio.to_thread(export_all)

            job_record["results"] = {
                "stock_summary": res_stock,
                "broker_summary": res_broker,
                "index_summary": res_index,
                "parquet_export": parquet_res,
            }

        else:
            raise ValueError(f"Unknown job type: {job_type}")

        # Rigorous completion evaluation: never mask scraper errors as success
        job_record["completed_at"] = datetime.datetime.now().isoformat()
        job_record["progress_pct"] = 100

        if job_type == "daily":
            res = job_record.get("results", {})
            failed_keys = [
                k
                for k, v in res.items()
                if (isinstance(v, dict) and v.get("status") == "error") or v == "error"
            ]
            if len(failed_keys) >= 3:
                job_record["status"] = "failed"
                job_record["message"] = "Daily ingestion failed: IDX exchange data unavailable or blocked by rate limit (HTTP 429)."
            elif len(failed_keys) > 0:
                job_record["status"] = "completed_with_warnings"
                job_record["message"] = f"Daily ingestion finished with warnings: {', '.join(failed_keys)} failed."
            else:
                job_record["status"] = "completed"
                job_record["message"] = "Daily market-close ingestion completed successfully."

        elif job_type == "backfill":
            res_s = job_record["results"].get("stock_summary", {})
            res_b = job_record["results"].get("broker_summary", {})
            res_i = job_record["results"].get("index_summary", {})

            total_fetched = res_s.get("dates_fetched", 0) + res_b.get("dates_fetched", 0) + res_i.get("dates_fetched", 0)
            total_skipped = res_s.get("dates_skipped", 0) + res_b.get("dates_skipped", 0) + res_i.get("dates_skipped", 0)
            total_errors = res_s.get("errors", 0) + res_b.get("errors", 0) + res_i.get("errors", 0)

            if total_errors > 0 and total_fetched == 0:
                job_record["status"] = "failed"
                job_record["message"] = (
                    f"Backfill failed: {total_errors} sessions blocked by rate limit (HTTP 429) "
                    "or trading summary not published by IDX yet."
                )
            elif total_errors > 0:
                job_record["status"] = "completed_with_warnings"
                job_record["message"] = (
                    f"Backfill finished with {total_errors} errors "
                    f"({total_fetched} dates fetched, {total_skipped} skipped)."
                )
            else:
                job_record["status"] = "completed"
                job_record["message"] = f"Backfill completed successfully ({total_fetched} dates fetched, {total_skipped} skipped)."

        if broadcast_callback:
            try:
                event_type = (
                    "ingestion_error"
                    if job_record["status"] == "failed"
                    else "ingestion_warning"
                    if job_record["status"] == "completed_with_warnings"
                    else "ingestion_completed"
                )
                payload = {
                    "type": event_type,
                    "job_id": job_id,
                    "status": job_record["status"],
                    "message": job_record["message"],
                    "results": job_record.get("results"),
                }
                if job_record["status"] == "failed":
                    payload["error"] = job_record["message"]
                await broadcast_callback(payload)
            except Exception:
                pass

    except Exception as exc:
        log.error("Ingestion job %s failed: %s", job_id, exc)
        job_record["status"] = "failed"
        job_record["message"] = str(exc)
        job_record["completed_at"] = datetime.datetime.now().isoformat()
        if broadcast_callback:
            try:
                await broadcast_callback(
                    {
                        "type": "ingestion_error",
                        "job_id": job_id,
                        "error": str(exc),
                    }
                )
            except Exception:
                pass

    return job_record
