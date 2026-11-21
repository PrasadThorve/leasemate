import os
import shutil
import tempfile
from pathlib import Path

# Must happen before the app imports, because db/database.py reads it on import.
TEMP_DIR = Path(tempfile.mkdtemp(prefix="leasemate-evals-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(TEMP_DIR / 'eval.db').as_posix()}"
os.environ["DEFAULT_COMPANY_ID"] = "1"  # every case is for Sahyadri Rental Communities

import argparse  # noqa: E402
import asyncio  # noqa: E402
import uuid  # noqa: E402
from collections import defaultdict  # noqa: E402

from fastmcp import Client  # noqa: E402
from langchain_core.messages import HumanMessage, ToolMessage  # noqa: E402
from langsmith import Client as LangSmithClient  # noqa: E402
from langsmith import aevaluate  # noqa: E402
from langsmith.schemas import Example  # noqa: E402

from app.agent import mcp_tools  # noqa: E402
from app.agent.graph import build_agent, create_llm  # noqa: E402
from app.agent.guardrails import make_classifier  # noqa: E402
from app.config import settings  # noqa: E402
from db.database import engine  # noqa: E402
from db.seed import seed  # noqa: E402
from evals.dataset import CASES, DATASET_NAME, to_example  # noqa: E402
from evals.evaluators import guardrail_correct, prices_grounded, tools_correct  # noqa: E402
from evals.judge import JUDGE_MODEL, make_judge  # noqa: E402
from mcp_server.server import mcp  # noqa: E402

COMPANY_ID = 1
CODE_EVALUATORS = [guardrail_correct, tools_correct, prices_grounded]


def use_in_memory_mcp() -> None:
    """Point the agent's tools at the MCP server in this process (no server on port 8001 needed)."""
    mcp_tools._mcp_client = lambda url, company_id: Client(mcp)


def ensure_dataset(client: LangSmithClient) -> None:
    """Upload the cases to LangSmith, only the first time this dataset name is used."""
    if client.has_dataset(dataset_name=DATASET_NAME):
        return
    dataset = client.create_dataset(
        DATASET_NAME, description="LeaseMate agent: guardrail decisions, tool use and grounded prices"
    )
    client.create_examples(dataset_id=dataset.id, examples=[to_example(case) for case in CASES])
    print(f"Created LangSmith dataset '{DATASET_NAME}' with {len(CASES)} cases.")


def local_examples() -> list[Example]:
    """The same cases as LangSmith Example objects, for --no-upload runs."""
    dataset_id = uuid.uuid4()
    return [
        Example(
            id=uuid.uuid4(),
            dataset_id=dataset_id,
            inputs=example["inputs"],
            outputs=example["reference_outputs"],
            metadata=example["metadata"],
        )
        for example in map(to_example, CASES)
    ]


async def make_target(model: str, guard_model: str):
    """Build the real agent once, and return the function LangSmith calls for each case."""
    agent = await build_agent(
        COMPANY_ID, llm=create_llm(model), classify=make_classifier(create_llm(guard_model))
    )

    async def run_agent(inputs: dict) -> dict:
        # Every case is a brand-new conversation, so cases can't affect each other.
        config = {"configurable": {"thread_id": str(uuid.uuid4())}}
        result = await agent.ainvoke({"messages": [HumanMessage(inputs["message"])]}, config)
        tool_results = [m for m in result["messages"] if isinstance(m, ToolMessage) and m.status != "error"]
        return {
            "reply": result["messages"][-1].text,
            "guardrail": result.get("guardrail"),
            "tools_used": [m.name for m in tool_results],
            "tool_outputs": [m.text for m in tool_results],
        }

    return run_agent


def print_summary(rows: list[dict]) -> None:
    """Pass rate per score, then every failure with its reason."""
    passed: dict[str, list[bool]] = defaultdict(list)
    not_scored: dict[str, int] = defaultdict(int)
    failures = []
    for row in rows:
        message = row["example"].inputs["message"]
        category = (row["example"].metadata or {}).get("category", "")
        for result in row["evaluation_results"]["results"]:
            if result.score is None:  # e.g. the judge call failed
                not_scored[result.key] += 1
                continue
            ok = bool(result.score)
            passed[result.key].append(ok)
            if not ok:
                failures.append(f"  [{category}] {result.key}: {message!r}\n      -> {result.comment}")

    print(f"\nResults ({len(rows)} cases; the judge skips blocked ones)")
    for key, oks in passed.items():
        errors = f"  ({not_scored[key]} not scored)" if not_scored[key] else ""
        print(f"  {key:<18} {sum(oks):>3}/{len(oks):<3} {sum(oks) / len(oks):.0%}{errors}")
    print("\nFailures:" if failures else "\nNo failures.")
    print("\n".join(failures))


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run the LeaseMate evals with the real models.")
    parser.add_argument("--model", default=settings.openai_model, help="model for the agent")
    parser.add_argument(
        "--guard-model", default=settings.guard_model or settings.openai_model, help="model for the guard"
    )
    parser.add_argument("--judge-model", default=JUDGE_MODEL, help="model for the LLM judge")
    parser.add_argument("--no-judge", action="store_true", help="skip the LLM judge (cheaper and faster)")
    parser.add_argument("--no-upload", action="store_true", help="don't save the dataset or results to LangSmith")
    args = parser.parse_args()
    upload = not args.no_upload

    if upload and not os.getenv("LANGSMITH_API_KEY"):
        raise SystemExit("LANGSMITH_API_KEY isn't set in backend/.env. Add it, or run with --no-upload.")

    seed()
    use_in_memory_mcp()
    target = await make_target(args.model, args.guard_model)
    evaluators = list(CODE_EVALUATORS)
    if not args.no_judge:
        evaluators.append(make_judge(create_llm(args.judge_model)))

    client = None
    if upload:
        client = LangSmithClient()
        ensure_dataset(client)

    judge = "off" if args.no_judge else args.judge_model
    print(f"Running {len(CASES)} cases: agent={args.model}, guard={args.guard_model}, judge={judge}")
    results = await aevaluate(
        target,
        data=DATASET_NAME if upload else local_examples(),
        evaluators=evaluators,
        experiment_prefix=f"{args.model}-guard-{args.guard_model}",
        metadata={
            "model": args.model,
            "guard_model": args.guard_model,
            "judge_model": judge,
            "reasoning_effort": settings.openai_reasoning_effort,
        },
        max_concurrency=4,  # 4 cases at a time: faster, but gentle on OpenAI rate limits
        client=client,
        upload_results=upload,
    )
    print_summary([row async for row in results])


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        engine.dispose()
        shutil.rmtree(TEMP_DIR, ignore_errors=True)