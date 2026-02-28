# Skylark BI Agent

A conversational Business Intelligence agent for Monday.com — ask plain-English questions and get live, formatted answers backed by real board data.

Built with **Chainlit** (chat UI), **FastMCP** (tool protocol), and **Groq** (free LLM inference). No paid API credits required.

---

## Demo

> "Break down our pipeline by sector"
> "Which deals are at highest risk of slipping?"
> "Show open deals in Mining with high probability"
> "What's our total accounts receivable?"

The agent calls live Monday.com GraphQL queries for every question — no caching, no stale data.

---

## Architecture

```
Browser → Chainlit UI (app.py)
               ↓
          agent.py  ←→  Groq LLM (llama-4-scout-17b, free tier)
               ↓  MCP stdio
          mcp_server.py   (8 FastMCP tools)
               ↓
          tools.py  →  monday_client.py  →  Monday.com API
                              ├── Deal Funnel board
                              └── Work Order Tracker board
```

| Layer | Technology | Why |
|---|---|---|
| Chat UI | Chainlit 2.x | Fast to build, markdown rendering, action buttons |
| LLM | Groq `llama-4-scout-17b` | Free tier: 30K TPM / 500K TPD |
| Tool protocol | FastMCP (stdio) | Works with Claude Desktop + Cursor too |
| Data source | Monday.com GraphQL | Live board state, no ETL pipeline needed |

---

## Quick Start

### 1. Prerequisites

