"""Chat with the LeaseMate agent in your terminal.

Start the MCP server first, in another terminal:
    uv run python -m mcp_server.server
Then run:
    uv run python -m scripts.chat_cli

Type 'new' to start a fresh conversation, or 'quit' to exit.
Every turn is traced in LangSmith (project from LANGSMITH_PROJECT in .env).
"""
import asyncio
import uuid

from langchain_core.messages import HumanMessage, ToolMessage

from app.agent.graph import build_agent
from app.config import settings


async def main() -> None:
    company_id = settings.default_company_id
    agent = await build_agent(company_id)
    thread_id = str(uuid.uuid4())
    print(f"LeaseMate is ready ({settings.openai_model}). Type 'new' for a new chat, 'quit' to exit.\n")

    while True:
        user_text = (await asyncio.to_thread(input, "You: ")).strip()
        if not user_text:
            continue
        if user_text.lower() in {"quit", "exit"}:
            break
        if user_text.lower() == "new":
            thread_id = str(uuid.uuid4())
            print("(Started a new conversation)\n")
            continue

        config = {
            # The checkpointer uses thread_id to remember this conversation.
            "configurable": {"thread_id": thread_id},
            # These show up in LangSmith, so you can filter and group traces.
            "run_name": "leasemate_chat",
            "tags": ["cli"],
            "metadata": {"thread_id": thread_id, "company_id": company_id, "channel": "cli"},
        }
        result = await agent.ainvoke({"messages": [HumanMessage(user_text)]}, config)

        # Show which tools the agent used in this turn (messages after our last question).
        messages = result["messages"]
        last_question = max(i for i, m in enumerate(messages) if isinstance(m, HumanMessage))
        tools_used = [m.name for m in messages[last_question:] if isinstance(m, ToolMessage)]
        if tools_used:
            print(f"  [tools: {', '.join(tools_used)}]")
        print(f"LeaseMate: {messages[-1].text}\n")


if __name__ == "__main__":
    asyncio.run(main())