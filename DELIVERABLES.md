# Deliverables — Skylark BI Agent

---

## 1. Hosted Prototype URL

🔗 **<a href="https://skylark-bi-agent-vabf.onrender.com/" target="_blank" rel="noopener noreferrer">https://skylark-bi-agent-vabf.onrender.com/</a>**

---

## 2. Monday.com Board Links

| Board | Link |
|---|---|
| Deal Funnel (ID `5026904002`) | **<a href="https://nkambadkone515s-team.monday.com/boards/5026904002" target="_blank" rel="noopener noreferrer">monday.com/boards/5026904002</a>** |
| Work Order Tracker (ID `5026906296`) | **<a href="https://nkambadkone515s-team.monday.com/boards/5026906296" target="_blank" rel="noopener noreferrer">monday.com/boards/5026906296</a>** |


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
🔗 <a href="https://github.com/nidhik52/skylark-bi-agent/blob/main/DECISION_LOG.md" target="_blank" rel="noopener noreferrer">https://github.com/nidhik52/skylark-bi-agent/blob/main/DECISION_LOG.md</a>

Covers:
- LLM provider selection (Groq over OpenAI / Anthropic / DeepSeek / Gemini)
- Hosting platform selection (Render over Railway — free trial expiry)
- Chainlit over Streamlit
- FastMCP tool protocol design
- Column name normalisation approach
- Groq-specific tool parameter quirk

---

## 5. Source Code ZIP + README

📦 **<a href="https://github.com/nidhik52/skylark-bi-agent/raw/main/skylark-bi-agent.zip" target="_blank" rel="noopener noreferrer">skylark-bi-agent.zip</a>** — download directly from GitHub

📄 <a href="https://github.com/nidhik52/skylark-bi-agent/blob/main/README.md" target="_blank" rel="noopener noreferrer">README.md</a> — quick-start, architecture diagram, tool reference, deployment guide

🔗 GitHub repo: <a href="https://github.com/nidhik52/skylark-bi-agent" target="_blank" rel="noopener noreferrer">https://github.com/nidhik52/skylark-bi-agent</a>

---
