# Decision Log - Skylark Monday.com BI Agent

**Candidate submission · AI Engineer Technical Assignment**

---

## 1. Tech Stack Choices

### LLM: DeepSeek-V3

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
