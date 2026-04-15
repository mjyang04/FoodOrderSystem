"""POST /ai/chat — multi-turn conversational agent with optional SSE streaming."""

from __future__ import annotations

import json
import logging
from typing import Any, Iterator

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse

from fos_ai.schemas_chat import (
    ChatData,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatSession,
    ToolCallRecord,
)
from fos_ai.services.chat_engine import ChatEngine, ChatMaxIterations
from fos_ai.services.chat_tools import ToolContext, ToolExecutor, all_tools
from fos_ai.services.llm_client import StreamEvent
from fos_ai.services.session_store import SessionStore, SessionStoreFull

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/chat")
def chat(
    body: ChatRequest,
    x_user_id: int = Header(..., alias="X-User-Id"),
):
    from fos_ai.deps import (
        get_corpus,
        get_db_conn,
        get_embedder,
        get_llm_client,
        get_menu,
    )
    from fos_ai import deps as _deps

    corpus = get_corpus()
    if not corpus.ready:
        raise HTTPException(status_code=503, detail="Menu corpus not loaded yet")

    session_store = _deps.get_session_store()

    try:
        session = session_store.get_or_create(body.session_id, user_id=x_user_id)
    except SessionStoreFull as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc

    ctx = ToolContext(
        user_id=x_user_id,
        menu=get_menu(),
        corpus=corpus,
        embedder=get_embedder(),
        llm=get_llm_client(),
        db_conn=get_db_conn(),
    )
    executor = ToolExecutor(ctx)
    engine = ChatEngine(llm=get_llm_client(), executor=executor)

    if body.stream:
        return StreamingResponse(
            _stream_generator(engine, session, session_store, body.message),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return _run_non_streaming(engine, session, session_store, body.message)


# ---------- non-streaming path ----------

def _run_non_streaming(
    engine: ChatEngine,
    session: ChatSession,
    store: SessionStore,
    user_text: str,
) -> ChatResponse:
    try:
        result = engine.run(session, user_text)
    except ChatMaxIterations as exc:
        raise HTTPException(status_code=502, detail=f"AI_MAX_ITERATIONS: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("chat engine error")
        raise HTTPException(status_code=502, detail=f"AI_TOOL_ERROR: {exc}") from exc

    store.save(session)
    return ChatResponse(
        success=True,
        data=ChatData(
            session_id=session.session_id,
            reply=result.reply,
            tool_calls=result.tool_calls,
            finish_reason=result.finish_reason,
        ),
    )


# ---------- SSE path ----------

def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _stream_generator(
    engine: ChatEngine,
    session: ChatSession,
    store: SessionStore,
    user_text: str,
) -> Iterator[str]:
    """Yield SSE frames as the agent thinks/tool-calls/replies.

    This runs ChatEngine non-streamingly (simpler, correct) and emits events
    around each tool call. Per-token LLM streaming is wired via the underlying
    LlmClient.messages_stream() but not exposed here to keep this code small.
    """
    yield _sse("session", {"session_id": session.session_id})

    try:
        result = engine.run(session, user_text)
    except ChatMaxIterations as exc:
        yield _sse("error", {"code": "AI_MAX_ITERATIONS", "message": str(exc)})
        return
    except Exception as exc:  # noqa: BLE001
        logger.exception("chat engine error (stream)")
        yield _sse("error", {"code": "AI_TOOL_ERROR", "message": str(exc)})
        return

    for tc in result.tool_calls:
        yield _sse("tool_call", {"tool": tc.tool, "input": tc.input})
        yield _sse("tool_result", {
            "tool": tc.tool,
            "output": tc.output,
            "error": tc.error,
        })

    if result.reply:
        yield _sse("text_delta", {"delta": result.reply})

    store.save(session)
    yield _sse("done", {"finish_reason": result.finish_reason})
