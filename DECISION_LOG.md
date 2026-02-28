# Decision Log - Skylark Monday.com BI Agent

---

## 1. Tech Stack Choices

### LLM: Groq (`meta-llama/llama-4-scout-17b-16e-instruct`)

Several LLM providers were trialled during development due to free-tier credit exhaustion:

| Provider | Model | Outcome |
|---|---|---|
| OpenAI | gpt-4o-mini | Rate limit exhausted |
| Anthropic | claude-3-haiku | Credit exhausted |
| DeepSeek | deepseek-v3 | Credit exhausted |
| Google | gemini-2.0-flash | Billing enabled on project - free tier disabled |
| Groq | llama-4-scout-17b | **Selected** - free, 30K TPM, 500K TPD |

Groq was chosen as the final provider because:
- **Genuinely free** - 30,000 tokens per minute, 500,000 per day on the free tier
- **OpenAI-compatible API** - single `base_url` swap, no prompt changes
- **Tool calling support** - llama-4-scout handles function/tool schemas reliably
- **Fast inference** - LPU hardware, typically <1 s TTFT

One Groq-specific quirk: the model sends integer/boolean parameters as JSON strings (e.g. `"20"` instead of `20`). FastMCP validates schema before calling functions, so all numeric/bool tool parameters are typed as `str` in `mcp_server.py` and cast internally.

### Interface: Chainlit

Switched from Streamlit because:
- Purpose-built for LLM chat - native async, collapsible `Step` components for tool-call traces, proper message threading
- Built-in action buttons (`cl.Action`) for suggested questions
- `@cl.on_message` / `@cl.action_callback` decorators replace session-state boilerplate
- Tool call traces are visible by default with expand/collapse - satisfies the "visible action/tool-call trace" requirement

### Monday.com Integration: FastMCP + GraphQL

An MCP layer (`mcp_server.py`) wraps all Monday.com tools because:
- The same server runs inside Chainlit (via `agent.py` subprocess) AND works with Claude Desktop / Cursor with zero code changes
- Decouples the LLM driver from the data layer
- Every invocation is a fresh live API call - no caching

**Monday.com API version**: pinned to `2023-10`. Version `2024-01` removed the `title` field from `ColumnValue`, which broke column mapping. The `title` is now fetched separately via `columns { id title }` metadata query and injected at runtime.

---

## 2. Data Handling Decisions

### Column name normalisation

`import_boards.py` sanitises column titles before creating Monday.com columns (strips `/`, `(`, `)` to avoid API rejections). This means `Sector/service` → `Sectorservice` on the board. All field lookups in `tools.py` and `data_utils.py` use the sanitised names.

### Normalisation approach

Data is cleaned at query time inside `data_utils.py`, not at import time:
- Monetary values: strip `₹`, `$`, commas, whitespace → `float`
- Dates: `dateutil.parse` handles all observed formats → ISO `YYYY-MM-DD`
- Status strings: case-insensitive map covers `"in progress"`, `"In Progress"`, `"Ongoing"`, etc.
- Numbers stored as text (e.g. `"₹1,23,456"`) → float

### Filtering: client-side

Monday.com's GraphQL column-value filters are fragile with text fields and inconsistent casing. All filtering is done in Python after fetching the full board. With <500 rows per board this runs in <2 s and supports fuzzy/substring matching.

---

## 3. Agent Design Decisions

### Tool granularity: 8 specific tools

Rather than 1-2 generic "fetch everything" tools:
- The model selects tools more reliably when each has a clear, specific purpose
- Each tool accepts filters, reducing data returned to the LLM
- Traces are readable - the user sees exactly which tool was called with which arguments

### Token budget management

`llama-3.1-8b-instant` (6K TPM) was too small for the tool schemas + conversation history. Switched to `llama-4-scout-17b` (30K TPM). Additionally:
- Tool descriptions trimmed to single-line docstrings (~300 tokens saved per request)
- System prompt shortened to one sentence (~80 tokens saved)
- `max_tool_rounds=8` prevents runaway loops

### Conversation continuity

Full conversation history passed on every turn, enabling follow-up questions ("What about Mining specifically?") without restating context.

---

## 4. Assumptions Made

| Assumption | Reason |
|---|---|
| Masked deal/WO names are intentional | Excel uses codenames (Naruto, Sasuke) and masked company codes |
| "Closed" and "Won" are equivalent for won-deal metrics | The data uses both interchangeably |
| Financial values are in INR | Consistent with Indian company context |
| `Tentative Close Date` used for pipeline filtering, not `Close Date A` | 92% of `Close Date A` values are null |
| Work Order board data is limited | Column creation during import silently failed; WO tool responses reflect this honestly |

---

## 5. What I Would Add With More Time

