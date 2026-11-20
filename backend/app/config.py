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

    mcp_server_url: str = "http://127.0.0.1:8001/mcp"
    default_company_id: int = 1

    @field_validator("openai_reasoning_effort", mode="before")
    @classmethod
    def empty_means_none(cls, value: str | None) -> str | None:
        return value or None


settings = Settings()