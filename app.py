"""
Chainlit Chat UI for the Skylark BI Agent.

Run locally:    chainlit run app.py
Deploy:         Chainlit Cloud or any server with `chainlit run app.py --host 0.0.0.0`

Required environment variables (set in .env locally or server environment):
    MONDAY_API_KEY
    GROQ_API_KEY
    DEALS_BOARD_ID
    WORK_ORDERS_BOARD_ID
"""

import os
import json

import chainlit as cl
from dotenv import load_dotenv

load_dotenv()

from agent import run_agent, AgentResponse, ToolCallTrace


EXAMPLE_QUESTIONS = [
    "How's our pipeline looking right now?",
    "What's the deal value in the Mining sector?",
    "Which deals are at highest risk?",
    "Show me our total accounts receivable",
    "What work orders are overdue?",
    "Break down revenue by sector",
    "What's our unbilled amount across all work orders?",
    "Show open deals in Powerline with high probability",
]


@cl.on_chat_start
async def on_chat_start():
    """Initialise session and show welcome message with quick-action buttons."""
    cl.user_session.set("history", [])

    actions = [
        cl.Action(name="ask_example", payload={"question": q}, label=q)
        for q in EXAMPLE_QUESTIONS
    ]

    board_deals = os.environ.get("DEALS_BOARD_ID", "not set")
    board_wo = os.environ.get("WORK_ORDERS_BOARD_ID", "not set")

    await cl.Message(
        content=(
            "## Skylark BI Agent\n\n"
            "I have **live access** to your Monday.com boards and answer founder-level questions about:\n\n"
            "- **Pipeline** - deal values, stages, sector performance\n"
            "- **Risks** - at-risk deals, overdue work orders\n"
            "- **Revenue & AR** - billed, collected, outstanding\n"
            "- **Search** - find specific deals or clients\n\n"
            f"*Connected boards - Deals: `{board_deals}` | Work Orders: `{board_wo}`*\n\n"
            "**Try a suggested question or type your own:**"
        ),
        actions=actions,
    ).send()


@cl.action_callback("ask_example")
async def ask_example(action: cl.Action):
    await action.remove()
    await process_question(action.payload["question"])


@cl.on_message
async def on_message(message: cl.Message):
    await process_question(message.content)


async def process_question(question: str):
    """Run the agent for the given question and stream results into the chat."""
    history = cl.user_session.get("history", [])

    # Placeholder message shown while thinking
    thinking_msg = cl.Message(content="")
    await thinking_msg.send()

    # Run the async agent directly
    response: AgentResponse = await run_agent(question, history)

    # Render each tool call as a collapsible Step
    for trace in response.tool_traces:
        args_str = json.dumps(trace.arguments, indent=2) if trace.arguments else "{}"
        async with cl.Step(name=trace.tool_name, type="tool") as step:
            step.input = args_str
            step.output = f"{trace.result_summary}\n\n⏱ {trace.duration_ms} ms"

    # Update the placeholder with the final answer
    if response.error:
        thinking_msg.content = f"⚠️ **Error:** {response.error}"
    else:
        thinking_msg.content = response.answer or "I could not find an answer. Please try rephrasing."

    await thinking_msg.update()
