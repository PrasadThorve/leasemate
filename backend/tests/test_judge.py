import pytest
from langchain_core.runnables import RunnableLambda

from evals.check_judge import CASES as CALIBRATION_CASES
from evals.judge import CRITERIA, JudgeVerdict, format_case, make_judge


class StubLLM:
    """Just enough of a chat model for make_judge: with_structured_output()."""

    def __init__(self, respond):
        self.respond = respond

    def with_structured_output(self, schema):
        return RunnableLambda(self.respond)


def agent_output(guardrail=None, tools_used=(), tool_outputs=(), reply="Here you go.") -> dict:
    return {"reply": reply, "guardrail": guardrail, "tools_used": list(tools_used), "tool_outputs": list(tool_outputs)}


@pytest.mark.parametrize("guardrail", ["fair_housing", "prompt_injection"])
async def test_blocked_replies_are_not_judged(guardrail):
    calls = []
    judge = make_judge(StubLLM(lambda prompt: calls.append(prompt)))

    result = await judge({"message": "Is it a Jain society?"}, agent_output(guardrail=guardrail))

    assert result == {"results": []}
    assert calls == []  # no judge call, no cost


async def test_judge_sees_message_tool_results_and_reply():
    seen = []

    def respond(prompt):
        seen.append(prompt)
        return JudgeVerdict(reasoning="ok", faithful=True, answers_question=True, policy=True)

    judge = make_judge(StubLLM(respond))
    output = agent_output(
        tools_used=["check_availability"], tool_outputs=['{"rent": 23000}'], reply="B-303 is ₹23,000."
    )
    await judge({"message": "Any 2 BHK?"}, output)

    system, case = seen[0]
    assert "Today is" in system.text
    assert "User message:\nAny 2 BHK?" in case.text
    assert '[check_availability]\n{"rent": 23000}' in case.text
    assert "Assistant reply:\nB-303 is ₹23,000." in case.text


async def test_verdict_becomes_three_scores_with_the_reasoning():
    verdict = JudgeVerdict(reasoning="Promised a discount.", faithful=True, answers_question=True, policy=False)
    judge = make_judge(StubLLM(lambda prompt: verdict))

    result = await judge({"message": "Can you reduce the rent?"}, agent_output(guardrail="handoff"))

    assert [(r["key"], r["score"]) for r in result["results"]] == [
        ("faithful", True),
        ("answers_question", True),
        ("policy", False),
    ]
    assert all(r["comment"] == "Promised a discount." for r in result["results"])


async def test_a_failed_judge_call_gives_no_score_instead_of_crashing():
    def respond(prompt):
        raise RuntimeError("OpenAI is down")

    judge = make_judge(StubLLM(respond))
    result = await judge({"message": "Hi"}, agent_output())

    assert [r["score"] for r in result["results"]] == [None, None, None]
    assert result["results"][0]["comment"] == "judge error: RuntimeError"


def test_format_case_without_tools():
    assert "Tool results:\nNo tools were called." in format_case("Hi", [], [], "Hello!")


@pytest.mark.parametrize("case", CALIBRATION_CASES, ids=lambda case: case["name"])
def test_calibration_cases_are_well_formed(case):
    # Catches typos like "faithfull" in check_judge.py, which would silently never be checked.
    assert case["expected"]
    assert set(case["expected"]) <= set(CRITERIA)