"""
One-time script to import Deal Funnel and Work Order data into Monday.com.

Usage:
    python import_boards.py

Requires:
    MONDAY_API_KEY in environment (or .env file)
    Excel files in the same directory as this script (skylark-bi-agent/)

After running, set in your .env:
    DEALS_BOARD_ID=<printed board ID>
    WORK_ORDERS_BOARD_ID=<printed board ID>
"""

from __future__ import annotations
import os
import sys
import time
import math
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# Fix path to find monday_client
sys.path.insert(0, os.path.dirname(__file__))
import monday_client as mc

# ── File paths ───────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
DEALS_FILE = os.path.join(_HERE, "Deal funnel Data.xlsx")
WO_FILE = os.path.join(_HERE, "Work_Order_Tracker Data.xlsx")


# ── Data loading ─────────────────────────────────────────────────────────────

def load_deals() -> pd.DataFrame:
    df = pd.read_excel(DEALS_FILE)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def load_work_orders() -> pd.DataFrame:
    # Row 0 is the actual header
    df = pd.read_excel(WO_FILE, header=None)
    df.columns = [str(v).strip() for v in df.iloc[0]]
    df = df.iloc[1:].reset_index(drop=True)
    return df


# ── Column type mapping ───────────────────────────────────────────────────────

def _col_type_for(col_name: str) -> str:
    """
    Map column names to Monday.com column types.
    We intentionally use only text / numbers / date - the three types that
    accept arbitrary values without requiring pre-configured labels or special
    setup.  'status' columns require their labels to exist before values can
    be set, which would cause 400 errors on create_item for every row.
    """
    name_lower = col_name.lower()
    if any(k in name_lower for k in ["date", "month"]):
        return "date"
    if any(k in name_lower for k in [
        "amount", "value", "rupee", "qty", "quantity",
        "billed", "collected", "receivable", "balance",
    ]):
        return "numbers"
    return "text"


def _to_monday_value(col_type: str, raw_value) -> str | dict | None:
    """
    Convert a pandas cell value to the Monday.com column_values format.
    Returns the Python object that will be JSON-stringified by the API client.
    """
    import json

    if raw_value is None or (isinstance(raw_value, float) and math.isnan(raw_value)):
        return None

    val = str(raw_value).strip()
    if not val or val.lower() in ("nan", "nat", "none", "n/a"):
        return None

    if col_type == "date":
        # Parse to YYYY-MM-DD
        try:
            from dateutil import parser as dp
            parsed = dp.parse(val)
            return {"date": parsed.strftime("%Y-%m-%d")}
        except Exception:
            return None

    if col_type == "numbers":
        import re
        clean = re.sub(r"[\u20b9$\u20ac\xa3,\s]", "", val)
        try:
            # Monday.com numbers column expects a numeric string in column_values
            num = float(clean)
            return str(num)
        except ValueError:
            return None

    # text / date fallback - return plain string
    return val


# ── Board creation ────────────────────────────────────────────────────────────

def _safe_title(s: str, max_len: int = 50) -> str:
    import re
    # Strip characters Monday.com rejects in column titles
    cleaned = re.sub(r"[\(\)\/\.\\\"']", "", str(s)).strip()
    # Collapse multiple spaces
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:max_len]


def create_and_populate_board(name: str, df: pd.DataFrame) -> str:
    """Create a Monday board, add columns, and populate with rows. Returns board ID."""
    print(f"\n→ Creating board: {name}")
    board_id = mc.create_board(name, "public")
    print(f"  Board ID: {board_id}")

    # The 'Name' column is built-in; skip it in column creation
    data_cols = [c for c in df.columns if c != df.columns[0]]  # first col used as item name

    # Create columns
    col_id_map: dict[str, tuple[str, str]] = {}  # title -> (mon_col_id, mon_col_type)
    for col in data_cols:
        ctype = _col_type_for(col)
        title = _safe_title(col)
        try:
            col_id = mc.create_column(board_id, title, ctype)
            col_id_map[col] = (col_id, ctype)
            print(f"  + Column '{title}' [{ctype}] → {col_id}")
        except Exception as e:
            # Retry as plain text before giving up
            if ctype != "text":
                try:
                    col_id = mc.create_column(board_id, title, "text")
                    col_id_map[col] = (col_id, "text")
                    print(f"  + Column '{title}' [text fallback] → {col_id}")
                except Exception as e2:
                    print(f"  ! Skipping column '{title}': {e2}")
            else:
                print(f"  ! Skipping column '{title}': {e}")
        time.sleep(0.15)

    # Import rows
    name_col = df.columns[0]
    print(f"\n  Importing {len(df)} rows …")
    for idx, row in df.iterrows():
        raw_name = row.iloc[0]
        item_name = str(raw_name).strip() if pd.notna(raw_name) else ""
        if not item_name or item_name.lower() in ("nan", "none", "nat"):
            item_name = f"Item {idx + 1}"

        column_values: dict = {}
        for col, (col_id, col_type) in col_id_map.items():
            mv = _to_monday_value(col_type, row.get(col))
            if mv is not None:
                column_values[col_id] = mv

        try:
            mc.create_item(board_id, item_name, column_values)
        except Exception as e:
            print(f"  ! Row {idx} failed: {e}")
        time.sleep(0.4)  # ~2.5 items/sec - stays well under Monday.com rate limits

        if (idx + 1) % 25 == 0:
            print(f"    … {idx + 1}/{len(df)} done")

    print(f"  ✓ Done importing {name}")
    return board_id


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("Loading data …")
    deals_df = load_deals()
    wo_df = load_work_orders()

    print(f"Deals: {deals_df.shape}, Work Orders: {wo_df.shape}")

    deals_board_id = create_and_populate_board("Deal Funnel", deals_df)
    wo_board_id = create_and_populate_board("Work Order Tracker", wo_df)

    print("\n" + "=" * 50)
    print("DONE! Add these to your .env file:")
    print(f"DEALS_BOARD_ID={deals_board_id}")
    print(f"WORK_ORDERS_BOARD_ID={wo_board_id}")
    print("=" * 50)


if __name__ == "__main__":
    main()
