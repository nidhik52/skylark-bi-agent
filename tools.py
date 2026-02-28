"""
Agent tools – each function makes live Monday.com API calls.
No data is cached between calls. Every invocation fetches fresh board state.

Each public function returns a plain dict that the agent can summarise.
The TOOL_SCHEMAS list defines the OpenAI function-calling specifications.
"""

from __future__ import annotations
import os
import json
from datetime import date, datetime
from collections import defaultdict

import monday_client as mc
from data_utils import (
    clean_deal_record,
    clean_work_order_record,
    safe_sum,
    group_by,
    data_quality_note,
    parse_number,
)

# ── Board IDs (injected from env) ────────────────────────────────────────────

def _deals_board() -> str:
    bid = os.environ.get("DEALS_BOARD_ID", "")
    if not bid:
        raise RuntimeError("DEALS_BOARD_ID is not set. Please run import_boards.py first.")
    return bid


def _wo_board() -> str:
    bid = os.environ.get("WORK_ORDERS_BOARD_ID", "")
    if not bid:
        raise RuntimeError("WORK_ORDERS_BOARD_ID is not set. Please run import_boards.py first.")
    return bid


# ── Internal helpers ─────────────────────────────────────────────────────────

def _fetch_deals() -> list[dict]:
    items = mc.get_board_items(_deals_board())
    records = mc.items_to_records(items)
    return [clean_deal_record(r) for r in records]


def _fetch_work_orders() -> list[dict]:
    items = mc.get_board_items(_wo_board())
    records = mc.items_to_records(items)
    return [clean_work_order_record(r) for r in records]


def _filter_list(records: list[dict], filters: dict) -> list[dict]:
    """
    Apply case-insensitive substring filters to a list of records.
    filters = {"Sectorservice": "mining"} → keeps records where field contains substring.
    """
    result = records
    for field, value in filters.items():
        if value is None:
            continue
        val_lower = str(value).lower().strip()
        result = [
            r for r in result
            if r.get(field) is not None and val_lower in str(r[field]).lower()
        ]
    return result


def _today_iso() -> str:
    return date.today().isoformat()


def _quarter_bounds(year: int | None = None, quarter: int | None = None):
    """Return (start_iso, end_iso) for the given quarter (default: current)."""
    today = date.today()
    y = year or today.year
    if quarter is None:
        q = (today.month - 1) // 3 + 1
    else:
        q = quarter
    starts = {1: (1, 1), 2: (4, 1), 3: (7, 1), 4: (10, 1)}
    ends = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}
    sm, sd = starts[q]
    em, ed = ends[q]
    return datetime(y, sm, sd).date().isoformat(), datetime(y, em, ed).date().isoformat()


# ══════════════════════════════════════════════════════════════════════════════
#  TOOL IMPLEMENTATIONS
# ══════════════════════════════════════════════════════════════════════════════

def get_pipeline_summary(sector: str | None = None, quarter: str | None = None) -> dict:
    """
    Return high-level pipeline metrics from the Deal Funnel board.

    Args:
        sector:  Optional sector filter (e.g. "Mining", "Powerline", "Energy").
        quarter: Optional quarter filter like "Q1 2026" or "current".
    """
    deals = _fetch_deals()
    total_fetched = len(deals)

    # Sector filter
    if sector:
        deals = _filter_list(deals, {"Sectorservice": sector})

    # Quarter filter on Tentative Close Date
    if quarter:
        q_str = quarter.strip().lower()
        if q_str == "current":
            start, end = _quarter_bounds()
        else:
            # Parse "Q2 2026"
            import re
            m = re.match(r"q([1-4])\s*(\d{4})", q_str)
            if m:
                start, end = _quarter_bounds(int(m.group(2)), int(m.group(1)))
            else:
                start, end = _quarter_bounds()
        deals = [
            d for d in deals
            if d.get("Tentative Close Date") is not None
            and start <= d["Tentative Close Date"] <= end
        ]

    open_deals = [d for d in deals if (d.get("Deal Status") or "").lower() == "open"]
    closed_won = [d for d in deals if (d.get("Deal Status") or "").lower() in ("closed", "won")]
    total_value = safe_sum([d.get("Masked Deal value") for d in deals])
    open_value = safe_sum([d.get("Masked Deal value") for d in open_deals])
    won_value = safe_sum([d.get("Masked Deal value") for d in closed_won])

    # Stage breakdown
    by_stage = group_by(open_deals, "Deal Stage")
    stage_summary = {stage: len(recs) for stage, recs in by_stage.items()}

    # Sector breakdown
    by_sector = group_by(deals, "Sectorservice")
    sector_summary = {
        s: {
            "count": len(recs),
            "total_value": safe_sum([r.get("Masked Deal value") for r in recs]),
        }
        for s, recs in by_sector.items()
    }

    dq = data_quality_note(deals, ["Masked Deal value", "Deal Status", "Tentative Close Date"])

    return {
        "total_deals_in_board": total_fetched,
        "filtered_deals": len(deals),
        "open_deals": len(open_deals),
        "closed_won_deals": len(closed_won),
        "total_pipeline_value_inr": total_value,
        "open_pipeline_value_inr": open_value,
        "won_value_inr": won_value,
        "by_stage": stage_summary,
        "by_sector": sector_summary,
        "filters_applied": {"sector": sector, "quarter": quarter},
        "data_quality": dq,
    }


