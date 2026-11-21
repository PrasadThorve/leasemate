from datetime import datetime
from zoneinfo import ZoneInfo

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.agent.guardrails import (
    BLOCKED_CATEGORIES,
    FAIR_HOUSING_REPLY,
    HANDOFF_INSTRUCTION,
    PROMPT_INJECTION_REPLY,
    Classifier,
    handoff_done_this_turn,
    make_classifier,
)
from app.agent.mcp_tools import load_mcp_tools
from app.agent.prompts import SYSTEM_PROMPT
from app.config import settings
from db.database import SessionLocal
from db.models import Company

IST = ZoneInfo("Asia/Kolkata")


class LeaseMateState(MessagesState):
    # Set by the guard on every turn: None (allowed), "handoff", "fair_housing" or "prompt_injection".
    guardrail: str | None


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


def create_llm(model: str | None = None) -> ChatOpenAI:
    return ChatOpenAI(
        model=model or settings.openai_model,
        api_key=settings.openai_api_key,
        reasoning_effort=settings.openai_reasoning_effort,
    )


async def build_agent(
    company_id: int,
    llm: BaseChatModel | None = None,
    classify: Classifier | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """Build the agent for one company. `llm` and `classify` can be swapped for fakes in tests."""
    tools = await load_mcp_tools(settings.mcp_server_url, company_id)
    llm_with_tools = (llm or create_llm()).bind_tools(tools)
    classify = classify or make_classifier(create_llm(settings.guard_model))
    company_name = get_company_name(company_id)

    async def guard(state: LeaseMateState) -> dict:
        decision = await classify(state["messages"])
        return {"guardrail": None if decision.category == "allow" else decision.category}

    def route_after_guard(state: LeaseMateState) -> str:
        return "blocked" if state.get("guardrail") in BLOCKED_CATEGORIES else "agent"

    async def blocked(state: LeaseMateState) -> dict:
        template = FAIR_HOUSING_REPLY if state["guardrail"] == "fair_housing" else PROMPT_INJECTION_REPLY
        return {"messages": [AIMessage(template.format(company=company_name))]}

    async def call_model(state: LeaseMateState) -> dict:
        prompt = [SystemMessage(SYSTEM_PROMPT.format(company_name=company_name, now=current_time_text()))]
        if state.get("guardrail") == "handoff" and not handoff_done_this_turn(state["messages"]):
            prompt.append(SystemMessage(HANDOFF_INSTRUCTION))
        response = await llm_with_tools.ainvoke([*prompt, *state["messages"]])
        return {"messages": [response]}

    builder = StateGraph(LeaseMateState)
    builder.add_node("guard", guard)
    builder.add_node("blocked", blocked)
    builder.add_node("agent", call_model)
    builder.add_node("tools", ToolNode(tools))

    builder.add_edge(START, "guard")
    builder.add_conditional_edges("guard", route_after_guard, ["blocked", "agent"])
    builder.add_edge("blocked", END)
    builder.add_conditional_edges("agent", tools_condition)  # -> "tools", or END if no tool calls
    builder.add_edge("tools", "agent")

    return builder.compile(checkpointer=checkpointer or InMemorySaver())