- **Streaming responses** - Groq supports `stream=True`; Chainlit has `cl.Message.stream_token()` - answers would appear word-by-word
- **Chart generation** - plotly figures rendered inline in chat for pipeline/AR visualisations
- **Auth layer** - Chainlit's `@cl.password_auth_callback` for production use
- **WO board re-import** - column creation failed silently; with the original Excel a re-run of `import_boards.py` against the existing board ID would populate all work order fields
- **Webhook cache invalidation** - listen to Monday.com change events, invalidate board cache selectively for a "live but fast" hybrid


OpenAI's rate limit was exhausted during development. DeepSeek was chosen as the replacement because:
- **Free tier** - $2 pre-loaded credit, ~$0.14/M tokens (cache miss), essentially free for prototyping
- **OpenAI-compatible API** - same `base_url` swap, zero changes to prompt format or tool schemas
- **Strong tool-calling** - DeepSeek-V3 handles structured data retrieval reliably at `temperature=0.2`

### Interface: Chainlit

Streamlit was the original choice for speed of deployment. Switched to Chainlit because:
- Purpose-built for LLM chat apps - native async, collapsible `Step` components for tool traces, proper chat bubbles
- `@cl.on_message` / `@cl.action_callback` decorators replace Streamlit's session-state boilerplate
- Cleaner default UI with zero extra CSS

### Monday.com Integration: MCP (Model Context Protocol) + GraphQL API

Original approach used direct GraphQL calls from tool functions. Added an MCP layer (`mcp_server.py`) wrapping the same tools because:
- The same server works with Claude Desktop, Cursor, or any MCP-compatible client without code changes
- Decouples the LLM driver (`agent.py`) from the Monday.com data layer (`mcp_server.py`)
- Implements the bonus requirement from the assignment spec

All tools still make fresh live API calls on every invocation - no caching.

---

## 2. Data Handling Decisions

### Work Order Excel header location

The `Work_Order_Tracker Data.xlsx` file stores column headers in row 0 of the data (not in pandas' default header row). The import script detects this and reads with `header=None`, then promotes row 0 as columns.

### Normalisation approach

Rather than cleaning data before import (which would obscure the original messiness), I normalise at query time inside `data_utils.py`. This means:
- Monetary values: strip currency symbols, commas, whitespace → `float`
- Dates: `dateutil.parse` handles all observed formats → ISO `YYYY-MM-DD`
- Status strings: case-insensitive map handles `"in progress"`, `"In Progress"`, `"Ongoing"`, etc.
- Numbers stored as text (e.g. `"₹1,23,456"`) → cleaned to float

The agent communicates data-quality caveats when significant fields have high null rates (e.g. 52% of deal values are missing - noted in every pipeline summary).

### Filtering: client-side vs server-side

Monday.com's GraphQL API supports column-value filtering, but it's fragile with text fields and inconsistent casing. I fetch the full board and filter in Python. With <500 rows per board this is fast (<2 s) and lets me do fuzzy/substring matching that the API can't.

---

## 3. Agent Design Decisions

### Tool granularity

I defined 8 tools rather than 2 giant "fetch everything" tools, because:
- GPT-4o selects the right tool more reliably when tools have clear, specific purposes
- Each tool can be called with filters, reducing data passed back to the model
- Traces are readable - the user can see exactly what was queried

### Conversation history

Full conversation history is passed on each turn, enabling follow-up questions ("What about Mining specifically?" after a pipeline summary) without re-stating context.

### Safety caps

`max_tool_rounds=8` prevents runaway tool-calling loops. Each individual round also has a `timeout=30s` on the Monday.com HTTP request.

---

## 4. Assumptions Made

| Assumption | Reason |
|---|---|
| Masked deal/WO names are intentional and should remain masked | The Excel uses codenames (Naruto, Sasuke, etc.) and masked company codes |
| "Closed" and "Won" deal statuses are equivalent for won-deal metrics | The data uses both interchangeably |
| Financial values are in INR unless stated otherwise | Consistent with Indian company context |
| `Tentative Close Date` used for pipeline date filtering, not `Close Date (A)` | 92% of `Close Date (A)` values are null; tentative is the operational field |

---

## 5. What I Would Add With More Time

- **Streaming responses** - DeepSeek supports `stream=True`; Chainlit has native streaming via `cl.Message.stream_token()`, so the answer would appear word by word
- **Chart generation** - matplotlib/plotly visualisations rendered inline in the chat for pipeline and AR data
- **Webhook listener** - invalidate a board-specific cache when Monday.com sends a change event, giving a "live but fast" hybrid
- **Auth layer** - Chainlit's built-in auth (`@cl.password_auth_callback`) for production use
- **Claude Desktop config** - ship a ready-made `claude_desktop_config.json` so `mcp_server.py` can be used directly in Claude Desktop with zero extra setup
