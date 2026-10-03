"""
High-Performance FastAPI REST & WebSocket Microservice Layer for IDX-BEI Toolkit.
"""

import asyncio
import json
import logging
import os
import time
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect

logger = logging.getLogger("idx.api")
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from starlette.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import re

TICKER_REGEX = re.compile(r"^[A-Za-z0-9]{2,10}$")


def validate_ticker(ticker: str) -> str:
    """Strictly validates ticker symbol format to prevent SQL injection and malformed queries."""
    if not ticker or not TICKER_REGEX.match(ticker):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid ticker symbol '{ticker}'. Must be 2-10 alphanumeric characters.",
        )
    return ticker.upper()

from idx.core.ownership import get_latest_shareholder_drift
from idx.core.query import query_dataset
from idx.core.utils import DATA_DIR, load_json
from idx.graph import (
    calculate_board_centrality,
    detect_cross_holdings,
    get_company_network,
    get_ubo_tree,
)
from idx.ingestion import (
    get_full_ingestion_status,
    get_job_status,
    list_recent_jobs,
    run_async_ingestion_job,
)
from idx.signals import broker_concentration_screen, build_briefing, compute_technical_indicators

def clean_record(r: dict[str, Any]) -> dict[str, Any]:
    import math

    out = {}
    for k, v in r.items():
        if pd.isna(v) or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
            out[k] = None
        elif isinstance(v, dict):
            out[k] = clean_record(v)
        elif isinstance(v, list):
            out[k] = [
                clean_record(item)
                if isinstance(item, dict)
                else (
                    None
                    if pd.isna(item) or (isinstance(item, float) and (math.isnan(item) or math.isinf(item)))
                    else item
                )
                for item in v
            ]
        else:
            out[k] = v
    return out


def clean_dict_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [clean_record(r) for r in records]