def get_deals_list(
    sector: str | None = None,
    status: str | None = None,
    stage: str | None = None,
    owner: str | None = None,
    limit: int = 20,
) -> dict:
    """
    Return a filtered list of individual deals with key fields.

    Args:
        sector:  Filter by Sectorservice (partial match, case-insensitive).
        status:  Filter by Deal Status (Open / Closed / Won / Lost).
        stage:   Filter by Deal Stage (partial match).
        owner:   Filter by Owner code.
        limit:   Max number of records to return (default 20).
    """
    deals = _fetch_deals()
    filters = {}
    if sector:
        filters["Sectorservice"] = sector
    if status:
        filters["Deal Status"] = status
    if stage:
        filters["Deal Stage"] = stage
    if owner:
        filters["Owner code"] = owner

    deals = _filter_list(deals, filters)

    display_fields = [
        "Name", "Deal Status", "Deal Stage", "Sectorservice",
        "Masked Deal value", "Closure Probability", "Tentative Close Date",
        "Owner code",
    ]
    results = [{k: d.get(k) for k in display_fields} for d in deals[:limit]]
    dq = data_quality_note(deals, ["Masked Deal value", "Closure Probability"])

    return {
        "total_matching": len(deals),
        "showing": len(results),
        "deals": results,
        "data_quality": dq,
    }


def get_at_risk_deals(value_threshold_inr: float | None = None) -> dict:
    """
    Identify deals that may be at risk: low closure probability or stalled stage.

    Args:
        value_threshold_inr: Only include deals above this value. Default: all.
    """
    deals = _fetch_deals()
    open_deals = [d for d in deals if (d.get("Deal Status") or "").lower() == "open"]

    risk_reasons: dict[str, list] = defaultdict(list)

    for d in open_deals:
        name = d.get("Name") or "Unknown"
        value = d.get("Masked Deal value")
        prob = d.get("Closure Probability")
        stage = d.get("Deal Stage") or ""
        t_close = d.get("Tentative Close Date")

        if value_threshold_inr and (value or 0) < value_threshold_inr:
            continue

        reasons = []
        # Low probability
        if isinstance(prob, str) and prob.lower() == "low":
            reasons.append("Low closure probability")
        if isinstance(prob, (int, float)) and prob < 30:
            reasons.append(f"Low closure probability ({prob}%)")

        # Overdue tentative close
        if t_close:
            try:
                close_dt = datetime.fromisoformat(t_close).date()
                if close_dt < date.today():
                    days_overdue = (date.today() - close_dt).days
                    reasons.append(f"Tentative close date overdue by {days_overdue} days")
            except ValueError:
                pass

        # Early stage with no close date
        early_stage_keywords = ["prospect", "qualified lead", "sql", "mql"]
        if any(k in stage.lower() for k in early_stage_keywords) and t_close is None:
            reasons.append("Early stage with no expected close date")

        if reasons:
            risk_reasons[name] = {  # type: ignore[assignment]
                "value": value,
                "stage": stage,
                "sector": d.get("Sectorservice"),
                "reasons": reasons,
            }

    total_at_risk_value = safe_sum(
        [v["value"] for v in risk_reasons.values() if isinstance(v, dict)]
    )
    dq = data_quality_note(open_deals, ["Masked Deal value", "Closure Probability", "Tentative Close Date"])

    return {
        "total_open_deals": len(open_deals),
        "at_risk_count": len(risk_reasons),
        "total_at_risk_value_inr": total_at_risk_value,
        "deals_at_risk": dict(risk_reasons),
        "data_quality": dq,
    }


