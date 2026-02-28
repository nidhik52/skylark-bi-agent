"""
Monday.com GraphQL API client.
Every call here is a live, real-time request – no caching, no pre-loading.
"""

import os
import time
import requests

MONDAY_API_URL = "https://api.monday.com/v2"
_MAX_ITEMS_PER_PAGE = 500


def _headers() -> dict:
    token = os.environ.get("MONDAY_API_KEY", "")
    if not token:
        raise RuntimeError("MONDAY_API_KEY environment variable is not set.")
    return {
        "Authorization": token,
        "Content-Type": "application/json",
        "API-Version": "2023-10",
    }


def run_query(query: str, variables: dict | None = None, _retries: int = 6) -> dict:
    """
    Execute a raw GraphQL query against Monday.com and return the response dict.
    Automatically retries on 429 Too Many Requests with exponential back-off.
    """
    payload: dict = {"query": query}
    if variables:
        payload["variables"] = variables

    wait = 5  # initial back-off seconds
    for attempt in range(_retries):
        resp = requests.post(MONDAY_API_URL, json=payload, headers=_headers(), timeout=30)

        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", wait))
            sleep_for = max(retry_after, wait)
            print(f"  Rate limited (429) - waiting {sleep_for}s before retry {attempt + 1}/{_retries}")
            time.sleep(sleep_for)
            wait *= 2  # exponential back-off
            continue

        resp.raise_for_status()
        data = resp.json()
        if "errors" in data:
            raise RuntimeError(f"Monday.com API error: {data['errors']}")
        return data

    raise RuntimeError("Monday.com API: exceeded retry limit due to rate limiting.")


def get_board_items(board_id: str | int) -> list[dict]:
    """
    Fetch ALL items from a board, handling Monday.com cursor-based pagination.
    Returns a list of item dicts:
        {
            "id": str,
            "name": str,
            "column_values": [{"id": str, "title": str, "text": str, "value": str}, ...]
        }
    """
    # Fetch column id -> title map first (the "title" field on ColumnValue was removed)
    col_meta_query = """
    query ($boardId: ID!) {
      boards(ids: [$boardId]) {
        columns { id title }
      }
    }
    """
    col_result = run_query(col_meta_query, {"boardId": str(board_id)})
    col_map: dict[str, str] = {
        c["id"]: c["title"]
        for c in col_result["data"]["boards"][0]["columns"]
    }

    items: list[dict] = []
    cursor: str | None = None

    while True:
        if cursor:
            query = """
            query ($boardId: ID!, $cursor: String!, $limit: Int!) {
              boards(ids: [$boardId]) {
                items_page(limit: $limit, cursor: $cursor) {
                  cursor
                  items {
                    id
                    name
                    column_values {
                      id
                      text
                      value
                    }
                  }
                }
              }
            }
            """
            variables = {"boardId": str(board_id), "cursor": cursor, "limit": _MAX_ITEMS_PER_PAGE}
        else:
            query = """
            query ($boardId: ID!, $limit: Int!) {
              boards(ids: [$boardId]) {
                items_page(limit: $limit) {
                  cursor
                  items {
                    id
                    name
                    column_values {
                      id
                      text
                      value
                    }
                  }
                }
              }
            }
            """
            variables = {"boardId": str(board_id), "limit": _MAX_ITEMS_PER_PAGE}

        result = run_query(query, variables)
        page = result["data"]["boards"][0]["items_page"]
        # Inject title from col_map so downstream code (items_to_records) works unchanged
        for item in page["items"]:
            for cv in item["column_values"]:
                cv["title"] = col_map.get(cv["id"], cv["id"])
        items.extend(page["items"])
        cursor = page.get("cursor")
        if not cursor:
            break
        time.sleep(0.2)  # be polite to the API

    return items


def get_board_metadata(board_id: str | int) -> dict:
    """Return board name and column definitions."""
    query = """
    query ($boardId: ID!) {
      boards(ids: [$boardId]) {
        name
        columns {
          id
          title
          type
        }
      }
    }
    """
    result = run_query(query, {"boardId": str(board_id)})
    board = result["data"]["boards"][0]
    return {"name": board["name"], "columns": board["columns"]}


def items_to_records(items: list[dict]) -> list[dict]:
    """
    Flatten Monday.com items into plain dicts keyed by column title.
    The item name is stored under 'Name'.
    """
    records = []
    for item in items:
        row: dict = {"_item_id": item["id"], "Name": item["name"]}
        for cv in item["column_values"]:
            row[cv["title"]] = cv["text"] if cv["text"] else None
        records.append(row)
    return records


def create_item(board_id: str | int, item_name: str, column_values: dict) -> str:
    """Create a single item on a board. Returns the new item's ID."""
    import json

    col_values_str = json.dumps(column_values)
    query = """
    mutation ($boardId: ID!, $itemName: String!, $colVals: JSON!) {
      create_item(board_id: $boardId, item_name: $itemName, column_values: $colVals) {
        id
      }
    }
    """
    result = run_query(
        query,
        {"boardId": str(board_id), "itemName": item_name, "colVals": col_values_str},
    )
    return result["data"]["create_item"]["id"]


def create_board(name: str, board_kind: str = "public") -> str:
    """Create a new board and return its ID."""
    query = """
    mutation ($name: String!, $kind: BoardKind!) {
      create_board(board_name: $name, board_kind: $kind) {
        id
      }
    }
    """
    result = run_query(query, {"name": name, "kind": board_kind})
    return result["data"]["create_board"]["id"]


def create_column(board_id: str | int, title: str, col_type: str) -> str:
    """
    Add a column to a board and return its ID.
    The column_type enum is inlined directly in the query (not passed as a variable)
    because Monday.com returns 400 when ColumnType is passed as a GraphQL variable.
    """
    # Sanitise: only allow known safe enum literals to prevent injection
    _VALID_TYPES = {
        "text", "numbers", "date", "status", "long_text", "email",
        "phone", "link", "rating", "checkbox", "dropdown", "timeline",
        "people", "tags", "country", "world_clock", "hour", "week",
        "boolean", "progress", "vote", "file",
    }
    safe_type = col_type if col_type in _VALID_TYPES else "text"
    # Inline the enum literal - no quotes around it in GraphQL
    query = f"""
    mutation ($boardId: ID!, $title: String!) {{
      create_column(board_id: $boardId, title: $title, column_type: {safe_type}) {{
        id
      }}
    }}
    """
    result = run_query(query, {"boardId": str(board_id), "title": title})
    return result["data"]["create_column"]["id"]
