# Deliverables — Skylark BI Agent

---

## 1. Hosted Prototype URL

🔗 **[https://skylark-bi-agent-vabf.onrender.com/](https://skylark-bi-agent-vabf.onrender.com/)**

---

## 2. Monday.com Board Links

| Board | Link |
|---|---|
| Deal Funnel (ID `5026904002`) | **[monday.com/boards/5026904002](https://nkambadkone515s-team.monday.com/boards/5026904002)** |
| Work Order Tracker (ID `5026906296`) | **[monday.com/boards/5026906296](https://nkambadkone515s-team.monday.com/boards/5026906296)** |


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