- Python 3.12+
- Monday.com account with API token
- Groq API key — free at [console.groq.com](https://console.groq.com)
- Two Monday.com boards (Deal Funnel + Work Order Tracker) — IDs in your `.env`

### 2. Install

```bash
git clone https://github.com/yourname/skylark-bi-agent.git
cd skylark-bi-agent
pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
```

Edit `.env`:

```env
MONDAY_API_KEY=your_monday_api_token
GROQ_API_KEY=your_groq_api_key
DEALS_BOARD_ID=5026904002
WORK_ORDERS_BOARD_ID=5026906296
```

### 4. Run

```bash
chainlit run app.py
```

Open **http://localhost:8000** — the agent is ready.

---

## Available Tools (MCP)

| Tool | What it answers |
|---|---|
| `get_pipeline_summary` | Total pipeline value, stage breakdown, sector split, win rate |
| `get_deals_list` | Filtered list of deals by sector / status / stage / owner |
| `get_at_risk_deals` | Overdue close dates, low probability, stalled stages |
| `get_work_order_summary` | Order value, billed, collected, unbilled |
| `get_accounts_receivable` | Outstanding AR by account / sector / priority |
| `get_revenue_by_sector` | Revenue breakdown across deals and work orders |
| `get_overdue_work_orders` | Work orders past their probable end date |
| `search_deals` | Free-text search across deal names, clients, owners, sectors |

---

## Using with Claude Desktop or Cursor (no Groq key needed)

The MCP server can be plugged directly into any MCP-compatible client — no Chainlit, no Groq required.

**Claude Desktop** — edit `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "skylark-bi": {
      "command": "python",
      "args": ["C:/path/to/skylark-bi-agent/mcp_server.py"],
      "env": {
        "MONDAY_API_KEY": "...",
        "DEALS_BOARD_ID": "5026904002",
        "WORK_ORDERS_BOARD_ID": "5026906296"
      }
    }
  }
}
```

Restart Claude Desktop — a plug icon confirms tools are loaded.

---

## One-time Board Import

If your Monday.com boards don't have data yet, place the Excel files in this directory and run:

```bash
python import_boards.py
```

Creates both boards, imports all rows, and prints the IDs to add to `.env`. Takes ~3 minutes. Only needed once.

---

## File Structure

```
skylark-bi-agent/
├── mcp_server.py        # FastMCP server — 8 Monday.com tools
├── tools.py             # Tool implementations (live Monday.com queries)
├── monday_client.py     # GraphQL API client with pagination + rate-limit retry
├── data_utils.py        # Data cleaning, normalisation, aggregation helpers
├── import_boards.py     # One-time: Excel → Monday.com board importer
├── agent.py             # Groq LLM agent loop (spawns mcp_server as subprocess)
├── app.py               # Chainlit UI
├── chainlit.md          # Chat welcome page
├── requirements.txt
├── .env.example
└── .gitignore
```

---

## Deployment

### Local (default)
```bash
chainlit run app.py
```

### Render (recommended for sharing)

1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → New → **Web Service** → connect GitHub repo
3. Runtime: **Docker** (auto-detected from `Dockerfile`)
4. Add environment variables (`MONDAY_API_KEY`, `GROQ_API_KEY`, `DEALS_BOARD_ID`, `WORK_ORDERS_BOARD_ID`) in the dashboard
5. Deploy — Render provides a public `*.onrender.com` URL

> Free tier note: the service spins down after 15 minutes of inactivity and cold-starts on the next request (~30 s). Fine for demos.

### Railway (alternative — requires paid plan)

1. Push this repo to GitHub
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Add environment variables in the Variables tab
4. Railway auto-detects the `Dockerfile`

> Railway's free trial is limited — a paid Hobby plan ($5/month) is required for persistent hosting.

### Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["python", "-m", "chainlit", "run", "app.py", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t skylark-bi-agent .
docker run -p 8000:8000 --env-file .env skylark-bi-agent
```

---

## Tech Stack

| | |
|---|---|
| Python | 3.12 |
| Chainlit | 2.x |
| FastMCP | 1.x |
| Groq SDK | via `openai` (OpenAI-compatible) |
| Monday.com | GraphQL API v2, API-Version 2023-10 |

---

## Notes

- **Work Order board**: column data requires re-import if the board was created without columns. See `import_boards.py`.
- **Rate limits**: Groq free tier is 30K TPM / 500K TPD on `llama-4-scout`. Swap the `model` in `agent.py` for any Groq model.
- **Data sensitivity**: deal values and client names on the boards are masked. The `.env` file is gitignored.


---

## Architecture

```
+--------------------------------------------------+
|  MCP Client (Claude Desktop / Cursor / etc.)     |
|  Uses YOUR existing subscription -- no API cost  |
+------------------+-------------------------------+
                   | MCP stdio transport
                   v
          mcp_server.py  <-- 8 Monday.com tools
                   |
                   v
            tools.py  ->  monday_client.py  ->  Monday.com API
                               |-- Deal Funnel board
                               +-- Work Order Tracker board
```

### Key design decisions

| Decision | Choice | Reason |
|---|---|---|
| Tool protocol | MCP (Model Context Protocol) | Works with Claude Desktop, Cursor, VS Code, any MCP client |
| LLM | Provided by MCP client | No API credits needed -- use your existing Claude/GPT subscription |
| Live data | No caching | Every tool call fetches fresh board state |
| Data cleaning | Runtime normalisation | Handles messy source data (nulls, mixed formats, currency strings) |

---

## Quick Start -- MCP Integration

No LLM API key needed. Uses Claude Desktop or Cursor with your existing subscription.

### 1 -- Install dependencies

```bash
pip install -r requirements.txt
```

### 2 -- Configure Claude Desktop

Edit `%APPDATA%\Claude\claude_desktop_config.json` (Windows) or `~/Library/Application Support/Claude/claude_desktop_config.json` (Mac):

```json
{
  "mcpServers": {
    "skylark-bi": {
      "command": "python",
      "args": ["C:/path/to/skylark-bi-agent/mcp_server.py"],
      "env": {
        "MONDAY_API_KEY": "your_monday_token",
        "DEALS_BOARD_ID": "5026904002",
        "WORK_ORDERS_BOARD_ID": "5026906296"
      }
    }
  }
}
```

Restart Claude Desktop -- a plug icon will appear confirming tools are loaded. You can then ask:
> "How is our pipeline looking?"   "Which deals are at risk?"   "Show me AR by sector"

### 3 -- Configure Cursor IDE

Open `Cursor Settings -> MCP` and add:

```json
{
  "skylark-bi": {
    "command": "python",
    "args": ["C:/path/to/skylark-bi-agent/mcp_server.py"],
    "env": {
      "MONDAY_API_KEY": "your_monday_token",
      "DEALS_BOARD_ID": "5026904002",
      "WORK_ORDERS_BOARD_ID": "5026906296"
    }
  }
}
```

---

## Optional -- Chainlit Chat UI

If you have a DeepSeek / OpenAI-compatible API key, a standalone chat interface is also available:

```bash
# Add DEEPSEEK_API_KEY to .env first
chainlit run app.py
```

Open http://localhost:8000. Uses the same MCP server under the hood.

---

## One-time Board Import

If the Monday.com boards do not exist yet, place the Excel files in `skylark-bi-agent/` and run:

```bash
python import_boards.py
```

Creates **Deal Funnel** and **Work Order Tracker** boards, imports ~520 rows, and prints the IDs. Takes ~3 minutes and only needs to run once.

---

## Available MCP Tools

| Tool | Description |
|---|---|
| `get_pipeline_summary` | Pipeline metrics -- value, stage breakdown, by sector/quarter |
| `get_deals_list` | Filtered list of individual deals |
| `get_at_risk_deals` | Deals with overdue close dates, low probability, or stalled stage |
| `get_work_order_summary` | Work order metrics -- order value, billed, collected, AR |
| `get_accounts_receivable` | Outstanding AR -- by account, sector, priority |
| `get_revenue_by_sector` | Revenue breakdown by sector (deals + work orders) |
| `get_overdue_work_orders` | Work orders past their probable end date |
| `search_deals` | Free-text search across deal/client names, sector, owner |

---

## File Structure

```
skylark-bi-agent/
|-- mcp_server.py                # * MCP server -- the main entry point
|-- tools.py                     # All 8 data-fetching functions
|-- monday_client.py             # Monday.com GraphQL API client
|-- data_utils.py                # Data cleaning & normalisation helpers
|-- import_boards.py             # One-time: Excel -> Monday.com boards
|-- app.py                       # Optional Chainlit chat UI
|-- agent.py                     # Optional DeepSeek LLM agent loop
|-- requirements.txt
|-- .env.example
+-- .gitignore
```

---

## Git

```bash
# Init (first time)
git init
git remote add origin https://github.com/yourname/skylark-bi-agent.git

# .env is already in .gitignore -- safe to push
git add .
git commit -m "initial commit"
git push -u origin main
```

> `.env` is excluded by `.gitignore`. Set env vars directly in the Claude Desktop config or use environment secrets for deployment.
