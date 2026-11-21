from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableLambda

from app.agent.guardrails import GuardDecision, handoff_done_this_turn, make_classifier, recent_transcript


def tool_call_message(name: str) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": {}, "id": "call_1"}])


def test_transcript_keeps_text_and_skips_tool_traffic():
    messages = [
        HumanMessage("Any 2 BHK in Hinjewadi?"),
        tool_call_message("check_availability"),
        ToolMessage('{"total_matches": 3}', tool_call_id="call_1", name="check_availability"),
        AIMessage("Yes, 3 flats from ₹22,000."),
    ]
    assert recent_transcript(messages) == "User: Any 2 BHK in Hinjewadi?\nAssistant: Yes, 3 flats from ₹22,000."


def test_transcript_keeps_only_the_latest_messages():
    messages = [HumanMessage(f"message {i}") for i in range(10)]
    assert recent_transcript(messages, max_messages=2) == "User: message 8\nUser: message 9"


def handoff_result(status: str = "success") -> ToolMessage:
    return ToolMessage("Handoff #1 created.", tool_call_id="call_1", name="request_human_handoff", status=status)


def test_handoff_done_this_turn():
    assert handoff_done_this_turn([HumanMessage("I want a discount"), handoff_result()])


def test_failed_handoff_does_not_count():
    assert not handoff_done_this_turn([HumanMessage("I want a discount"), handoff_result(status="error")])


def test_handoff_from_an_earlier_turn_does_not_count():
    messages = [HumanMessage("I want a discount"), handoff_result(), AIMessage("Done."), HumanMessage("Me again")]
    assert not handoff_done_this_turn(messages)


class StubLLM:
    """Just enough of a chat model for make_classifier: with_structured_output()."""

    def __init__(self, respond):
        self.respond = respond

    def with_structured_output(self, schema):
        return RunnableLambda(self.respond)


async def test_classifier_returns_the_models_decision():
    seen = []

    def respond(prompt):
        seen.append(prompt[-1].text)
        return GuardDecision(category="handoff", reason="wants a discount")

    classify = make_classifier(StubLLM(respond))
    decision = await classify([HumanMessage("Can you reduce the deposit?")])

    assert decision.category == "handoff"
    assert "User: Can you reduce the deposit?" in seen[0]  # the classifier saw the transcript


async def test_classifier_fails_open_when_the_model_is_down():
    def respond(prompt):
        raise RuntimeError("OpenAI is down")

    classify = make_classifier(StubLLM(respond))
    decision = await classify([HumanMessage("Hi")])

    assert decision.category == "allow"
    assert decision.reason == "classifier unavailable"