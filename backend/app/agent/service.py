import asyncio
import uuid
from dataclasses import dataclass

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.state import CompiledStateGraph

from app.agent.graph import build_agent


class ToolsUnavailableError(Exception):
    """The MCP server couldn't be reached, so the agent can't be built."""


@dataclass
class ChatTurn:
    thread_id: str
    reply: str
    tools_used: list[str]
    guardrail: str | None


class AgentService:
    def __init__(self) -> None:
        # InMemorySaver forgets everything when the server restarts. Fine for a demo;
        # production would use a database-backed checkpointer (e.g. Postgres).
        self._checkpointer = InMemorySaver()
        self._agents: dict[int, CompiledStateGraph] = {}
        self._lock = asyncio.Lock()

    async def _get_agent(self, company_id: int) -> CompiledStateGraph:
        if company_id not in self._agents:
            # The lock stops two simultaneous first requests from building the agent twice.
            async with self._lock:
                if company_id not in self._agents:
                    try:
                        self._agents[company_id] = await build_agent(
                            company_id, checkpointer=self._checkpointer
                        )
                    except RuntimeError as error:  # FastMCP: "Client failed to connect"
                        raise ToolsUnavailableError(str(error)) from error
        return self._agents[company_id]

    @staticmethod
    def _run_config(company_id: int, thread_id: str, channel: str) -> dict:
        return {
            "configurable": {"thread_id": f"{company_id}:{thread_id}"},
            # These show up in LangSmith, so traces can be filtered by company and channel.
            "run_name": "leasemate_chat",
            "tags": [channel],
            "metadata": {"thread_id": thread_id, "company_id": company_id, "channel": channel},
        }

    async def chat(
        self, company_id: int, message: str, thread_id: str | None = None, channel: str = "web"
    ) -> ChatTurn:
        """Send one message and get the agent's reply. No thread_id = new conversation."""
        thread_id = thread_id or str(uuid.uuid4())
        agent = await self._get_agent(company_id)
        result = await agent.ainvoke(
            {"messages": [HumanMessage(message)]},
            self._run_config(company_id, thread_id, channel),
        )

        messages = result["messages"]
        last_question = max(i for i, m in enumerate(messages) if isinstance(m, HumanMessage))
        tools_used = [
            m.name
            for m in messages[last_question:]
            if isinstance(m, ToolMessage) and m.status != "error"  # don't show failed tools as done
        ]
        return ChatTurn(
            thread_id=thread_id,
            reply=messages[-1].text,
            tools_used=tools_used,
            guardrail=result.get("guardrail"),
        )

    async def history(self, company_id: int, thread_id: str) -> list[tuple[str, str]]:
        """The visible conversation so far: (role, text) pairs, without tool calls."""
        agent = await self._get_agent(company_id)
        state = await agent.aget_state(self._run_config(company_id, thread_id, "web"))
        messages = state.values.get("messages", []) if state.values else []

        visible = []
        for message in messages:
            if isinstance(message, HumanMessage):
                visible.append(("user", message.text))
            elif isinstance(message, AIMessage) and not message.tool_calls and message.text:
                visible.append(("assistant", message.text))
        return visible