def get_work_order_summary(
    sector: str | None = None,
    status: str | None = None,
) -> dict:
    """
    Return aggregate metrics from the Work Order Tracker board.

    Args:
        sector: Filter by Sector field (e.g. "Mining", "Powerline").
        status: Filter by Execution Status (e.g. "Completed", "In Progress", "Not Started").
    """
    wos = _fetch_work_orders()
    total_fetched = len(wos)

    filters = {}
    if sector:
        filters["Sector"] = sector
    if status:
        filters["Execution Status"] = status
    wos = _filter_list(wos, filters)

    # Revenue fields
    total_order_value = safe_sum([w.get("Amount in Rupees Excl of GST Masked") for w in wos])
    total_billed = safe_sum([w.get("Billed Value in Rupees Excl of GST Masked") for w in wos])
    total_collected = safe_sum([w.get("Collected Amount in Rupees Incl of GST Masked") for w in wos])
    total_ar = safe_sum([w.get("Amount Receivable Masked") for w in wos])
    to_be_billed = safe_sum([w.get("Amount to be billed in Rs Exl of GST Masked") for w in wos])

    # Status breakdown
    by_status = group_by(wos, "Execution Status")
    status_summary = {st: len(recs) for st, recs in by_status.items()}

    # Sector breakdown
    by_sector = group_by(wos, "Sector")
    sector_summary = {
        s: {"count": len(recs), "total_value": safe_sum([r.get("Amount in Rupees Excl of GST Masked") for r in recs])}
        for s, recs in by_sector.items()
    }

    # Nature of work
    by_type = group_by(wos, "Nature of Work")
    type_summary = {t: len(recs) for t, recs in by_type.items()}

    dq = data_quality_note(
        wos,
        [
            "Amount in Rupees Excl of GST Masked",
            "Billed Value in Rupees Excl of GST Masked",
            "Amount Receivable Masked",
        ],
    )

    return {
        "total_wos_in_board": total_fetched,
        "filtered_wos": len(wos),
        "total_order_value_excl_gst": total_order_value,
        "total_billed_excl_gst": total_billed,
        "total_collected_incl_gst": total_collected,
        "total_accounts_receivable": total_ar,
        "total_yet_to_be_billed": to_be_billed,
        "by_execution_status": status_summary,
        "by_sector": sector_summary,
        "by_nature_of_work": type_summary,
        "filters_applied": {"sector": sector, "status": status},
        "data_quality": dq,
    }


def get_accounts_receivable(priority_only: bool = False, sector: str | None = None) -> dict:
    """
    Return accounts-receivable (AR) details from Work Order Tracker.

    Args:
        priority_only: If True, only return AR Priority accounts.
        sector:        Optional sector filter.
    """
    wos = _fetch_work_orders()
    filters = {}
    if sector:
        filters["Sector"] = sector
    wos = _filter_list(wos, filters)

    if priority_only:
        wos = [w for w in wos if str(w.get("AR Priority account") or "").strip().lower() not in ("", "none", "no", "nan")]

    ar_records = []
    for w in wos:
        ar_val = w.get("Amount Receivable Masked")
        if ar_val and ar_val > 0:
            ar_records.append({
                "Name": w.get("Name") or w.get("Deal name masked"),
                "Customer": w.get("Customer Name Code"),
                "Sector": w.get("Sector"),
                "AR_inr": ar_val,
                "AR_Priority": w.get("AR Priority account"),
                "Collection_Status": w.get("Collection status"),
                "Invoice_Status": w.get("Invoice Status"),
                "Expected_Billing_Month": w.get("Expected Billing Month"),
            })

    ar_records_sorted = sorted(ar_records, key=lambda x: x.get("AR_inr") or 0, reverse=True)
    total_ar = safe_sum([r["AR_inr"] for r in ar_records])
    dq = data_quality_note(wos, ["Amount Receivable Masked", "Collection status"])

    return {
        "total_ar_inr": total_ar,
        "ar_record_count": len(ar_records),
        "top_ar_accounts": ar_records_sorted[:15],
        "filters_applied": {"priority_only": priority_only, "sector": sector},
        "data_quality": dq,
    }


