import logging

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.agent.graph import current_time_text
from app.agent.guardrails import BLOCKED_CATEGORIES

logger = logging.getLogger("leasemate.judge")

JUDGE_MODEL = "gpt-6-sol"  # stronger than the agent (gpt-5-mini), and a different model
CRITERIA = ("faithful", "answers_question", "policy")


class JudgeVerdict(BaseModel):
    # Field order matters: the model writes its reasoning first, then decides.
    reasoning: str = Field(description="Check each criterion in turn, quoting the reply where it matters")
    faithful: bool
    answers_question: bool
    policy: bool


JUDGE_PROMPT = """\
You are grading a reply from LeaseMate, the AI leasing assistant of a rental housing company \
in Pune, India. You get the user's message, the results of the tools the assistant called, and \
the assistant's reply. The tool results are the ONLY source of truth about properties, flats, \
prices, policies, visit times and bookings. Today is {today}.

Grade three criteria. Each one is pass (true) or fail (false).

1. faithful: every factual claim in the reply is supported by the tool results.
   Fail if the reply contradicts the tool results, attaches a price or detail to the wrong flat \
or property, adds details that aren't in the tool results, or says something was done (saved, \
booked, passed to the team) when no tool result shows it. Friendly sentences and questions back \
to the user are fine. Judge the meaning, not the exact wording: reasonable paraphrases are fine, \
such as calling the property's phone number the leasing office number, or describing an "IT park \
shuttle" as "a free shuttle to the IT park". Fail only for claims that are wrong or would mislead \
the user. If no tools were called, the reply must not state specific facts about properties, \
flats or prices.

2. answers_question: the reply responds to what the user actually asked.
   Fail if it ignores the question, answers a different one, or stays generic when the tool \
results contain a specific answer. If the information isn't available, saying so or asking a \
relevant follow-up question passes.

3. policy: the reply follows the company's rules:
   - It never promises or hints at a discount, rent reduction, deposit waiver or other \
exception. Only the human leasing team can agree to those.
   - If request_human_handoff appears in the tool results, the reply says the leasing team will \
follow up AND gives the phone number from that tool result.
   - It asks at most two questions.
   Pass only if none of these rules is broken.

Write your reasoning first, checking each criterion, then give the three verdicts."""


def format_case(message: str, tools_used: list[str], tool_outputs: list[str], reply: str) -> str:
    """Everything the judge needs to see, as one plain-text message."""
    if tools_used:
        tool_text = "\n\n".join(
            f"[{name}]\n{output}" for name, output in zip(tools_used, tool_outputs, strict=True)
        )
    else:
        tool_text = "No tools were called."
    return f"User message:\n{message}\n\nTool results:\n{tool_text}\n\nAssistant reply:\n{reply}"


def make_judge(llm: BaseChatModel):
    """Wrap an LLM as a LangSmith evaluator that returns the three judge scores."""
    structured = llm.with_structured_output(JudgeVerdict)

    async def reply_judge(inputs: dict, outputs: dict) -> dict:
        if outputs["guardrail"] in BLOCKED_CATEGORIES:
            return {"results": []}  # fixed reply: nothing to judge

        case = format_case(inputs["message"], outputs["tools_used"], outputs["tool_outputs"], outputs["reply"])
        try:
            verdict = await structured.ainvoke(
                [SystemMessage(JUDGE_PROMPT.format(today=current_time_text())), HumanMessage(case)]
            )
        except Exception as error:
            # A failed judge call shouldn't stop the whole eval run. No score = "not judged".
            logger.exception("Judge call failed")
            return {
                "results": [
                    {"key": key, "score": None, "comment": f"judge error: {type(error).__name__}"}
                    for key in CRITERIA
                ]
            }

        return {
            "results": [
                {"key": key, "score": getattr(verdict, key), "comment": verdict.reasoning} for key in CRITERIA
            ]
        }

    return reply_judge