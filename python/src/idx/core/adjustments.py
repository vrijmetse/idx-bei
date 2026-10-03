"""
Corporate Action & Split Adjustment Engine.

Applies standard backward split adjustment factors to historical OHLCV data
to eliminate artificial price discontinuities caused by stock splits and reverse splits.
"""

from typing import Dict, Optional
import pandas as pd
from idx.core.query import query_dataset

# In-memory cache of split events by ticker: {ticker: [(split_date, ratio), ...]}
_SPLITS_CACHE: Optional[Dict[str, list]] = None


def get_all_splits_cache() -> Dict[str, list]:
    """Load and cache all stock split and reverse stock events across IDX."""
    global _SPLITS_CACHE
    if _SPLITS_CACHE is not None:
        return _SPLITS_CACHE

    splits_map: Dict[str, list] = {}
    try:
        df_ca = query_dataset(
            "corporate_actions",
            where="JenisTindakan IN ('stockSplit', 'reverseStock')",
        )
        if len(df_ca) > 0:
            df_ca = df_ca.sort_values("TanggalPencatatan")
            for _, r in df_ca.iterrows():
                ticker = str(r["KodeEmiten"]).upper()
                split_date = pd.to_datetime(r["TanggalPencatatan"])
                action = str(r["JenisTindakan"])
                after = float(r["JumlahSahamSetelahTindakan"] or 0)
                add_or_base = float(r["JumlahSaham"] or 0)

                ratio = 1.0
                if action == "stockSplit":
                    # For IDX stockSplit: after / (after - add_or_base)
                    denom = after - add_or_base
                    if denom > 0:
                        ratio = after / denom
                    elif add_or_base > 0:
                        ratio = after / add_or_base
                elif action == "reverseStock":
                    # Reverse split decreases shares and increases price
                    if add_or_base > 0 and after > 0:
                        ratio = after / add_or_base

                # Only register meaningful splits (ratio differs from 1.0 by at least 10%)
                if ratio > 1.1 or (0 < ratio < 0.9):
                    splits_map.setdefault(ticker, []).append((split_date, ratio))
    except Exception as e:
        import logging
        logging.getLogger("idx.adjustments").warning(f"Could not load corporate actions splits: {e}")

    _SPLITS_CACHE = splits_map
    return _SPLITS_CACHE


def adjust_stock_splits(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Apply backward split adjustment to a stock's historical OHLCV time-series."""
    if len(df) == 0:
        return df

    splits = get_all_splits_cache().get(ticker.upper(), [])
    if not splits:
        return df

    df = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df["Date"]):
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    # Sort splits in reverse chronological order to apply backward cumulative factors
    for split_date, ratio in sorted(splits, key=lambda x: x[0], reverse=True):
        mask = df["Date"] < split_date
        if not mask.any():
            continue

        for col in ["Close", "OpenPrice", "High", "Low", "Previous"]:
            if col in df.columns:
                df.loc[mask, col] = df.loc[mask, col] / ratio

        if "Volume" in df.columns:
            df.loc[mask, "Volume"] = df.loc[mask, "Volume"] * ratio

    return df
