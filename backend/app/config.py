"""App settings, loaded from backend/.env.
"""
from pathlib import Path

from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BACKEND_DIR / ".env"

load_dotenv(ENV_FILE)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    openai_api_key: str
    openai_model: str = "gpt-5-mini"
    # For reasoning models (like gpt-5-mini): "low" keeps replies fast enough for chat.
    # Leave it empty in .env if you switch to a model that doesn't support it.
    openai_reasoning_effort: str | None = "low"
    
    # Model for the guardrail classifier. Empty = same as OPENAI_MODEL. A smaller,
    # cheaper model works well here because classifying is an easy task.
    guard_model: str | None = None

    mcp_server_url: str = "http://127.0.0.1:8001/mcp"
    default_company_id: int = 1
    
    # Websites allowed to call the API from a browser (the React dev server).
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Each company embeds the chat widget with its own public widget key. The API maps
    # the key to a company, so the browser never sends a company id directly.
    widget_keys: dict[str, int] = {"sahyadri-demo-key": 1, "indrayani-demo-key": 2}
    
    # Keys for the leasing office dashboard (/admin). Unlike widget keys these are secret:
    # only the company's staff should have them. Demo values; production would use staff login.
    admin_keys: dict[str, int] = {"sahyadri-admin-demo": 1, "indrayani-admin-demo": 2}

    @field_validator("openai_reasoning_effort", "guard_model", mode="before")
    @classmethod
    def empty_means_none(cls, value: str | None) -> str | None:
        return value or None


settings = Settings()