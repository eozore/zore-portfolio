"""
FastAPI server for the Agentic Marketing Platform agents service.

Exposes:
- POST /chat: SSE endpoint for real-time conversation with the Director agent.
- GET /health: Public health check endpoint.

The /chat endpoint validates the Firebase ID token, resolves the tenant_id,
creates or recovers an ADK session, and streams SSE events back to the client.

SSE event types:
- token: text fragments from the Director
- activity: sub-agent or tool status updates
- done: signals end of response with run_id
- error: failure information

Features:
- Event persistence to Firestore (runs/{runId}/events)
- In-memory event buffer (300s TTL) for reconnection with Last-Event-ID
- Background agent execution survives client disconnection

Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from apps.agents.config import settings
from apps.agents.event_store import (
    event_buffer,
    persist_event_to_firestore,
    ensure_run_document,
)
from apps.agents.middleware import FirebaseAuthMiddleware

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)
logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))

# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Agentic Marketing Platform — Agents Service",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS Configuration
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "https://*.run.app",  # Cloud Run domains
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Firebase Auth Middleware
# ---------------------------------------------------------------------------

app.add_middleware(FirebaseAuthMiddleware)

# ---------------------------------------------------------------------------
# Request/Response Models
# ---------------------------------------------------------------------------

MAX_MESSAGE_LENGTH = 4000


class ChatRequest(BaseModel):
    """Request body for the POST /chat endpoint."""

    message: str = Field(
        ...,
        min_length=1,
        max_length=MAX_MESSAGE_LENGTH,
        description="User message to send to the Director (max 4000 characters).",
    )
    session_id: str | None = Field(
        default=None,
        description="Existing ADK session ID to continue a conversation. "
        "If None, a new session is created.",
    )


# ---------------------------------------------------------------------------
# Health Check (Public — no auth required)
# ---------------------------------------------------------------------------


@app.get("/health")
async def health_check() -> dict:
    """Public health check endpoint for load balancers and readiness probes."""
    return {"status": "ok", "service": "agents", "timestamp": int(time.time())}


# ---------------------------------------------------------------------------
# SSE Helpers
# ---------------------------------------------------------------------------


def _sse_event(event_type: str, data: dict, event_id: str | None = None) -> str:
    """
    Format a single SSE event as a string.

    Format:
        event: <type>\ndata: <json>\nid: <id>\n\n
    """
    lines: list[str] = []
    lines.append(f"event: {event_type}")
    lines.append(f"data: {json.dumps(data, ensure_ascii=False)}")
    if event_id:
        lines.append(f"id: {event_id}")
    lines.append("")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Placeholder ADK Runner
# ---------------------------------------------------------------------------


async def _run_director_session(
    tenant_id: str,
    session_id: str,
    message: str,
    run_id: str,
) -> AsyncGenerator[tuple[str, str, str, dict], None]:
    """
    Placeholder async generator that simulates the Director agent responding.

    Yields tuples of (raw_sse, event_id, event_type, data) for each event.

    In production, this will:
    1. Create or recover an ADK session for the tenant.
    2. Send the user message to the Director root agent.
    3. Yield SSE events as the Director and sub-agents process the request.

    For now, it simulates a realistic streaming response pattern.
    """
    event_counter = 0

    def next_event_id() -> str:
        nonlocal event_counter
        event_counter += 1
        return f"evt_{run_id}_{event_counter:04d}"

    # Activity: Director is thinking
    evt_id = next_event_id()
    data = {
        "agent": "director",
        "status": "working",
        "message": "Analisando sua mensagem...",
    }
    yield _sse_event("activity", data, evt_id), evt_id, "activity", data
    await asyncio.sleep(0.3)

    # Simulate streaming token response
    response_chunks = [
        "Entendi ",
        "seu pedido. ",
        "Estou ",
        "coordenando ",
        "o time ",
        "para ",
        "atender ",
        "sua ",
        "solicitação.",
    ]

    for chunk in response_chunks:
        evt_id = next_event_id()
        data = {"text": chunk}
        yield _sse_event("token", data, evt_id), evt_id, "token", data
        await asyncio.sleep(0.05)

    # Activity: Director delegating
    evt_id = next_event_id()
    data = {
        "agent": "director",
        "status": "completed",
        "message": "Resposta concluída.",
    }
    yield _sse_event("activity", data, evt_id), evt_id, "activity", data

    # Done event
    evt_id = next_event_id()
    data = {"run_id": run_id}
    yield _sse_event("done", data, evt_id), evt_id, "done", data


# ---------------------------------------------------------------------------
# Background Task Runner
# ---------------------------------------------------------------------------

# Dict to store background tasks keyed by run_id so agent continues if client disconnects
_background_tasks: dict[str, asyncio.Task] = {}


async def _run_agent_background(
    tenant_id: str,
    session_id: str,
    message: str,
    run_id: str,
) -> None:
    """
    Run the agent session in the background, buffering all events.

    This ensures the agent continues executing even if the SSE connection
    is dropped by the client. Events are stored in the in-memory buffer
    (300s TTL) and persisted to Firestore for later retrieval.
    """
    try:
        # Ensure the run document exists
        await ensure_run_document(tenant_id, run_id, message)

        async for raw_sse, evt_id, evt_type, data in _run_director_session(
            tenant_id=tenant_id,
            session_id=session_id,
            message=message,
            run_id=run_id,
        ):
            # Buffer every event for reconnection support
            event_buffer.add_event(
                run_id=run_id,
                event_id=evt_id,
                event_type=evt_type,
                data=data,
                raw_sse=raw_sse,
            )

            # Persist activity events to Firestore
            if evt_type == "activity":
                await persist_event_to_firestore(
                    tenant_id=tenant_id,
                    run_id=run_id,
                    event_id=evt_id,
                    event_type=evt_type,
                    data=data,
                )
    except Exception:
        logger.exception(
            "Error in background agent execution",
            extra={"run_id": run_id, "tenant_id": tenant_id},
        )
        # Buffer error event
        error_evt_id = f"evt_{run_id}_error"
        error_data = {
            "message": "Ocorreu um erro ao processar sua mensagem.",
            "run_id": run_id,
        }
        error_sse = _sse_event("error", error_data, error_evt_id)
        event_buffer.add_event(
            run_id=run_id,
            event_id=error_evt_id,
            event_type="error",
            data=error_data,
            raw_sse=error_sse,
        )
    finally:
        # Clean up task reference
        _background_tasks.pop(run_id, None)


# ---------------------------------------------------------------------------
# POST /chat — SSE Streaming Endpoint
# ---------------------------------------------------------------------------


@app.post("/chat")
async def chat(request: Request, body: ChatRequest) -> StreamingResponse:
    """
    Chat endpoint that accepts user messages and streams Director responses via SSE.

    Flow:
    1. Validate message length (enforced by Pydantic, max 4000 chars).
    2. Resolve tenant_id from request.state (set by FirebaseAuthMiddleware).
    3. Create or recover ADK session using session_id.
    4. Check for Last-Event-ID header for reconnection support.
    5. Start agent in background (survives client disconnect).
    6. Stream SSE events: token, activity, done, error.

    Headers required:
        Authorization: Bearer <firebase_id_token>
    
    Headers optional:
        Last-Event-ID: <event_id> — for reconnection, replays missed events

    Body:
        {
            "message": "string (1-4000 chars)",
            "session_id": "string | null"
        }

    Response:
        Content-Type: text/event-stream
        SSE events streamed until done or error.
    """
    # Extract tenant info from middleware
    tenant_id: str = request.state.tenant_id
    uid: str = request.state.uid

    # Resolve or create session
    session_id = body.session_id or str(uuid.uuid4())
    run_id = str(uuid.uuid4())

    # Check for Last-Event-ID header (reconnection support)
    last_event_id: str | None = request.headers.get("last-event-id")

    logger.info(
        "Chat request received",
        extra={
            "tenant_id": tenant_id,
            "uid": uid,
            "session_id": session_id,
            "run_id": run_id,
            "message_length": len(body.message),
            "last_event_id": last_event_id,
        },
    )

    # Start agent in background so it continues even if client disconnects
    task = asyncio.create_task(
        _run_agent_background(
            tenant_id=tenant_id,
            session_id=session_id,
            message=body.message,
            run_id=run_id,
        )
    )
    _background_tasks[run_id] = task

    async def event_stream() -> AsyncGenerator[str, None]:
        """
        Async generator that yields SSE events.

        If Last-Event-ID is provided, first replays missed events from buffer,
        then streams new events as they arrive from the background task.
        """
        # If reconnecting with Last-Event-ID, replay buffered events
        if last_event_id:
            # Extract run_id from event_id format: evt_{run_id}_{counter}
            # Try to find events in any matching buffer
            replay_events = event_buffer.get_events_after_id(
                run_id, last_event_id
            )
            for buffered_evt in replay_events:
                yield buffered_evt.raw_sse

        # Stream new events as they are produced by the background task
        last_seen_count = 0
        while True:
            # Check current buffer state
            all_events = event_buffer.get_all_events(run_id)
            new_events = all_events[last_seen_count:]

            for evt in new_events:
                # Skip events already replayed via Last-Event-ID
                if last_event_id and evt.event_id == last_event_id:
                    continue
                yield evt.raw_sse

            last_seen_count = len(all_events)

            # Check if the background task is done
            if task.done():
                # Yield any final events that arrived after our last check
                final_events = event_buffer.get_all_events(run_id)
                for evt in final_events[last_seen_count:]:
                    yield evt.raw_sse
                break

            # Brief pause to avoid busy-waiting
            await asyncio.sleep(0.02)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Error Handlers
# ---------------------------------------------------------------------------


@app.exception_handler(422)
async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle Pydantic validation errors with a clear message."""
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Validation error",
            "message": "A mensagem deve ter entre 1 e 4000 caracteres.",
        },
    )


# ---------------------------------------------------------------------------
# Entrypoint (for local development)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "apps.agents.server:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level=settings.log_level.lower(),
    )
