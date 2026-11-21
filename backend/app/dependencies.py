from typing import Annotated

from fastapi import Header, HTTPException, Request, status

from app.agent.service import AgentService
from app.config import settings


def get_company_id(x_widget_key: Annotated[str | None, Header()] = None) -> int:
    """Work out which company this request is for, from the X-Widget-Key header.

    Each company's website embeds the chat widget with its own public key. The key
    identifies the company (it is not a password); the company id itself is never
    sent by the browser and never seen by the LLM.
    """
    company_id = settings.widget_keys.get(x_widget_key or "")
    if company_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing or unknown X-Widget-Key header.")
    return company_id

def get_admin_company_id(x_admin_key: Annotated[str | None, Header()] = None) -> int:
    """Which company's leasing office is signed in, from the secret X-Admin-Key header.
    The public widget key is NOT accepted here: anyone can read it from the website."""
    company_id = settings.admin_keys.get(x_admin_key or "")
    if company_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing or unknown X-Admin-Key header.")
    return company_id


def get_agent_service(request: Request) -> AgentService:
    """The single AgentService created when the app starts (see lifespan in main.py)."""
    return request.app.state.agent_service