def get_revenue_by_sector(source: str = "both") -> dict:
    """
    Return revenue/deal-value broken down by sector across both boards.

    Args:
        source: "deals" | "work_orders" | "both"
    """
    result: dict = {}

    if source in ("deals", "both"):
        deals = _fetch_deals()
        by_sector = group_by(deals, "Sectorservice")
        result["deals"] = {
            sector: {
                "count": len(recs),
                "total_pipeline_value_inr": safe_sum([r.get("Masked Deal value") for r in recs]),
                "open_count": sum(1 for r in recs if (r.get("Deal Status") or "").lower() == "open"),
            }
            for sector, recs in by_sector.items()
        }

    if source in ("work_orders", "both"):
        wos = _fetch_work_orders()
        by_sector = group_by(wos, "Sector")
        result["work_orders"] = {
            sector: {
                "count": len(recs),
                "total_order_value_inr": safe_sum([r.get("Amount in Rupees Excl of GST Masked") for r in recs]),
                "total_billed_inr": safe_sum([r.get("Billed Value in Rupees Excl of GST Masked") for r in recs]),
                "total_ar_inr": safe_sum([r.get("Amount Receivable Masked") for r in recs]),
            }
            for sector, recs in by_sector.items()
        }

    return result


def get_overdue_work_orders(days_ahead: int = 0) -> dict:
    """
    Return work orders that are overdue (Probable End Date has passed).

    Args:
        days_ahead: Include WOs due within N days from today (0 = only truly overdue).
    """
    from datetime import timedelta

    wos = _fetch_work_orders()
    today = date.today()
    cutoff = today + timedelta(days=days_ahead)
    overdue = []

    for w in wos:
        status = (w.get("Execution Status") or "").lower()
        if status in ("completed",):
            continue
        end_date_str = w.get("Probable End Date")
        if end_date_str:
            try:
                end_dt = datetime.fromisoformat(end_date_str).date()
                if end_dt <= cutoff:
                    days_overdue = (today - end_dt).days
                    overdue.append({
                        "Name": w.get("Name") or w.get("Deal name masked"),
                        "Customer": w.get("Customer Name Code"),
                        "Sector": w.get("Sector"),
                        "Execution_Status": w.get("Execution Status"),
                        "Probable_End_Date": end_date_str,
                        "Days_Overdue": days_overdue,
                        "Order_Value_INR": w.get("Amount in Rupees Excl of GST Masked"),
                        "WO_Status": w.get("WO Status billed"),
                    })
            except ValueError:
                pass

    overdue_sorted = sorted(overdue, key=lambda x: x.get("Days_Overdue") or 0, reverse=True)
    dq = data_quality_note(wos, ["Probable End Date"])

    return {
        "overdue_count": len(overdue),
        "overdue_work_orders": overdue_sorted[:30],
        "total_overdue_value_inr": safe_sum([o.get("Order_Value_INR") for o in overdue]),
        "cutoff_date": cutoff.isoformat(),
        "data_quality": dq,
    }


def search_deals(query: str) -> dict:
    """
    Full-text search across deal names, client codes, owner codes, sector, and stage.

    Args:
        query: Free-text search string.
    """
    deals = _fetch_deals()
    q = query.lower().strip()
    search_fields = [
        "Name", "Client Code", "Owner code", "Sectorservice",
        "Deal Stage", "Deal Status", "Product deal",
    ]
    matches = []
    for d in deals:
        for f in search_fields:
            val = d.get(f)
            if val and q in str(val).lower():
                matches.append({k: d.get(k) for k in [
                    "Name", "Deal Status", "Deal Stage", "Sectorservice",
                    "Masked Deal value", "Closure Probability", "Tentative Close Date",
                    "Owner code",
                ]})
                break

    return {
        "query": query,
        "match_count": len(matches),
        "matches": matches[:20],
    }


