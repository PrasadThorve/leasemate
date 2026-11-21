import os
import shutil
import tempfile
from pathlib import Path

# --- 1. Safe settings for every test run (must come before the app imports) ---
TEST_DIR = Path(tempfile.mkdtemp(prefix="leasemate-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(TEST_DIR / 'test.db').as_posix()}"
os.environ["OPENAI_API_KEY"] = "sk-test-not-a-real-key"  # tests never call OpenAI
os.environ["LANGSMITH_TRACING"] = "false"  # don't send test runs to LangSmith
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["DEFAULT_COMPANY_ID"] = "1"  # in-memory MCP calls have no headers, so this decides the company

import pytest  # noqa: E402
from fastmcp import Client  # noqa: E402

import db.seed as seed_module  # noqa: E402
from db.database import engine  # noqa: E402
from mcp_server.server import mcp  # noqa: E402

# Safety net: seed() deletes every table, so make sure we're NOT on the real leasemate.db.
assert "leasemate-tests-" in str(engine.url), f"Tests must use the temp database, not {engine.url}"


# --- 2. Fixtures ---

@pytest.fixture(autouse=True)
def fresh_database():
    """Runs before EVERY test (autouse): rebuild the database from the seed data.
    Each test starts from the same known state, so tests can't affect each other."""
    seed_module.rng.seed(42)  # same "random" flats every time, not a continuation
    seed_module.seed()


@pytest.fixture
async def mcp_client():
    """An MCP client connected to our server IN MEMORY: real MCP protocol, real
    validation, real tools, but no HTTP server or port needed."""
    async with Client(mcp) as client:
        yield client


@pytest.fixture
def in_memory_mcp(monkeypatch):
    """Make the agent's MCP adapter talk to the in-memory server instead of
    http://127.0.0.1:8001. monkeypatch undoes the swap after the test."""
    monkeypatch.setattr("app.agent.mcp_tools._mcp_client", lambda url, company_id: Client(mcp))


@pytest.fixture(scope="session", autouse=True)
def remove_test_database():
    """After the whole test run: close database connections and delete the temp folder."""
    yield
    engine.dispose()
    shutil.rmtree(TEST_DIR, ignore_errors=True)