# Deliverables — Skylark BI Agent

---

## 1. Hosted Prototype URL

> ⏳ Build in progress on Render — update this link once deploy completes.

🔗 **`https://skylark-bi-agent.onrender.com`** *(placeholder — replace with actual Render URL)*

---

## 2. Monday.com Board Links

| Board | Link |
|---|---|
| Deal Funnel (ID `5026904002`) | *(paste `view.monday.com/...` share link here)* |
| Work Order Tracker (ID `5026906296`) | *(paste `view.monday.com/...` share link here)* |

To generate: open each board in Monday.com → **Share** → **Create shareable link**.

---

## 3. Visible Tool-Call Trace

Tool calls are shown inline in the Chainlit UI as collapsible **Steps** (powered by `cl.Step`).  
Each step displays:
- Tool name called (e.g. `get_work_order_summary`)
- Arguments passed (e.g. `{"sector": "Mining"}`)
- Raw JSON response from Monday.com

No extra configuration needed — traces appear automatically on every agent response.

---

## 4. Decision Log (≤ 2 pages)

📄 [`DECISION_LOG.md`](DECISION_LOG.md)

Also available on GitHub:  
🔗 https://github.com/nidhik52/skylark-bi-agent/blob/main/DECISION_LOG.md

Covers:
- LLM provider selection (Groq over OpenAI / Anthropic / DeepSeek / Gemini)
- Hosting platform selection (Render over Railway — free trial expiry)
- Chainlit over Streamlit
- FastMCP tool protocol design
- Column name normalisation approach
- Groq-specific tool parameter quirk

---

## 5. Source Code ZIP + README

📦 **`skylark-bi-agent.zip`** — included in submission

📄 [`README.md`](README.md) — quick-start, architecture diagram, tool reference, deployment guide

🔗 GitHub repo: https://github.com/nidhik52/skylark-bi-agent

---

## Checklist

| # | Deliverable | Status |
|---|---|---|
| 1 | Hosted prototype URL | ⏳ Render building |
| 2 | Monday.com board share links | ⏳ Manual — generate from board Share menu |
| 3 | Visible tool-call trace | ✅ Chainlit `cl.Step` (live in app) |
| 4 | Decision Log ≤ 2 pages | ✅ `DECISION_LOG.md` |
| 5 | Source ZIP + README | ✅ `skylark-bi-agent.zip` + `README.md` |