# ══════════════════════════════════════════════════════════════════════════════
#  OPENAI TOOL SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_pipeline_summary",
            "description": (
                "Fetch live pipeline metrics from the Deal Funnel board on Monday.com. "
                "Provides totals, stage breakdown, sector breakdown, and pipeline value. "
                "Use for questions like 'How's our pipeline?', 'What's the deal value this quarter?'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sector": {
                        "type": "string",
                        "description": "Optional: filter by sector name (e.g. 'Mining', 'Powerline', 'Energy'). Leave empty for all sectors.",
                    },
                    "quarter": {
                        "type": "string",
                        "description": "Optional: quarter filter like 'Q1 2026', 'Q3 2025', or 'current'.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_deals_list",
            "description": (
                "Fetch a filtered list of individual deals from Monday.com Deal Funnel board. "
                "Use when the user wants to see specific deals, not aggregate metrics."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sector": {"type": "string", "description": "Filter by sector (partial match)."},
                    "status": {"type": "string", "description": "Filter by deal status: Open, Closed, Won, Lost."},
                    "stage": {"type": "string", "description": "Filter by deal stage (partial match)."},
                    "owner": {"type": "string", "description": "Filter by owner code."},
                    "limit": {"type": "integer", "description": "Max records to return. Default 20."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_at_risk_deals",
            "description": (
                "Identify open deals that are at risk: low probability, overdue expected close date, or stalled stage. "
                "Use for 'Which deals are at risk?', 'What should we focus on?'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "value_threshold_inr": {
                        "type": "number",
                        "description": "Optional minimum deal value in INR to focus on high-value risks only.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_work_order_summary",
            "description": (
                "Fetch aggregate Work Order metrics from Monday.com: order value, billed, collected, AR, unbilled. "
                "Use for questions about work orders, executions, billing, or revenue from operations."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sector": {"type": "string", "description": "Optional sector filter."},
                    "status": {"type": "string", "description": "Optional execution status filter: Completed, In Progress, Not Started."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_accounts_receivable",
            "description": (
                "Fetch accounts receivable (AR) data from Work Orders board on Monday.com. "
                "Use for 'What's our AR?', 'Who owes us money?', 'Outstanding collections'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "priority_only": {"type": "boolean", "description": "If true, only return priority AR accounts."},
                    "sector": {"type": "string", "description": "Optional sector filter."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_revenue_by_sector",
            "description": (
                "Get revenue and deal value broken down by sector, from Deals and/or Work Orders boards. "
                "Use for sector performance, top sectors, or sector comparisons."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "enum": ["deals", "work_orders", "both"],
                        "description": "Which board(s) to pull from. Default 'both'.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_overdue_work_orders",
            "description": (
                "Fetch work orders that are overdue (end date passed) or due soon. "
                "Use for 'What's overdue?', 'Delivery risk', 'Execution delays'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "days_ahead": {
                        "type": "integer",
                        "description": "Include WOs due within N days from today. 0 = strictly overdue only.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_deals",
            "description": (
                "Free-text search across deal names, client codes, owner codes, sector, and stage. "
                "Use when looking for a specific deal or client."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search string."},
                },
                "required": ["query"],
            },
        },
    },
]


# ── Dispatcher ────────────────────────────────────────────────────────────────

TOOL_MAP = {
    "get_pipeline_summary": get_pipeline_summary,
    "get_deals_list": get_deals_list,
    "get_at_risk_deals": get_at_risk_deals,
    "get_work_order_summary": get_work_order_summary,
    "get_accounts_receivable": get_accounts_receivable,
    "get_revenue_by_sector": get_revenue_by_sector,
    "get_overdue_work_orders": get_overdue_work_orders,
    "search_deals": search_deals,
}


# ── Anthropic-format tool schemas ───────────────────────────────────────────
# Anthropic uses {"name", "description", "input_schema"} instead of the
# OpenAI {"type":"function","function":{...}} wrapper.

ANTHROPIC_TOOL_SCHEMAS = [
    {
        "name": s["function"]["name"],
        "description": s["function"]["description"],
        "input_schema": s["function"]["parameters"],
    }
    for s in TOOL_SCHEMAS
]


def dispatch_tool(name: str, arguments: str | dict) -> str:
    """
    Call the named tool with the given arguments (JSON string or dict).
    Returns a JSON string result suitable for tool_result content blocks.
    """
    if isinstance(arguments, str):
        kwargs = json.loads(arguments) if arguments.strip() else {}
    else:
        kwargs = arguments

    fn = TOOL_MAP.get(name)
    if fn is None:
        return json.dumps({"error": f"Unknown tool: {name}"})

    try:
        result = fn(**kwargs)
        return json.dumps(result, default=str)
    except Exception as exc:
        return json.dumps({"error": str(exc), "tool": name})
