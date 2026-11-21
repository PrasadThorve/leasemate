import logging
from contextlib import asynccontextmanager
from typing import Annotated

import openai
from fastapi import Depends, FastAPI, HTTPException, Path, status
from fastapi.middleware.cors import CORSMiddleware

from app.agent.service import AgentService, ToolsUnavailableError
from app.config import settings
from app.dependencies import get_agent_service, get_company_id
from app.schemas import THREAD_ID_PATTERN, ChatRequest, ChatResponse, HistoryMessage, HistoryResponse
from app.admin import router as admin_router

logger = logging.getLogger("leasemate")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.agent_service = AgentService()
    yield


app = FastAPI(
    title="LeaseMate API",
    description="Chat API for the LeaseMate AI leasing agent.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Widget-Key", "X-Admin-Key"],
)

app.include_router(admin_router)


CompanyId = Annotated[int, Depends(get_company_id)]
Service = Annotated[AgentService, Depends(get_agent_service)]


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, company_id: CompanyId, service: Service) -> ChatResponse:
    try:
        turn = await service.chat(company_id, body.message, body.thread_id)
    except ToolsUnavailableError as error:
        logger.exception("MCP server unreachable")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The leasing system is unavailable. Is the MCP server running?",
        ) from error
    except openai.APIError as error:
        logger.exception("OpenAI request failed")
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "The AI model didn't respond. Please try again.",
        ) from error
        
    except Exception as error:
        # Any other bug: log the full error for us, show a safe message to the user.
        # Raising HTTPException here (instead of letting the error escape) keeps the
        # CORS headers on the response, so the browser shows this message rather than
        # a misleading "CORS error / can't reach the API".
        logger.exception("Unexpected error in /chat")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Something went wrong on our side. Please try again.",
        ) from error

    return ChatResponse(
        thread_id=turn.thread_id, reply=turn.reply, tools_used=turn.tools_used, guardrail=turn.guardrail
    )


@app.get("/chat/{thread_id}", response_model=HistoryResponse)
async def chat_history(
    thread_id: Annotated[str, Path(pattern=THREAD_ID_PATTERN)],
    company_id: CompanyId,
    service: Service,
) -> HistoryResponse:
    try:
        messages = await service.history(company_id, thread_id)
    except ToolsUnavailableError as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "The leasing system is unavailable.") from error

    return HistoryResponse(
        thread_id=thread_id,
        messages=[HistoryMessage(role=role, content=text) for role, text in messages],
    )