"""
Data cleaning and normalization utilities.
Handles the intentionally-messy fields from both boards.
"""

from __future__ import annotations
import re
from typing import Any


# ── Currency / numeric ──────────────────────────────────────────────────────

def parse_number(value: Any) -> float | None:
    """Parse various numeric representations to float. Returns None on failure."""
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.lower() in ("nan", "n/a", "-", ""):
        return None
    # Strip currency symbols, commas, whitespace
    s = re.sub(r"[₹$€£,\s]", "", s)
    try:
        return float(s)
    except ValueError:
        return None


def fmt_inr(value: float | None, label: str = "") -> str:
    """Format a float as Indian Rupees string."""
    if value is None:
        return "N/A"
    prefix = f"₹{value:,.2f}"
    return f"{prefix} {label}".strip()


# ── Date normalisation ───────────────────────────────────────────────────────

def parse_date(value: Any) -> str | None:
    """
    Return an ISO-format date string (YYYY-MM-DD) from various date representations,
    or None if unparseable.
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.lower() in ("nan", "n/a", "-", ""):
        return None

    # Already ISO
    iso_match = re.match(r"(\d{4}-\d{2}-\d{2})", s)
    if iso_match:
        return iso_match.group(1)

    from dateutil import parser as dparser  # type: ignore
    try:
        return dparser.parse(s, dayfirst=False).strftime("%Y-%m-%d")
    except Exception:
        return None


# ── Text normalisation ───────────────────────────────────────────────────────

_PROB_MAP = {
    "high": "High",
    "medium": "Medium",
    "med": "Medium",
    "low": "Low",
    "confirmed": "Confirmed",
    "very high": "Very High",
}


def normalise_probability(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip().lower()
    return _PROB_MAP.get(s, str(value).strip() if value else None)


_STATUS_MAP = {
    "open": "Open",
    "closed": "Closed",
    "won": "Won",
    "lost": "Lost",
    "in progress": "In Progress",
    "completed": "Completed",
    "not started": "Not Started",
    "on hold": "On Hold",
    "update required": "Update Required",
    "partially billed": "Partially Billed",
}


def normalise_status(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip().lower()
    return _STATUS_MAP.get(s, str(value).strip() if value else None)


# ── Record cleaning ──────────────────────────────────────────────────────────

def clean_deal_record(record: dict) -> dict:
    """Normalise a single deal record fetched from Monday.com."""
    numeric_fields = [
        "Masked Deal value",
        "Closure Probability",    # sometimes stored as a number
    ]
    date_fields = [
        "Close Date A",
        "Tentative Close Date",
        "Created Date",
    ]
    status_fields = ["Deal Status"]
    prob_fields = []  # already text for this board

    out = dict(record)
    for f in numeric_fields:
        if f in out:
            out[f] = parse_number(out[f])
    for f in date_fields:
        if f in out:
            out[f] = parse_date(out[f])
    for f in status_fields:
        if f in out:
            out[f] = normalise_status(out[f])
    # Closure Probability can be text (High/Med/Low) or numeric %
    cp = out.get("Closure Probability")
    if cp is not None:
        num = parse_number(cp)
        if num is None:
            out["Closure Probability"] = normalise_probability(cp)
        # else leave the numeric value as-is
    return out


def clean_work_order_record(record: dict) -> dict:
    """Normalise a single work-order record fetched from Monday.com."""
    numeric_fields = [
        "Amount in Rupees Excl of GST Masked",
        "Amount in Rupees Incl of GST Masked",
        "Billed Value in Rupees Excl of GST Masked",
        "Billed Value in Rupees Incl of GST Masked",
        "Collected Amount in Rupees Incl of GST Masked",
        "Amount to be billed in Rs Exl of GST Masked",
        "Amount to be billed in Rs Incl of GST Masked",
        "Amount Receivable Masked",
        "Quantity by Ops",
        "Quantities as per PO",
        "Quantity billed till date",
        "Balance in quantity",
    ]
    date_fields = [
        "Date of POLOI",
        "Probable Start Date",
        "Probable End Date",
        "Data Delivery Date",
        "Last invoice date",
        "Expected Billing Month",
        "Actual Billing Month",
        "Actual Collection Month",
        "Collection Date",
    ]
    status_fields = ["Execution Status", "WO Status billed", "Invoice Status", "Billing Status", "Collection status"]

    out = dict(record)
    for f in numeric_fields:
        if f in out:
            out[f] = parse_number(out[f])
    for f in date_fields:
        if f in out:
            out[f] = parse_date(out[f])
    for f in status_fields:
        if f in out:
            out[f] = normalise_status(out[f])
    return out


# ── Aggregation helpers ──────────────────────────────────────────────────────

def safe_sum(values: list[Any]) -> float:
    return sum(v for v in values if isinstance(v, (int, float)))


def group_by(records: list[dict], key: str) -> dict[str, list[dict]]:
    """Group records by the value of a field."""
    groups: dict[str, list[dict]] = {}
    for r in records:
        k = str(r.get(key) or "Unknown")
        groups.setdefault(k, []).append(r)
    return groups


def data_quality_note(records: list[dict], fields: list[str]) -> str:
    """Return a brief data-quality caveat string for the given fields."""
    total = len(records)
    if total == 0:
        return ""
    notes = []
    for f in fields:
        missing = sum(1 for r in records if r.get(f) is None)
        if missing:
            pct = round(100 * missing / total)
            notes.append(f"'{f}' missing in {missing}/{total} records ({pct}%)")
    if notes:
        return "⚠ Data quality notes: " + "; ".join(notes)
    return ""
