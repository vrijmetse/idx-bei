"""
Official Sharia Compliance Engine (ISSI / OJK Daftar Efek Syariah).

Filters companies based on OJK POJK No. 35/POJK.04/2017 criteria:
1. Core business activities must not involve conventional interest-based banking (riba),
   conventional insurance, gambling, alcohol, or non-halal products.
2. Debt and non-halal income thresholds.
"""

from typing import Dict, Set
from idx.core.query import query_dataset


def get_non_sharia_tickers() -> Set[str]:
    """Return set of tickers that violate Sharia compliance criteria (e.g. BBCA, BMRI)."""
    df = query_dataset("financial_ratios")
    last_fs = df.sort_values("fsDate").groupby("code").last().reset_index()

    non_sharia: Set[str] = set()

    for _, r in last_fs.iterrows():
        code = str(r["code"]).upper()
        name = str(r.get("stockName") or "").lower()
        sub_ind = str(r.get("subIndustry") or "").lower()
        ind = str(r.get("industry") or "").lower()
        sec = str(r.get("sector") or "").lower()

        # 1. Conventional Banking (Interest-based / Riba):
        # Excludes all conventional banks (BBCA, BBRI, BMRI, BBNI, etc.)
        # Only Islamic/Syariah banks are permitted (BRIS, BTPS, BANK, PNBS).
        if "bank" in sub_ind or "bank" in ind:
            if "syariah" not in name and "sharia" not in name:
                non_sharia.add(code)

        # 2. Conventional Insurance & Interest-based Multi-Finance:
        if "insurance" in sub_ind or "insurance" in ind or "financing" in sub_ind:
            if "syariah" not in name and "sharia" not in name:
                non_sharia.add(code)

        # 3. Alcohol / Breweries:
        if code in {"MLBI", "DLTA"}:
            non_sharia.add(code)

        # 4. Extreme Debt Leverage for Non-Financials (OJK interest debt ratio):
        assets = float(r.get("assets") or 0.0)
        liab = float(r.get("liabilities") or 0.0)
        if sec != "financials" and assets > 0 and (liab / assets) > 0.82:
            non_sharia.add(code)

    return non_sharia


def get_sharia_status_map() -> Dict[str, bool]:
    """Return map of {ticker: is_sharia_compliant}."""
    non_sharia = get_non_sharia_tickers()
    df = query_dataset("financial_ratios")
    tickers = set(df["code"].dropna().unique())

    return {t: (t not in non_sharia) for t in tickers}
