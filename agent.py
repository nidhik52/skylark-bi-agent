"""
Monday.com BI Agent - Groq LLM + MCP tool protocol.

Architecture:
  1. On first call, spawn mcp_server.py as a subprocess and connect via stdio.
  2. List available tools from the MCP server; convert to OpenAI function-call format.
  3. Send user message + tools to Groq (OpenAI-compatible endpoint).
  4. If tool_calls returned, call each via MCP session.call_tool().
  5. Feed results back; repeat until Groq returns a final text answer.
"""

from __future__ import annotations
import os
import sys
import json
import time
from dataclasses import dataclass, field
from contextlib import AsyncExitStack

from openai import AsyncOpenAI
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

# -- Groq client (OpenAI-compatible) --------------------------------------

def _llm_client() -> AsyncOpenAI:
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        raise RuntimeError("GROQ_API_KEY environment variable is not set.")
    return AsyncOpenAI(
        api_key=key,
        base_url="https://api.groq.com/openai/v1",
    )


# -- Trace data structures ---------------------------------------------------

@dataclass
class ToolCallTrace:
    tool_name: str
    arguments: dict
    result_summary: str
    result_full: str
    duration_ms: int

@dataclass
class AgentResponse:
    answer: str
    tool_traces: list[ToolCallTrace] = field(default_factory=list)
    error: str | None = None


# -- MCP connection (singleton, lazily initialised) -------------------------

_exit_stack: AsyncExitStack | None = None
_mcp_session: ClientSession | None = None
_cached_tool_schemas: list[dict] | None = None


async def _get_mcp() -> tuple[ClientSession, list[dict]]:
    """Return (session, openai_tool_schemas), starting the MCP server if needed."""
    global _exit_stack, _mcp_session, _cached_tool_schemas

    if _mcp_session is None:
        server_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp_server.py")
        env = dict(os.environ)
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[server_script],
            env=env,
        )
        _exit_stack = AsyncExitStack()
        read, write = await _exit_stack.enter_async_context(stdio_client(server_params))
        _mcp_session = await _exit_stack.enter_async_context(ClientSession(read, write))
        await _mcp_session.initialize()

        # Fetch tool list once and convert to OpenAI function-call format
        # Strip extra JSON Schema meta-fields ($schema, title, $defs) that
        # DeepSeek/OpenAI API validation does not accept.
        tools_result = await _mcp_session.list_tools()
        _cached_tool_schemas = []
        for t in tools_result.tools:
            params = dict(t.inputSchema)
            params.pop("$schema", None)
            params.pop("title", None)
            # Clean titles from individual properties too
            for prop in params.get("properties", {}).values():
                if isinstance(prop, dict):
                    prop.pop("title", None)
            _cached_tool_schemas.append({
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description or "",
                    "parameters": params,
                },
            })

    return _mcp_session, _cached_tool_schemas


# -- System prompt ----------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are a BI assistant for an aerial survey company. "
    "Use MCP tools to fetch LIVE Monday.com data — never invent numbers. "
    "Be concise. Format with Markdown. Use INR crores/lakhs. Today: {today}."
)


def _system_prompt() -> str:
    from datetime import date
    return _SYSTEM_PROMPT.replace("{today}", date.today().strftime("%B %d, %Y"))


# -- Formatting helpers -----------------------------------------------------

def _summarise_result(tool_name: str, result_json: str) -> str:
    try:
        data = json.loads(result_json)
    except Exception:
        return result_json[:200]
    if "error" in data:
        return "Error: " + str(data.get("error", ""))
    key_map = {
        "get_pipeline_summary": lambda d: f"{d.get('filtered_deals', '?')} deals, pipeline Rs.{d.get('open_pipeline_value_inr') or 0:,.0f}",
        "get_deals_list": lambda d: f"{d.get('total_matching', '?')} deals found",
        "get_at_risk_deals": lambda d: f"{d.get('at_risk_count', '?')} deals at risk",
        "get_work_order_summary": lambda d: f"{d.get('filtered_wos', '?')} WOs, total Rs.{d.get('total_order_value_excl_gst') or 0:,.0f}",
        "get_accounts_receivable": lambda d: f"Total AR Rs.{d.get('total_ar_inr') or 0:,.0f}, {d.get('ar_record_count', '?')} accounts",
        "get_revenue_by_sector": lambda d: "Sectors: " + ", ".join(list((d.get("deals") or d.get("work_orders") or {}).keys())[:5]),
        "get_overdue_work_orders": lambda d: f"{d.get('overdue_count', '?')} overdue work orders",
        "search_deals": lambda d: f"{d.get('match_count', '?')} matches",
    }
    fn = key_map.get(tool_name)
    if fn:
        try:
            return fn(data)
        except Exception:
            pass
    return json.dumps(data)[:200]


# -- Agent loop -------------------------------------------------------------

async def run_agent(
    user_message: str,
    conversation_history: list[dict],
    model: str = "meta-llama/llama-4-scout-17b-16e-instruct",
    max_tool_rounds: int = 8,
) -> AgentResponse:
    """
    Run one turn of the BI agent.

    Args:
        user_message:          Latest user message.
        conversation_history:  Prior messages (user/assistant text pairs). Updated in-place.
        model:                 Groq model name.
        max_tool_rounds:       Maximum tool-calling iterations.

    Returns:
        AgentResponse with the final answer and tool trace.
    """
    try:
        session, tool_schemas = await _get_mcp()
    except Exception as exc:
        return AgentResponse(answer="", error=f"MCP server error: {exc}")

    client = _llm_client()
    traces: list[ToolCallTrace] = []

    messages: list[dict] = [{"role": "system", "content": _system_prompt()}]
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_message})

    for _round in range(max_tool_rounds):
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tool_schemas,
                tool_choice="auto",
                temperature=0.2,
            )
        except Exception as exc:
            return AgentResponse(answer="", error=f"LLM API error: {exc}")

        msg = response.choices[0].message

        # No tool calls -> final answer
        if not msg.tool_calls:
            answer = msg.content or ""
            conversation_history.append({"role": "user", "content": user_message})
            conversation_history.append({"role": "assistant", "content": answer})
            return AgentResponse(answer=answer, tool_traces=traces)

        # Append assistant message with tool_calls
        messages.append(msg.model_dump(exclude_none=True))

        # Execute each tool call via MCP
        tool_results = []
        for tc in msg.tool_calls:
            tool_name = tc.function.name
            try:
                args = json.loads(tc.function.arguments) if tc.function.arguments else {}
            except Exception:
                args = {}

            t0 = time.perf_counter()
            try:
                mcp_result = await session.call_tool(tool_name, args)
                # MCP result content is a list of content blocks
                if mcp_result.content:
                    result_json = mcp_result.content[0].text
                else:
                    result_json = json.dumps({"error": "empty result"})
            except Exception as exc:
                result_json = json.dumps({"error": str(exc)})
            elapsed_ms = int((time.perf_counter() - t0) * 1000)

            summary = _summarise_result(tool_name, result_json)
            traces.append(ToolCallTrace(
                tool_name=tool_name,
                arguments=args,
                result_summary=summary,
                result_full=result_json,
                duration_ms=elapsed_ms,
            ))

            tool_results.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result_json,
            })

        messages.extend(tool_results)

    return AgentResponse(
        answer="I reached the maximum number of tool calls. Please try a more specific query.",
        tool_traces=traces,
    )
