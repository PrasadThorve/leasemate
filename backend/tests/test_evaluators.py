"""Unit tests for the eval scorers in evals/evaluators.py.

If an evaluator is wrong, every eval score is wrong, so the evaluators get tests too.
"""
import pytest

from evals.evaluators import guardrail_correct, prices_grounded, rupee_amounts, tools_correct


def agent_output(reply: str = "", guardrail: str | None = None, tools_used=(), tool_outputs=()) -> dict:
    return {"reply": reply, "guardrail": guardrail, "tools_used": list(tools_used), "tool_outputs": list(tool_outputs)}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Rent is ₹22,000 per month.", {22000}),
        ("Rs. 22000, or INR 1,25,000 for the 3 BHK", {22000, 125000}),
        ("Around ₹22k a month", {22000}),
        ("A ₹1.2 lakh deposit", {120000}),
        ("Visits run 10 AM to 7 PM for the 2 BHK on floor 12.", set()),  # numbers, but no rupees
    ],
)
def test_rupee_amounts(text, expected):
    assert rupee_amounts(text) == expected


def test_guardrail_correct():
    assert guardrail_correct(agent_output(guardrail="handoff"), {"guardrail": "handoff"})["score"] is True

    result = guardrail_correct(agent_output(guardrail=None), {"guardrail": "fair_housing"})
    assert result["score"] is False
    assert result["comment"] == "expected fair_housing, got allow"


def test_tools_correct_accepts_alternatives_and_read_only_extras():
    output = agent_output(tools_used=["list_properties", "check_availability"])
    assert tools_correct(output, {"tools": ["get_property_details|check_availability"]})["score"] is True


def test_tools_correct_reports_missing_tools():
    result = tools_correct(agent_output(tools_used=["list_properties"]), {"tools": ["check_availability"]})
    assert result["score"] is False
    assert result["comment"] == "missing: check_availability"


def test_tools_correct_flags_writes_nobody_asked_for():
    output = agent_output(tools_used=["check_availability", "book_tour"])
    result = tools_correct(output, {"tools": ["check_availability"]})
    assert result["score"] is False
    assert result["comment"] == "unexpected write: book_tour"


TOOL_OUTPUT = '{"rent": 23000, "rent_display": "₹23,000", "security_deposit": 46000}'


def test_prices_from_tool_results_are_grounded():
    output = agent_output(
        reply="The 2 BHK is ₹23,000 a month with a ₹46,000 deposit.", tool_outputs=[TOOL_OUTPUT]
    )
    assert prices_grounded({"message": "2 BHK?"}, output)["score"] is True


def test_an_invented_price_is_caught():
    output = agent_output(reply="The 2 BHK is ₹21,500 a month.", tool_outputs=[TOOL_OUTPUT])
    result = prices_grounded({"message": "2 BHK?"}, output)
    assert result["score"] is False
    assert result["comment"] == "not found in any tool result: ₹21,500"


def test_prices_from_the_users_own_message_are_allowed():
    output = agent_output(reply="Nothing under ₹25,000 right now, sorry.")
    assert prices_grounded({"message": "Any 2 BHK under ₹25,000?"}, output)["score"] is True


def test_a_reply_without_prices_passes():
    result = prices_grounded({"message": "Hi"}, agent_output(reply="Hello! How can I help?"))
    assert result == {"key": "prices_grounded", "score": True, "comment": "no prices in the reply"}