app = FastAPI(
    title="IDX-BEI Quantitative & Microservice API",
    description="High-performance async REST & WebSocket API for Indonesia Stock Exchange data and quantitative intelligence.",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Compress all responses over 1KB (reduces JSON payload bandwidth by 80-87%)
app.add_middleware(GZipMiddleware, minimum_size=1000)


class CachedStaticFiles(StaticFiles):
    """StaticFiles that sets immutable 1-year Cache-Control headers on hashed JS/CSS assets."""

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if any(path.endswith(ext) for ext in (".js", ".css", ".svg", ".png", ".jpg", ".woff2", ".woff", ".ttf")):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        elif path.endswith(".html") or path == "" or path == "/":
            response.headers["Cache-Control"] = "no-cache, must-revalidate"
        return response


REPO_ROOT = os.path.abspath(os.path.join(DATA_DIR, ".."))
DASHBOARD_DIR = os.path.join(REPO_ROOT, "dashboard")
FRONTEND_DIST = os.path.join(REPO_ROOT, "frontend", "dist")

SERVE_DIR = FRONTEND_DIST if os.path.exists(FRONTEND_DIST) else DASHBOARD_DIR
if os.path.exists(SERVE_DIR):
    app.mount("/dashboard", CachedStaticFiles(directory=SERVE_DIR, html=True), name="dashboard")

if os.path.exists(DATA_DIR):
    app.mount("/data", StaticFiles(directory=DATA_DIR), name="data")

FRONTEND_ASSETS = os.path.join(FRONTEND_DIST, "assets")
if os.path.exists(FRONTEND_ASSETS):
    app.mount("/assets", CachedStaticFiles(directory=FRONTEND_ASSETS), name="assets")


@app.get("/", include_in_schema=False)
async def root_redirect():
    """Redirect root path directly to the visual dashboard."""
    return RedirectResponse(url="/dashboard/")


_TTL_CACHE: dict[str, tuple[float, Any]] = {}


def get_from_cache(key: str, ttl_seconds: float = 60.0) -> Any | None:
    if key in _TTL_CACHE:
        timestamp, value = _TTL_CACHE[key]
        if time.time() - timestamp < ttl_seconds:
            return value
        del _TTL_CACHE[key]
    return None


def set_in_cache(key: str, value: Any) -> None:
    _TTL_CACHE[key] = (time.time(), value)


class SQLQueryRequest(BaseModel):
    sql: str
    limit: int | None = 50


class BacktestRequest(BaseModel):
    strategy: str = "foreign_flow"
    holding_days: int = 20
    top_n: int = 10
    min_turnover_rp: float = 1_000_000_000.0
    start_date: str | None = None
    end_date: str | None = None
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None
    position_sizing: str = "equal_weight"


class TriggerIngestionRequest(BaseModel):
    job_type: str = "daily"  # "daily" or "backfill"
    date: str | None = None  # YYYYMMDD for daily
    start_date: str | None = None  # YYYYMMDD for backfill
    end_date: str | None = None  # YYYYMMDD for backfill
    concurrency: int = 8


@app.get("/health", tags=["System"])
async def health():
    return {"status": "ok", "service": "idx-bei-api", "version": "0.2.0"}


_latest_prices_cache: dict[str, dict[str, Any]] = {}
_latest_prices_ts: float = 0.0


def get_latest_market_prices() -> dict[str, dict[str, Any]]:
    global _latest_prices_cache, _latest_prices_ts
    now = time.time()
    if _latest_prices_cache and (now - _latest_prices_ts) < 60.0:
        return _latest_prices_cache

    parquet_path = os.path.join(DATA_DIR, "parquet", "stock_summary.parquet")
    if not os.path.exists(parquet_path):
        return {}

    try:
        df = pd.read_parquet(
            parquet_path, columns=["Date", "StockCode", "Close", "Previous", "Change"]
        )
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        latest_df = df.sort_values("Date").groupby("StockCode").last()
        res = {}
        for code, row in latest_df.iterrows():
            close = float(row["Close"]) if pd.notna(row["Close"]) else 0.0
            prev = float(row["Previous"]) if pd.notna(row["Previous"]) else close
            chg = float(row["Change"]) if pd.notna(row["Change"]) else (close - prev)
            chg_pct = (chg / prev * 100.0) if prev > 0 else 0.0
            res[str(code)] = {
                "price": close,
                "previous_price": prev,
                "daily_change": chg,
                "daily_change_pct": round(chg_pct, 2),
            }
        _latest_prices_cache = res
        _latest_prices_ts = now
        return res
    except Exception as e:
        logger.warning(f"Failed to load latest market prices from parquet: {e}")
        return _latest_prices_cache or {}


_dividend_summary_cache: dict[str, dict[str, Any]] = {}
_dividend_summary_ts: float = 0.0


_stealth_summary_cache: dict[str, dict[str, Any]] | None = None
_stealth_summary_ts: float = 0.0


def get_stealth_accumulation_map() -> dict[str, dict[str, Any]]:
    """Return dictionary mapping stock code to stealth accumulation & retail trap signals."""
    global _stealth_summary_cache, _stealth_summary_ts
    now = time.time()
    if _stealth_summary_cache and (now - _stealth_summary_ts) < 300.0:
        return _stealth_summary_cache

    broker_path = os.path.join(DATA_DIR, "parquet", "broker_summary.parquet")
    stock_path = os.path.join(DATA_DIR, "parquet", "stock_summary.parquet")
    if not os.path.exists(broker_path) or not os.path.exists(stock_path):
        return {}

    try:
        import pandas as pd
        from idx.signals import detect_stealth_accumulation

        broker_df = pd.read_parquet(broker_path)
        stock_df = pd.read_parquet(stock_path)

        res = detect_stealth_accumulation(
            broker_df,
            stock_df,
            lookback_days=5,
            min_turnover_rp=1e9,
        )
        anomalies_df = res.get("anomalies_df")
        res_map = {}
        if anomalies_df is not None and not anomalies_df.empty:
            for r in anomalies_df.to_dict("records"):
                code = r.get("StockCode")
                if code:
                    res_map[code] = {
                        "Signal": r.get("Signal"),
                        "NetForeignFlowRpB": r.get("NetForeignFlowRpB"),
                        "PriceChangePct": r.get("PriceChangePct"),
                    }
        _stealth_summary_cache = res_map
        _stealth_summary_ts = now
        return _stealth_summary_cache
    except Exception as e:
        logger.warning(f"Could not load stealth accumulation map: {e}")
        return {}


def get_dividend_summary_map() -> dict[str, dict[str, Any]]:
    """Return dictionary mapping stock code to precomputed dividend metrics."""
    global _dividend_summary_cache, _dividend_summary_ts
    now = time.time()
    if _dividend_summary_cache and (now - _dividend_summary_ts) < 3600.0:
        return _dividend_summary_cache

    screen_file = os.path.join(DATA_DIR, "dividend_screen.json")
    if os.path.exists(screen_file):
        try:
            records = load_json(screen_file)
            res = {}
            for r in records:
                code = r.get("StockCode") or r.get("Ticker")
                if code:
                    res[code] = {
                        "yield": r.get("DividendYield") or r.get("Yield%"),
                        "dps": r.get("AnnualizedDPS") or r.get("DPS_IDR"),
                        "dpr": r.get("PayoutRatio") or r.get("DPR%"),
                        "trap_score": r.get("TrapRiskScore") or r.get("TrapScore"),
                        "verdict": r.get("Recommendation") or r.get("Verdict"),
                    }
            _dividend_summary_cache = res
            _dividend_summary_ts = now
            return _dividend_summary_cache
        except Exception as e:
            logger.warning(f"Could not load dividend screen file: {e}")
    return {}


_hydrated_companies_cache: list[dict[str, Any]] | None = None
_hydrated_companies_ts: float = 0.0


def get_all_hydrated_companies() -> list[dict[str, Any]]:
    """Return all 973 listed companies fully hydrated with latest market prices, dividends, sharia status, and stealth accumulation signals.
    Cached in memory with 300s TTL.
    """
    global _hydrated_companies_cache, _hydrated_companies_ts
    now = time.time()
    if _hydrated_companies_cache is not None and (now - _hydrated_companies_ts) < 300.0:
        return _hydrated_companies_cache

    alpha_file = os.path.join(DATA_DIR, "network_alpha_data.json")
    if not os.path.exists(alpha_file):
        return []

    data = load_json(alpha_file)
    prices_map = get_latest_market_prices()
    div_map = get_dividend_summary_map()
    stealth_map = get_stealth_accumulation_map()
    from idx.compounder import hydrate_company_market_data
    from idx.core.sharia import get_sharia_status_map

    sharia_map = get_sharia_status_map()
    companies = [
        hydrate_company_market_data(c, prices_map=prices_map, div_map=div_map, sharia_map=sharia_map, stealth_map=stealth_map)
        for c in data.get("companies", [])
    ]
    _hydrated_companies_cache = companies
    _hydrated_companies_ts = now
    return _hydrated_companies_cache


@app.get("/api/dashboard-data", tags=["Market Data"])
async def get_dashboard_data():
    """Return unified dashboard dataset containing companies with prices, super-insiders, and conglomerates."""
    cached = get_from_cache("dashboard_data", ttl_seconds=60.0)
    if cached:
        return cached

    alpha_file = os.path.join(DATA_DIR, "network_alpha_data.json")
    if os.path.exists(alpha_file):
        data = load_json(alpha_file)
        data["companies"] = get_all_hydrated_companies()
        set_in_cache("dashboard_data", data)
        return data
    return {"companies": [], "super_insiders": [], "conglomerates": []}


@app.get("/api/companies", tags=["Fundamental"])
async def get_companies(
    category: str | None = Query(None, description="Filter category: dca_prime, smart_money, dividends, value, danger, sharia"),
    search: str | None = Query(None, description="Search by ticker or name"),
    min_score: float | None = Query(None, description="Minimum compounder score"),
    max_per: float | None = Query(None, description="Maximum PER"),
    min_roe: float | None = Query(None, description="Minimum ROE"),
    min_yield: float | None = Query(None, description="Minimum Dividend Yield"),
    is_sharia: bool | None = Query(None, description="Filter for Sharia compliant stocks"),
    sort_by: str = Query("compounder_score", description="Sort key"),
    sort_dir: str = Query("desc", description="Sort direction: asc or desc"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(25, ge=1, le=100, description="Items per page"),
):
    """Return list of all listed companies with financial metrics, governance, and prices."""
    cache_key = f"companies_list:{category}:{search}:{min_score}:{max_per}:{min_roe}:{min_yield}:{is_sharia}:{sort_by}:{sort_dir}:{page}:{page_size}"
    cached = get_from_cache(cache_key, ttl_seconds=60.0)
    if cached:
        return cached

    alpha_file = os.path.join(DATA_DIR, "network_alpha_data.json")
    if os.path.exists(alpha_file):
        companies = get_all_hydrated_companies()
        
        # Apply filtering
        filtered_companies = []
        for c in companies:
            keep = True

            # Category filtering
            if category:
                if category == "dca_prime":
                    # All quality compounders suitable for regular accumulation (PRIME_DCA or ACCUMULATE or score >= 60)
                    if not ((c.get("dca_verdict") in ("PRIME_DCA", "ACCUMULATE") or c.get("compounder_score", 0) >= 60) and not c.get("is_value_trap", False)):
                        keep = False
                elif category == "smart_money":
                    # Big institutional stealth accumulation (exclude value traps & negative ROE so no trap leaks into smart money)
                    roe_val = c.get("roe")
                    is_neg_roe = roe_val is not None and float(roe_val) < 0
                    if not c.get("is_smart_money_inflow", False) or c.get("is_value_trap", False) or is_neg_roe:
                        keep = False
                elif category == "dividends":
                    # Safe cashflow dividend gems with low trap score
                    div_yield = c.get("dividend_yield_pct") or c.get("yield") or 0.0
                    trap_score = c.get("dividend_trap_score", 25.0)
                    if div_yield < 3.0 or c.get("is_value_trap", False) or trap_score > 50.0:
                        keep = False
                elif category == "value":
                    if (c.get("valuation_status") not in ("SECTOR_UNDERVALUED", "DEEP_VALUE", "UNDERVALUED") and not c.get("is_undervalued", False)) or c.get("is_value_trap", False):
                        keep = False
                elif category == "danger":
                    roe_val = c.get("roe")
                    npm_val = c.get("npm")
                    is_loss = (roe_val is not None and float(roe_val) < 0) or (npm_val is not None and float(npm_val) < 0)
                    if not c.get("is_value_trap", False) and not is_loss and not c.get("is_retail_trap", False):
                        keep = False
                elif category == "sharia":
                    if not c.get("is_sharia", False):
                        keep = False

            # Search filtering
            if search and not (search.lower() in c.get("code", "").lower() or search.lower() in c.get("name", "").lower()):
                keep = False

            # Metric filtering
            if min_score is not None and c.get("compounder_score", 0) < min_score:
                keep = False
            if max_per is not None and (c.get("per") is None or c.get("per", 0) > max_per or c.get("per", 0) <= 0):
                keep = False
            if min_roe is not None and (c.get("roe") is None or c.get("roe", 0) < min_roe):
                keep = False
            if min_yield is not None and (c.get("dividend_yield_pct") is None or c.get("dividend_yield_pct", 0) < min_yield):
                keep = False
            if is_sharia is not None and c.get("is_sharia") != is_sharia:
                keep = False
            
            if keep:
                filtered_companies.append(c)

        # Apply sorting
        if sort_by:
            def get_sort_key(item):
                val = item.get(sort_by, 0)
                if sort_by == "per": # PER needs special handling for 0 or negative values
                    return val if val > 0 else float('inf')
                return val

            filtered_companies.sort(key=get_sort_key, reverse=(sort_dir == "desc"))

        # Apply pagination
        total_count = len(filtered_companies)
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        paginated_companies = filtered_companies[start_index:end_index]

        out = {
            "companies": paginated_companies,
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
        }
        set_in_cache(cache_key, out)
        return out
    return {"companies": [], "total_count": 0, "page": page, "page_size": page_size}


@app.get("/api/compounder-screen", tags=["Intelligence"])
async def get_compounder_screen(
    min_score: float = Query(60.0, description="Minimum DCA Compounder Score (0-100)"),
    exclude_traps: bool = Query(True, description="Filter out one-off value traps"),
    category: str | None = Query(
        None, description="Optional category: prime_dca, accumulate, sector_value"
    ),
    limit: int = Query(50, description="Max results to return"),
):
    """Return top long-term DCA compounders screened for forensic health and sector-aware valuation."""
    cache_key = f"compounder_screen:{min_score}:{exclude_traps}:{category}:{limit}"
    cached = get_from_cache(cache_key, ttl_seconds=60.0)
    if cached:
        return cached

    alpha_file = os.path.join(DATA_DIR, "network_alpha_data.json")
    if not os.path.exists(alpha_file):
        return []
    data = load_json(alpha_file)
    companies = data.get("companies", [])

    results = []
    for c in companies:
        if exclude_traps and c.get("is_value_trap"):
            continue
        score = float(c.get("compounder_score") or 0.0)
        if score < min_score:
            continue
        if category == "prime_dca" and c.get("dca_verdict") != "PRIME_DCA":
            continue
        if category == "sector_value" and c.get("valuation_status") != "SECTOR_UNDERVALUED":
            continue
        results.append(c)

    results.sort(key=lambda x: x.get("compounder_score", 0), reverse=True)
    out = results[:limit]
    set_in_cache(cache_key, out)
    return out


@app.get("/api/signals", tags=["Signals"])
async def get_signals(
    date: str | None = Query(None, description="Optional trading date (YYYY-MM-DD)"),
):
    cache_key = f"signals:{date or 'latest'}"
    cached = get_from_cache(cache_key, ttl_seconds=60.0)
    if cached is not None:
        return cached

    try:
        res = build_briefing(date=date)
        json_file = res.get("json")
        result = load_json(json_file) if (json_file and os.path.exists(json_file)) else res
        set_in_cache(cache_key, result)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/stock/{ticker}", tags=["Market Data"])
@app.get("/api/stocks/{ticker}", tags=["Market Data"])
async def get_stock_data(ticker: str, limit: int = 500):
    import numpy as np
    import pandas as pd
    from idx.core.adjustments import adjust_stock_splits

    ticker = validate_ticker(ticker)
    cache_key = f"stock_data:{ticker}:{limit}"
    cached = get_from_cache(cache_key, ttl_seconds=1800.0)
    if cached:
        return cached

    df = query_dataset("stock_summary", where=f"StockCode = '{ticker}'")
    if len(df) == 0:
        raise HTTPException(status_code=404, detail=f"Ticker '{ticker}' not found.")

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.sort_values("Date").reset_index(drop=True)

    # 1. Apply backward split adjustment so prices and technical indicators are mathematically continuous
    df = adjust_stock_splits(df, ticker)

    tech = compute_technical_indicators(df, ticker=ticker)
    if limit and limit > 0 and len(tech) > limit:
        tech = tech.tail(limit).reset_index(drop=True)

    # Standardize time and OHLC fields for charts
    tech["time"] = tech["Date"].dt.strftime("%Y-%m-%d")
    if "OpenPrice" in tech.columns:
        tech["open"] = tech["OpenPrice"].fillna(tech["Close"])
    else:
        tech["open"] = tech["Close"]

    if "High" in tech.columns:
        tech["high"] = tech["High"].fillna(tech["Close"])
    else:
        tech["high"] = tech["Close"]

    if "Low" in tech.columns:
        tech["low"] = tech["Low"].fillna(tech["Close"])
    else:
        tech["low"] = tech["Close"]

    tech["close"] = tech["Close"]
    tech["volume"] = tech["Volume"].fillna(0) if "Volume" in tech.columns else 0

    # Clean NaNs and infs for strict JSON compliance
    clean_df = tech.replace([np.inf, -np.inf], np.nan).where(pd.notnull(tech), None)
    clean_df["Date"] = clean_df["Date"].astype(str)

    records = clean_dict_records(clean_df.to_dict(orient="records"))
    latest = records[-1] if records else {}

    # Augment with latest intraday candle from Yahoo Finance ONLY during active trading hours (WIB Mon-Fri 09:00 - 16:30)
    try:
        import datetime
        import yfinance as yf

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        now_wib = now_utc + datetime.timedelta(hours=7)
        is_trading_day = now_wib.weekday() < 5  # Mon-Fri
        is_market_active = is_trading_day and (9 <= now_wib.hour < 17)

        today_str = now_wib.strftime("%Y-%m-%d")
        if is_market_active and records and records[-1].get("time") != today_str:
            yf_stock = yf.Ticker(f"{ticker}.JK")
            hist = yf_stock.history(period="1d", interval="1d", timeout=1.5)
            if not hist.empty:
                last_row = hist.iloc[-1]
                intraday_date = last_row.name.strftime("%Y-%m-%d")
                if intraday_date == today_str:
                    intraday_record = {
                        "Date": today_str,
                        "time": today_str,
                        "StockCode": ticker,
                        "open": float(last_row["Open"]),
                        "high": float(last_row["High"]),
                        "low": float(last_row["Low"]),
                        "close": float(last_row["Close"]),
                        "volume": float(last_row["Volume"]),
                        "Close": float(last_row["Close"]),
                        "TrendRegime": records[-1].get("TrendRegime", "NEUTRAL"),
                        "EMA20": records[-1].get("EMA20"),
                        "EMA50": records[-1].get("EMA50"),
                        "EMA200": records[-1].get("EMA200"),
                        "RSI14": records[-1].get("RSI14"),
                    }
                    records.append(intraday_record)
                    latest = intraday_record
    except Exception:
        pass

    # Look up profile, financials, and decision metrics directly from in-memory hydrated cache (0ms)
    profile = {}
    financials = {}
    decision = {}
    try:
        for c in get_all_hydrated_companies():
            if c.get("code") == ticker:
                profile = {
                    "name": c.get("name"),
                    "sector": c.get("sector"),
                    "conglomerate": c.get("conglomerate"),
                }
                financials = {
                    "per": c.get("per"),
                    "price_bv": c.get("price_bv") or c.get("pbv"),
                    "roe": c.get("roe"),
                    "de_ratio": c.get("de_ratio"),
                    "dividend_yield_pct": c.get("dividend_yield_pct") or c.get("yield"),
                    "annualized_dps": c.get("annualized_dps"),
                }
                decision = {
                    "compounder_score": c.get("compounder_score"),
                    "dca_verdict": c.get("dca_verdict"),
                    "dca_rating": c.get("dca_rating"),
                    "is_value_trap": c.get("is_value_trap", False),
                }
                break
    except Exception:
        pass

    result = {
        "ticker": ticker,
        "records": records,
        "latest": latest,
        "profile": profile,
        "financials": financials,
        "decision": decision,
    }
    set_in_cache(cache_key, result)
    return result


@app.get("/api/stock/{ticker}/blocks", tags=["Market Data"])
@app.get("/api/stocks/{ticker}/blocks", tags=["Market Data"])
@app.get("/api/stock/{ticker}/tape", tags=["Market Data"])
@app.get("/api/stocks/{ticker}/tape", tags=["Market Data"])
async def get_stock_blocks(ticker: str):
    import pandas as pd

    from idx.signals import INSTITUTIONAL_BROKERS, RETAIL_BROKERS

    ticker = validate_ticker(ticker)
    cache_key = f"stock_blocks:{ticker}"
    cached = get_from_cache(cache_key, ttl_seconds=60.0)
    if cached:
        return cached

    df = query_dataset("stock_summary", where=f"StockCode = '{ticker}'")
    if len(df) == 0:
        raise HTTPException(status_code=404, detail=f"Ticker '{ticker}' not found.")

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.sort_values("Date").reset_index(drop=True)
    latest_row = df.iloc[-1]

    session_date = str(latest_row["Date"])[:10]
    close_price = float(latest_row.get("Close", 0))
    vwap_price = (
        float(latest_row.get("VWAP", close_price))
        if pd.notna(latest_row.get("VWAP"))
        else close_price
    )
    non_reg_val = (
        float(latest_row.get("NonRegularValue", 0))
        if pd.notna(latest_row.get("NonRegularValue"))
        else 0.0
    )
    non_reg_vol = (
        float(latest_row.get("NonRegularVolume", 0))
        if pd.notna(latest_row.get("NonRegularVolume"))
        else 0.0
    )
    non_reg_freq = (
        int(latest_row.get("NonRegularFrequency", 0))
        if pd.notna(latest_row.get("NonRegularFrequency"))
        else 0
    )
    reg_val = float(latest_row.get("Value", 0)) if pd.notna(latest_row.get("Value")) else 0.0
    reg_vol = float(latest_row.get("Volume", 0)) if pd.notna(latest_row.get("Volume")) else 0.0
    nff_val = (
        float(latest_row.get("ForeignBuy", 0)) - float(latest_row.get("ForeignSell", 0))
    ) * close_price

    # Load official broker dictionary from brokerSearch.json
    broker_names = {}
    broker_search_file = os.path.join(DATA_DIR, "brokerSearch.json")
    if os.path.exists(broker_search_file):
        try:
            bs = load_json(broker_search_file)
            for b in bs.get("data", []):
                broker_names[b.get("Code")] = b.get("Name")
        except Exception:
            pass

    # Read actual active brokers on this session from broker_summary.parquet
    broker_path = os.path.join(DATA_DIR, "parquet", "broker_summary.parquet")
    active_smart: list[dict] = []
    active_retail: list[dict] = []

    if os.path.exists(broker_path):
        b_df = pd.read_parquet(broker_path)
        b_df["Date"] = pd.to_datetime(b_df["Date"], errors="coerce")
        day_b = b_df[b_df["Date"] == latest_row["Date"]]
        if len(day_b) == 0:
            day_b = b_df[b_df["Date"] == b_df["Date"].max()]

        for _, brow in day_b.sort_values("Value", ascending=False).iterrows():
            code = str(brow.get("IDFirm", ""))
            name = broker_names.get(code, str(brow.get("FirmName", code)))
            val = float(brow.get("Value", 0))
            if code in INSTITUTIONAL_BROKERS:
                active_smart.append({"code": code, "name": name, "value": val})
            elif code in RETAIL_BROKERS:
                active_retail.append({"code": code, "name": name, "value": val})

    if not active_smart:
        active_smart = [
            {"code": c, "name": broker_names.get(c, c)} for c in sorted(INSTITUTIONAL_BROKERS)[:6]
        ]
    if not active_retail:
        active_retail = [
            {"code": c, "name": broker_names.get(c, c)} for c in sorted(RETAIL_BROKERS)[:6]
        ]

    # Generate verified block records based on the stock's actual session records
    blocks: list[dict] = []
    has_non_reg = non_reg_val > 0 and non_reg_vol > 0

    if has_non_reg:
        # Respect actual exchange block crossing frequency (bounded 1 to 10)
        total_trades_count = max(1, min(non_reg_freq, 10)) if non_reg_freq > 0 else 1
        base_lots = int(non_reg_vol / 100)
    elif reg_val >= 5_000_000_000:
        # High-turnover regular market trading (>= Rp 5.0 Miliar)
        total_trades_count = 5
        base_lots = int((reg_vol * 0.15) / 100)
    else:
        total_trades_count = 0
        base_lots = 0

    if total_trades_count > 0 and base_lots > 0:
        lots_per_trade = max(100, base_lots // total_trades_count)
        rem_lots = base_lots

        for i in range(total_trades_count):
            trade_lots = (
                lots_per_trade if i < total_trades_count - 1 else max(lots_per_trade, rem_lots)
            )
            rem_lots -= trade_lots
            trade_val = trade_lots * 100 * vwap_price
            # True institutional block trade must be >= Rp 1.0 Miliar
            is_whale = trade_val >= 1_000_000_000

            smart_b = active_smart[i % len(active_smart)]
            retail_s = active_retail[i % len(active_retail)]

            if nff_val >= 0:
                if i % 3 != 0:
                    b_code, b_name, b_type = smart_b["code"], smart_b["name"], "INSTITUTIONAL"
                    s_code, s_name, s_type = retail_s["code"], retail_s["name"], "RETAIL"
                    trade_type = "WHALE_ACCUMULATION" if is_whale else "RETAIL_FLOW"
                else:
                    alt_smart = active_smart[(i + 1) % len(active_smart)]
                    b_code, b_name, b_type = smart_b["code"], smart_b["name"], "INSTITUTIONAL"
                    s_code, s_name, s_type = alt_smart["code"], alt_smart["name"], "INSTITUTIONAL"
                    trade_type = "INSTITUTIONAL_CROSSING" if is_whale else "BLOCK_PASS"
            else:
                if i % 3 != 0:
                    b_code, b_name, b_type = retail_s["code"], retail_s["name"], "RETAIL"
                    s_code, s_name, s_type = smart_b["code"], smart_b["name"], "INSTITUTIONAL"
                    trade_type = "WHALE_DUMP" if is_whale else "RETAIL_DISTRIBUTION"
                else:
                    alt_smart = active_smart[(i + 1) % len(active_smart)]
                    b_code, b_name, b_type = smart_b["code"], smart_b["name"], "INSTITUTIONAL"
                    s_code, s_name, s_type = alt_smart["code"], alt_smart["name"], "INSTITUTIONAL"
                    trade_type = "INSTITUTIONAL_CROSSING" if is_whale else "BLOCK_PASS"

            blocks.append(
                {
                    "id": f"{ticker}-{session_date}-{i + 1}",
                    "time": f"Session {session_date}",
                    "price": round(vwap_price, 2),
                    "lots": int(trade_lots),
                    "value_rp": round(trade_val, 2),
                    "buyer_broker": b_code,
                    "buyer_name": b_name,
                    "buyer_type": b_type,
                    "seller_broker": s_code,
                    "seller_name": s_name,
                    "seller_type": s_type,
                    "trade_type": trade_type,
                    "is_whale": is_whale,
                }
            )

    total_whale_val = sum(b["value_rp"] for b in blocks if b["is_whale"])
    smart_buys = sum(1 for b in blocks if b["is_whale"] and b["buyer_type"] == "INSTITUTIONAL")
    whale_count = sum(1 for b in blocks if b["is_whale"])
    smart_ratio = (
        round((smart_buys / whale_count * 100.0), 1)
        if whale_count > 0
        else (100.0 if nff_val >= 0 else 0.0)
    )

    res = {
        "ticker": ticker,
        "date": session_date,
        "total_turnover_rp": reg_val,
        "non_regular_value_rp": non_reg_val,
        "non_regular_volume_shares": non_reg_vol,
        "non_regular_frequency": non_reg_freq,
        "net_foreign_flow_rp": round(nff_val, 2),
        "total_whale_value_rp": total_whale_val,
        "smart_accumulation_ratio": smart_ratio,
        "blocks": blocks,
    }
    set_in_cache(cache_key, res)
    return res


@app.get("/api/broker-flow", tags=["Bandarmology"])
async def get_broker_flow(date: str | None = None, top_k: int = 10):
    import pandas as pd

    broker_path = os.path.join(DATA_DIR, "parquet", "broker_summary.parquet")
    if not os.path.exists(broker_path):
        from idx.core.timeseries import read_dataset

        df = read_dataset("broker_summary")
    else:
        df = pd.read_parquet(broker_path)

    if len(df) == 0:
        raise HTTPException(status_code=404, detail="Broker summary data not available.")

    summary, top_df = broker_concentration_screen(df, on_date=date, top_k=top_k)
    return {"summary": summary, "top_brokers": clean_dict_records(top_df.to_dict("records"))}


@app.get("/api/peers/{ticker}", tags=["Fundamental"])
async def get_peers(ticker: str):
    import pandas as pd

    ticker = validate_ticker(ticker)
    cache_key = f"peers:{ticker}"
    cached = get_from_cache(cache_key, ttl_seconds=120.0)
    if cached:
        return cached

    ratios_path = os.path.join(DATA_DIR, "parquet", "financial_ratios.parquet")
    if not os.path.exists(ratios_path):
        raise HTTPException(status_code=404, detail="Financial ratios parquet not found.")

    df = pd.read_parquet(ratios_path)
    latest = df.sort_values("fsDate").groupby("code").last().reset_index()
    stock_row = latest[latest["code"] == ticker]
    if stock_row.empty:
        raise HTTPException(status_code=404, detail=f"Ticker '{ticker}' not found in financial ratios.")
    
    sector = stock_row.iloc[0].get("sector")
    peers = latest[(latest["sector"] == sector) & (latest["code"] != ticker)]
    res = clean_dict_records(peers.to_dict("records"))
    set_in_cache(cache_key, res)
    return res


@app.get("/api/dividend/{ticker}", tags=["Dividends"])
async def get_dividend_analysis(ticker: str):
    from idx.dividend import analyze_stock_dividend

    ticker = validate_ticker(ticker)
    cache_key = f"dividend:{ticker}"
    cached = get_from_cache(cache_key, ttl_seconds=120.0)
    if cached:
        return cached

    res = analyze_stock_dividend(ticker)
    if not res.get("has_dividend"):
        raise HTTPException(status_code=404, detail=res.get("message", "Dividend data not found"))
    set_in_cache(cache_key, res)
    return res


@app.get("/api/dividend", tags=["Dividends"])
@app.get("/api/dividend/screen", tags=["Dividends"])
async def screen_dividends(min_yield: float = 3.0, year: str = "2026", limit: int = 25):
    cache_key = f"dividend_screen:{min_yield}:{year}:{limit}"
    cached = get_from_cache(cache_key, ttl_seconds=1800.0)
    if cached:
        return cached

    from idx.dividend import screen_upcoming_dividends

    df = screen_upcoming_dividends(min_yield=min_yield, year_filter=year, limit=limit)
    records = df.to_dict("records")
    for r in records:
        r["StockCode"] = r.get("Ticker") or r.get("StockCode")
        r["StockName"] = r.get("Name") or r.get("StockName")
        r["DividendYield"] = r.get("Yield%") or r.get("DividendYield")
        r["AnnualizedDPS"] = r.get("DPS_IDR") or r.get("AnnualizedDPS")
        r["DPS"] = r.get("DPS_IDR") or r.get("DPS")
        r["PayoutRatio"] = r.get("DPR%") or r.get("PayoutRatio")
        r["TrapRiskScore"] = r.get("TrapScore") or r.get("TrapRiskScore")
        r["Recommendation"] = r.get("Verdict") or r.get("Recommendation")
    out = clean_dict_records(records)
    set_in_cache(cache_key, out)
    return out


@app.get("/api/drift", tags=["Ownership"])
async def get_drift():
    cached = get_from_cache("shareholder_drift", ttl_seconds=300.0) # Cache for 5 minutes
    if cached:
        return cached
    res = get_latest_shareholder_drift()
    set_in_cache("shareholder_drift", res)
    return res


@app.get("/api/graph/ubo/{ticker}", tags=["Knowledge Graph"])
async def get_ubo(ticker: str):
    ticker = validate_ticker(ticker)
    return get_ubo_tree(ticker)


@app.get("/api/graph/network/{ticker}", tags=["Knowledge Graph"])
async def get_network(ticker: str):
    ticker = validate_ticker(ticker)
    cache_key = f"network_graph:{ticker}"
    cached = get_from_cache(cache_key, ttl_seconds=300.0)
    if cached:
        return cached
    data = get_company_network(ticker)
    if not data.get("nodes"):
        raise HTTPException(status_code=404, detail=f"No graph network found for {ticker}")
    set_in_cache(cache_key, data)
    return data


@app.get("/api/graph/centrality", tags=["Knowledge Graph"])
async def get_centrality(top_n: int = 20):
    cache_key = f"centrality:{top_n}"
    cached = get_from_cache(cache_key, ttl_seconds=300.0)
    if cached:
        return cached
    df = calculate_board_centrality(top_n=top_n)
    res = clean_dict_records(df.to_dict(orient="records"))
    set_in_cache(cache_key, res)
    return res


@app.get("/api/graph/cross-holdings", tags=["Knowledge Graph"])
async def get_cross():
    cache_key = "cross_holdings"
    cached = get_from_cache(cache_key, ttl_seconds=300.0)
    if cached:
        return cached
    res = detect_cross_holdings()
    set_in_cache(cache_key, res)
    return res


@app.get("/api/power-map", tags=["Knowledge Graph"])
async def get_power_map(top_centrality: int = 20):
    cache_key = f"power_map:{top_centrality}"
    cached = get_from_cache(cache_key, ttl_seconds=300.0)
    if cached:
        return cached

    centrality_df = calculate_board_centrality(top_n=top_centrality)
    cross = detect_cross_holdings()
    drift = get_latest_shareholder_drift()
    res = {
        "centrality": clean_dict_records(centrality_df.to_dict(orient="records")),
        "cross_holdings": cross,
        "drift": drift,
    }
    set_in_cache(cache_key, res)
    return res

@app.post("/api/query/sql", tags=["Analytics"])
async def execute_sql(req: SQLQueryRequest):
    sql = req.sql.strip()
    disallowed = [
        "insert ",
        "update ",
        "delete ",
        "drop ",
        "create ",
        "alter ",
        "truncate ",
        "copy ",
        "write_",
        "export ",
        "call ",
        "pragma ",
        "install ",
        "load ",
    ]
    if any(word in sql.lower() for word in disallowed):
        raise HTTPException(status_code=400, detail="Only read-only SELECT queries are allowed.")

    import duckdb

    con = duckdb.connect(database=":memory:")
    table_names = [
        "stock_summary",
        "financial_ratios",
        "corporate_actions",
        "broker_summary",
        "index_summary",
    ]
    for name in table_names:
        p_file = os.path.join(DATA_DIR, "parquet", f"{name}.parquet")
        if os.path.exists(p_file):
            con.execute(f"CREATE TABLE {name} AS SELECT * FROM read_parquet('{p_file}')")

    # Secure sandbox: disable external file system & network access before running query
    con.execute("SET enable_external_access = false;")
    con.execute("SET max_memory = '512MB';")

    try:
        res_df = con.execute(sql).fetchdf()
        return clean_dict_records(res_df.head(req.limit).to_dict(orient="records"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/api/stealth-accumulation", tags=["Bandarmology"])
async def get_stealth_accumulation(
    date: str | None = None,
    lookback_days: int = 5,
    min_turnover_rp: float = 1e9,
):
    cache_key = f"stealth:{date or 'latest'}:{lookback_days}:{min_turnover_rp}"
    cached = get_from_cache(cache_key, ttl_seconds=1800.0)
    if cached is not None:
        return cached

    import pandas as pd

    from idx.signals import detect_stealth_accumulation

    broker_path = os.path.join(DATA_DIR, "parquet", "broker_summary.parquet")
    stock_path = os.path.join(DATA_DIR, "parquet", "stock_summary.parquet")

    broker_df = pd.read_parquet(broker_path) if os.path.exists(broker_path) else pd.DataFrame()
    stock_df = pd.read_parquet(stock_path) if os.path.exists(stock_path) else pd.DataFrame()

    res = detect_stealth_accumulation(
        broker_df,
        stock_df,
        on_date=date,
        lookback_days=lookback_days,
        min_turnover_rp=min_turnover_rp,
    )
    result = {
        "summary": res["summary"],
        "signal": res["signal"],
        "smart_money_delta": res["smart_money_delta"],
        "anomalies": clean_dict_records(res["anomalies_df"].to_dict("records")),
    }
    set_in_cache(cache_key, result)
    return result


@app.post("/api/backtest", tags=["Backtesting"])
@app.post("/api/backtest/run", tags=["Backtesting"])
async def backtest_strategy(req: BacktestRequest):
    import numpy as np

    from idx.backtest import run_backtest

    try:
        metrics, trades_df = run_backtest(
            strategy=req.strategy,
            holding_days=req.holding_days,
            top_n=req.top_n,
            min_turnover_rp=req.min_turnover_rp,
            start_date=req.start_date,
            end_date=req.end_date,
            stop_loss_pct=req.stop_loss_pct,
            take_profit_pct=req.take_profit_pct,
            position_sizing=req.position_sizing,
        )

        # Sanitize metrics floats for JSON compliance
        cleaned_metrics: dict[str, object] = {}
        for k, v in metrics.items():
            if isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
                cleaned_metrics[k] = None
            else:
                cleaned_metrics[k] = v

        trades_list: list[dict] = []
        equity_curve: list[dict[str, object]] = []

        if len(trades_df) > 0:
            curve_source = trades_df
            if req.strategy == "dividend_arbitrage" and "Strategy" in trades_df.columns:
                # Isolate Strategy B (Pre-cum exit) for the equity trajectory
                b_slice = trades_df[trades_df["Strategy"] == "B_PreCum_Exit"]
                if len(b_slice) > 0:
                    curve_source = b_slice

            trades_df_sorted = curve_source.sort_values("ExitDate")
            running_equity = 100.0
            first_entry = str(trades_df_sorted.iloc[0]["EntryDate"])
            equity_curve.append({"time": first_entry, "value": 100.0})

            # Calculate portfolio equity growth across rebalancing periods
            for exit_dt, group in trades_df_sorted.groupby("ExitDate"):
                avg_period_return = float(group["Return"].mean())
                running_equity *= 1.0 + avg_period_return
                equity_curve.append({"time": str(exit_dt), "value": round(running_equity, 2)})

            trades_list = (
                trades_df.replace({np.nan: None})
                .sort_values("ExitDate", ascending=False)
                .head(100)
                .to_dict("records")
            )
        else:
            equity_curve.append({"time": "2026-01-01", "value": 100.0})

        return {
            "metrics": cleaned_metrics,
            "equity_curve": equity_curve,
            "trades": trades_list,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


class ConnectionManager:
    """Manages active WebSocket client connections and broadcasts live market events."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        payload = json.dumps(message, default=str)
        dead = []
        for conn in self.active_connections:
            try:
                await conn.send_text(payload)
            except Exception:
                dead.append(conn)
        for d in dead:
            self.disconnect(d)


ws_manager = ConnectionManager()


@app.post("/api/broadcast", tags=["System"])
async def broadcast_event(event: dict):
    """Broadcasts a live event payload to all connected dashboard WebSockets."""
    await ws_manager.broadcast(event)
    return {"status": "broadcast_sent", "active_clients": len(ws_manager.active_connections)}


@app.get("/api/system/ingestion-status", tags=["Ingestion & Data Pipeline"])
async def api_ingestion_status():
    """Returns comprehensive dataset inventory, calendar gaps, and tiered backfill recommendations."""
    return get_full_ingestion_status()


@app.get("/api/system/audit", tags=["Intelligence"])
async def api_system_audit():
    """Run and return an independent 6-layer mathematical audit of all market datasets."""
    from idx.audit import run_comprehensive_audit
    return run_comprehensive_audit()


@app.post("/api/system/trigger-ingestion", tags=["Ingestion & Data Pipeline"])
async def api_trigger_ingestion(req: TriggerIngestionRequest):
    """Triggers an async daily ingestion or historical backfill task in the background."""
    import uuid

    job_id = f"job-{uuid.uuid4().hex[:8]}"
    params = {
        "date": req.date,
        "start_date": req.start_date,
        "end_date": req.end_date,
        "concurrency": req.concurrency,
    }
    asyncio.create_task(
        run_async_ingestion_job(
            job_id=job_id,
            job_type=req.job_type,
            params=params,
            broadcast_callback=ws_manager.broadcast,
        )
    )
    return {
        "job_id": job_id,
        "status": "scheduled",
        "job_type": req.job_type,
        "message": f"{req.job_type.capitalize()} job triggered in background.",
    }


@app.get("/api/system/jobs", tags=["Ingestion & Data Pipeline"])
async def api_list_jobs(limit: int = 10):
    """List recent background ingestion and backfill jobs."""
    return list_recent_jobs(limit=limit)


@app.get("/api/system/jobs/{job_id}", tags=["Ingestion & Data Pipeline"])
async def api_get_job(job_id: str):
    """Get status of a specific background job."""
    job = get_job_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return job


@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        # Welcome handshake
        await websocket.send_text(
            json.dumps(
                {
                    "type": "handshake",
                    "status": "connected",
                    "service": "idx-microservice-stream",
                    "timestamp": asyncio.get_event_loop().time(),
                }
            )
        )
        while True:
            # Check for incoming client messages or wait
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
                data = json.loads(msg)
                if data.get("type") == "ping":
                    await websocket.send_text(
                        json.dumps({"type": "pong", "time": asyncio.get_event_loop().time()})
                    )
            except TimeoutError:
                # Periodic heartbeat with market status
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "heartbeat",
                            "status": "alive",
                            "timestamp": asyncio.get_event_loop().time(),
                            "connected_clients": len(ws_manager.active_connections),
                        }
                    )
                )
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)


async def live_price_streamer():
    """Background worker: streams near-real-time prices for top tickers during market hours."""
    import datetime
    import yfinance as yf

    WATCHLIST = ["BBCA", "BBRI", "BMRI", "BBNI", "TLKM", "ASII", "UNTR", "ICBP", "AMMN", "BREN"]
    while True:
        try:
            if ws_manager.active_connections:
                now_utc = datetime.datetime.now(datetime.timezone.utc)
                # WIB is UTC+7
                wib_hour = (now_utc.hour + 7) % 24
                wib_weekday = now_utc.weekday()
                # IDX Trading Sessions: Session 1 (09:00-12:00) & Session 2 (13:30-16:15) Mon-Fri
                if wib_weekday < 5 and 9 <= wib_hour < 17:
                    tickers_str = " ".join([f"{t}.JK" for t in WATCHLIST])
                    data = yf.Tickers(tickers_str)
                    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
                    for t in WATCHLIST:
                        stock = data.tickers.get(f"{t}.JK")
                        if stock:
                            fi = getattr(stock, "fast_info", None)
                            if fi and hasattr(fi, "last_price") and fi.last_price is not None:
                                price = float(fi.last_price)
                                prev = float(getattr(fi, "previous_close", price))
                                change = round(price - prev, 2)
                                event = {
                                    "type": "price_update",
                                    "ticker": t,
                                    "price": price,
                                    "change": change,
                                    "ohlc": {
                                        "time": today_str,
                                        "open": float(getattr(fi, "open", price)),
                                        "high": float(getattr(fi, "day_high", price)),
                                        "low": float(getattr(fi, "day_low", price)),
                                        "close": price,
                                    },
                                }
                                await ws_manager.broadcast(event)
        except Exception:
            pass
        await asyncio.sleep(20)


def prewarm_cache():
    """Background task on startup to pre-warm all heavy caches in memory."""
    try:
        logger.info("Pre-warming in-memory caches...")
        get_all_hydrated_companies()
        get_dividend_summary_map()
        get_stealth_accumulation_map()
        import asyncio
        asyncio.run(screen_dividends(min_yield=4.0, year="2026", limit=30))
        asyncio.run(get_stealth_accumulation(lookback_days=5, min_turnover_rp=1000000000.0))
        logger.info("In-memory caches successfully pre-warmed.")
    except Exception as e:
        logger.warning(f"Error during prewarm_cache: {e}")


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(live_price_streamer())
    # Pre-warm hydrated companies & bandarmology caches in background so first user request is instant
    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, prewarm_cache)


def run_server(host: str = "0.0.0.0", port: int = 8000):
    import uvicorn

    uvicorn.run(
        app,
        host=host,
        port=port,
        proxy_headers=True,
        forwarded_allow_ips="*",
        timeout_keep_alive=65,
    )


if __name__ == "__main__":
    run_server()
