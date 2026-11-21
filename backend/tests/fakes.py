from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from app.agent.guardrails import HANDOFF_INSTRUCTION, GuardDecision


class FakeLLM(BaseChatModel):
    """Pretends to be the agent's LLM. Counts how many times it was called."""

    calls: int = 0

    @property
    def _llm_type(self) -> str:
        return "fake-leasing-llm"

    def bind_tools(self, tools, **kwargs):
        return self  # the fake already knows our tool names

    def _generate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.calls += 1
        return ChatResult(generations=[ChatGeneration(message=self._reply(messages))])

    def _reply(self, messages: list[BaseMessage]) -> AIMessage:
        last = messages[-1]

        # A tool just ran: answer in words (like the real model does after a tool result).
        if isinstance(last, ToolMessage):
            if last.status == "error":
                return AIMessage(f"Sorry, that didn't work: {last.text}")
            return AIMessage(f"Here's what I found using {last.name}.")

        # The graph added the handoff instruction: obey it.
        if any(isinstance(m, SystemMessage) and m.text == HANDOFF_INSTRUCTION for m in messages):
            return self._tool_call(
                "request_human_handoff", reason="negotiation", summary="The prospect wants a lower rent."
            )

        text = last.text.lower()
        if "properties" in text:
            return self._tool_call("list_properties")
        if "2 bhk" in text:
            return self._tool_call("check_availability", bedrooms=2)
        if "phone" in text:
            # Deliberately invalid, to test how failed tools are handled.
            return self._tool_call(
                "create_guest_card", property_id=1, first_name="Asha", last_name="Patil", phone="12345"
            )
        return AIMessage("Hello! How can I help you find a home?")

    def _tool_call(self, name: str, **args) -> AIMessage:
        return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"call_{self.calls}"}])


async def fake_classify(messages: list[BaseMessage]) -> GuardDecision:
    """Pretends to be the guard classifier, using keywords from the latest user message."""
    text = next(m for m in reversed(messages) if isinstance(m, HumanMessage)).text.lower()
    if "ignore your instructions" in text or "system prompt" in text:
        return GuardDecision(category="prompt_injection", reason="tries to change the rules")
    if "vegetarian" in text or "bachelors" in text:
        return GuardDecision(category="fair_housing", reason="asks to filter by food habits or marital status")
    if "discount" in text or "human" in text:
        return GuardDecision(category="handoff", reason="negotiation or wants a person")
    return GuardDecision(category="allow", reason="normal leasing question")