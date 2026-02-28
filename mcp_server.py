"""
MCP Server for Skylark Monday.com BI tools.

Exposes all Monday.com data tools via the Model Context Protocol.
Can be used from:
  - Claude Desktop  (add to claude_desktop_config.json)
  - Cursor / VS Code Copilot / any MCP-compatible client
  - Chainlit app (agent.py launches it as a subprocess)

Run standalone:
    python mcp_server.py

Claude Desktop config example:
    {
      "mcpServers": {
        "skylark-bi": {
          "command": "python",
          "args": ["C:/path/to/skylark-bi-agent/mcp_server.py"],
          "env": {
            "MONDAY_API_KEY": "...",
            "DEALS_BOARD_ID": "...",
            "WORK_ORDERS_BOARD_ID": "..."
          }
        }
      }
    }
"""

import os
import sys
import json
from pathlib import Path

# Ensure the package root is on the path when run as a subprocess
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from dotenv import load_dotenv
# Load .env relative to this script, not the caller's CWD (important for Claude Desktop)
load_dotenv(_HERE / ".env")

from mcp.server.fastmcp import FastMCP
from tools import (
    get_pipeline_summary as _pipeline_summary,
    get_deals_list as _deals_list,
    get_at_risk_deals as _at_risk_deals,
    get_work_order_summary as _wo_summary,
    get_accounts_receivable as _ar,
    get_revenue_by_sector as _revenue_sector,
    get_overdue_work_orders as _overdue_wo,
    search_deals as _search_deals,
)

mcp = FastMCP("Skylark Monday.com BI")


def _j(obj) -> str:
    """Serialize result to JSON string."""
    return json.dumps(obj, default=str)


@mcp.tool()
def get_pipeline_summary(sector: str = "", quarter: str = "") -> str:
    """Pipeline metrics: totals, stage/sector breakdown, deal value. sector e.g. 'Mining'. quarter e.g. 'Q1 2026' or 'current'."""
    return _j(_pipeline_summary(
        sector=sector or None,
        quarter=quarter or None,
    ))


@mcp.tool()
def get_deals_list(
    sector: str = "",
    status: str = "",
    stage: str = "",
    owner: str = "",
    limit: str = "20",
) -> str:
    """List individual deals with filters. status: Open/Closed/Won/Lost. limit: max rows."""
    return _j(_deals_list(
        sector=sector or None,
        status=status or None,
        stage=stage or None,
        owner=owner or None,
        limit=int(limit),
    ))


@mcp.tool()
def get_at_risk_deals(value_threshold_inr: str = "0") -> str:
    """At-risk open deals: low probability, overdue close date, stalled stage. value_threshold_inr filters by min deal value."""
    v = float(value_threshold_inr)
    return _j(_at_risk_deals(
        value_threshold_inr=v or None,
    ))


@mcp.tool()
def get_work_order_summary(sector: str = "", status: str = "") -> str:
    """Work order metrics: order value, billed, collected, AR, unbilled. status: Completed/In Progress/Not Started."""
    return _j(_wo_summary(
        sector=sector or None,
        status=status or None,
    ))


@mcp.tool()
def get_accounts_receivable(priority_only: str = "false", sector: str = "") -> str:
    """Accounts receivable: outstanding collections. priority_only='true' for priority accounts only."""
    p = str(priority_only).lower() in ("true", "1", "yes")
    return _j(_ar(
        priority_only=p,
        sector=sector or None,
    ))


@mcp.tool()
def get_revenue_by_sector(source: str = "both") -> str:
    """Revenue and deal value by sector. source: 'deals', 'work_orders', or 'both'."""
    return _j(_revenue_sector(source=source))


@mcp.tool()
def get_overdue_work_orders(days_ahead: str = "0") -> str:
    """Overdue or soon-due work orders. days_ahead includes WOs due within N days."""
    return _j(_overdue_wo(days_ahead=int(days_ahead)))


@mcp.tool()
def search_deals(query: str) -> str:
    """Search deals by name, client code, owner, sector, or stage."""
    return _j(_search_deals(query=query))


if __name__ == "__main__":
    mcp.run(transport="stdio")
