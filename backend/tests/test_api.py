import pytest
from fastapi.testclient import TestClient

from app.agent.service import AgentService
from app.main import app
from tests.fakes import FakeLLM, fake_classify

SAHYADRI = {"X-Widget-Key": "sahyadri-demo-key"}
INDRAYANI = {"X-Widget-Key": "indrayani-demo-key"}


@pytest.fixture
def client(monkeypatch, in_memory_mcp):
    monkeypatch.setattr("app.agent.graph.create_llm", lambda model=None: FakeLLM())
    monkeypatch.setattr("app.agent.graph.make_classifier", lambda llm: fake_classify)
    # "with" runs the app's lifespan, so every test gets a fresh AgentService (and empty memory).
    with TestClient(app) as test_client:
        yield test_client


def chat(client, message: str, headers=SAHYADRI, thread_id: str | None = None):
    return client.post("/chat", json={"message": message, "thread_id": thread_id}, headers=headers)


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


@pytest.mark.parametrize("headers", [{}, {"X-Widget-Key": "made-up-key"}])
def test_chat_needs_a_valid_widget_key(client, headers):
    assert chat(client, "Hello", headers=headers).status_code == 401


@pytest.mark.parametrize(
    "body",
    [
        {"message": ""},  # too short
        {"message": "x" * 2001},  # too long
        {"message": "Hello", "thread_id": "../../etc/passwd"},  # unsafe characters
    ],
)
def test_invalid_requests_are_rejected(client, body):
    assert client.post("/chat", json=body, headers=SAHYADRI).status_code == 422


def test_chat_returns_reply_tools_and_thread(client):
    response = chat(client, "Which properties do you have?")

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "Here's what I found using list_properties."
    assert body["tools_used"] == ["list_properties"]
    assert body["guardrail"] is None
    assert body["thread_id"]  # a new id was generated


def test_guardrail_is_reported_to_the_frontend(client):
    body = chat(client, "Do you allow bachelors?").json()
    assert body["guardrail"] == "fair_housing"
    assert body["tools_used"] == []


def test_failed_tools_are_not_listed_as_done(client):
    body = chat(client, "My phone is 12345").json()
    assert body["tools_used"] == []  # create_guest_card failed (invalid phone)
    assert body["reply"].startswith("Sorry, that didn't work")


def test_history_continues_and_stays_within_the_company(client):
    thread_id = chat(client, "Hello").json()["thread_id"]
    chat(client, "Which properties do you have?", thread_id=thread_id)

    history = client.get(f"/chat/{thread_id}", headers=SAHYADRI).json()["messages"]
    assert [m["role"] for m in history] == ["user", "assistant", "user", "assistant"]

    # Another company using the same thread id sees nothing.
    other = client.get(f"/chat/{thread_id}", headers=INDRAYANI).json()["messages"]
    assert other == []


def test_mcp_server_down_returns_503(client, monkeypatch):
    async def mcp_unreachable(*args, **kwargs):
        raise RuntimeError("Client failed to connect")

    monkeypatch.setattr("app.agent.service.build_agent", mcp_unreachable)
    response = chat(client, "Hello")

    assert response.status_code == 503
    assert "MCP server" in response.json()["detail"]


def test_unexpected_errors_return_a_safe_500(client, monkeypatch):
    async def broken_chat(*args, **kwargs):
        raise ValueError("secret internal details")

    monkeypatch.setattr(AgentService, "chat", broken_chat)
    response = chat(client, "Hello")

    assert response.status_code == 500
    assert response.json()["detail"] == "Something went wrong on our side. Please try again."
    assert "secret" not in response.text  # internal errors never leak to the user