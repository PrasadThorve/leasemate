"""The LeaseMate agent, built as a LangGraph graph.

    START -> agent --(LLM asked for tools?)--> tools -> agent -> ... -> END
                   \\--(no tool calls: final answer)--> END

- "agent" node: calls the LLM with the system prompt + conversation so far.
- "tools" node: runs whatever tools the LLM asked for and adds their results.
- The loop repeats until the LLM answers without asking for a tool.
- The checkpointer saves each conversation's messages under a thread_id, so the
  agent remembers earlier turns of the same chat.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.agent.mcp_tools import load_mcp_tools
from app.agent.prompts import SYSTEM_PROMPT
from app.config import settings
from db.database import SessionLocal
from db.models import Company

IST = ZoneInfo("Asia/Kolkata")


def get_company_name(company_id: int) -> str:
    with SessionLocal() as session:
        company = session.get(Company, company_id)
        if company is None:
            raise ValueError(f"Unknown company id {company_id}")
        return company.name


def current_time_text() -> str:
    """e.g. 'Friday, 20 November 2026, 3:45 PM'."""
    now = datetime.now(IST)
    return f"{now:%A}, {now.day} {now:%B %Y}, {now.strftime('%I:%M %p').lstrip('0')}"


def create_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        reasoning_effort=settings.openai_reasoning_effort,
    )


async def build_agent(
    company_id: int,
    llm: BaseChatModel | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """Build the agent for one company. `llm` can be swapped for a fake model in tests."""
    tools = await load_mcp_tools(settings.mcp_server_url, company_id)
    llm_with_tools = (llm or create_llm()).bind_tools(tools)
    company_name = get_company_name(company_id)

    async def call_model(state: MessagesState) -> dict:
        system = SystemMessage(SYSTEM_PROMPT.format(company_name=company_name, now=current_time_text()))
        response = await llm_with_tools.ainvoke([system, *state["messages"]])
        return {"messages": [response]}

    builder = StateGraph(MessagesState)
    builder.add_node("agent", call_model)
    builder.add_node("tools", ToolNode(tools))
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", tools_condition)  # -> "tools", or END if no tool calls
    builder.add_edge("tools", "agent")

    return builder.compile(checkpointer=checkpointer or InMemorySaver())