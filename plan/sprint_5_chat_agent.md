# Sprint 5 — Conversational Chat Agent + Order Status + Eval Harness

**Status:** DONE (2026-04-15)
**Created:** 2026-04-12
**Branch:** `feature/rest-api`
**Entry gate:** Sprint 4 closed on 2026-04-12 (8 commits, 60 pytest + 83 ctest green).
**Goal:** Ship the flagship interview feature: a multi-turn conversational agent (`POST /api/ai/chat`) with tool use, SSE streaming, plus deferred order status transitions and an AI evaluation harness.
**Exit:** Chat works end-to-end with 4 tools, SSE streaming, session persistence. Order PATCH endpoints enforce state machine. Eval harness produces quality scores.

---

## 0. Scope

### In scope

| ID | Feature | Layer |
|----|---------|-------|
| F1 | `POST /api/ai/chat` — multi-turn agent with tool use | Python + C++ proxy |
| F2 | In-memory session store with TTL expiry | Python |
| F3 | 4 chat tools: `search_menu`, `create_order_draft`, `check_order_status`, `get_recommendations` | Python |
| F4 | Iterative tool loop (max 5 iterations) | Python |
| F5 | SSE streaming for final text + tool progress events | Python + C++ pass-through |
| F6 | `PATCH /api/orders/:id/status` — admin status transitions | C++ |
| F7 | `PATCH /api/orders/:id/rating` — customer rates delivered order | C++ |
| F8 | `eval/` harness — labeled test cases for search/recommend/parse | Python |
| F9 | New error codes for chat + status transitions | C++ |

### Out of scope

- Redis/DB-backed session persistence
- Docker orchestration (Sprint 6)
- Embedding corpus refresh endpoint
- Rate limiting on AI endpoints
- WebSocket for chat

---

## 1. Design Decisions

### D1. Session model — in-memory dict with TTL

Sessions stored in `dict[str, ChatSession]` with threading lock. UUID4 session IDs. 30-minute TTL, eviction every 60s via background task. Server restart loses sessions — acceptable for demo.

### D2. Tool schema — Anthropic-native, converted for OpenAI

Reuses existing `_anthropic_tools_to_openai()` converter. Four tools:

| Tool | Input | Calls |
|------|-------|-------|
| `search_menu` | `{query, limit?}` | `search.search()` |
| `create_order_draft` | `{text, restaurant_hint_id?}` | `parser.parse_order()` |
| `check_order_status` | `{order_id}` | `order_repo.fetch_order_status()` |
| `get_recommendations` | `{limit?}` | `recommender.recommend()` |

### D3. Iterative tool loop

Standard ReAct pattern: send messages → if tool_use, execute tools, append results, re-send. Max 5 iterations safety cap. Both Anthropic and OpenAI support multi-turn tool use natively.

### D4. Streaming — SSE on final text + tool progress

Python returns `text/event-stream` with events: `session`, `tool_call`, `tool_result`, `text_delta`, `done`. C++ proxy pipes SSE bytes without parsing (chunked transfer). Non-streaming mode available via `stream: false`.

### D5. Order status state machine

```
Pending → Confirmed → Preparing → Delivering → Delivered
Pending → Cancelled
Confirmed → Cancelled
```

Admin-only for all transitions. Rating only on Delivered orders, range [1.0, 5.0].

### D6. LlmClient extension for multi-turn + streaming

Add `messages()` (full history) and `messages_stream()` (yields StreamEvent) to Protocol. Existing `tool_call()` unchanged.

---

## 2. Architecture

```
Client
  │  POST /api/ai/chat { message, session_id?, stream? }
  ▼
fos_api (C++) :8080
  │  AiController::chat() — JWT → AuthContext → proxy
  │  OrderController::updateStatus()  [NEW]
  │  OrderController::rateOrder()     [NEW]
  ▼
fos_ai (Python) :8000
  │  POST /ai/chat
  │    SessionStore.get_or_create()
  │    ChatEngine.run()
  │      ├─ LLM call with tool definitions
  │      ├─ Tool execution loop (max 5 iters)
  │      │    ├─ search_menu → search.search()
  │      │    ├─ create_order_draft → parser.parse_order()
  │      │    ├─ check_order_status → order_repo
  │      │    └─ get_recommendations → recommender.recommend()
  │      └─ Final text response (streamed)
  │    SessionStore.save()
  ▼
MySQL
```

---

## 3. Endpoint Contracts

### POST /api/ai/chat

**Request:**
```json
{
  "message": "I want kung pao chicken from Sichuan Delight",
  "session_id": null,
  "stream": true
}
```

**JSON response (stream=false):**
```json
{
  "success": true,
  "data": {
    "session_id": "a1b2c3d4-...",
    "reply": "I found Kung Pao Chicken at Sichuan Delight...",
    "tool_calls": [
      {"tool": "search_menu", "input": {...}, "output": {...}}
    ],
    "finish_reason": "end_turn"
  }
}
```

**SSE response (stream=true):**
```
event: session
data: {"session_id": "a1b2c3d4-..."}

event: tool_call
data: {"tool": "search_menu", "input": {"query": "kung pao chicken"}}

event: tool_result
data: {"tool": "search_menu", "output": {"results": [...], "count": 3}}

event: text_delta
data: {"delta": "I found "}

event: done
data: {"finish_reason": "end_turn"}
```

### PATCH /api/orders/:id/status

```json
// Request
{"status": "Confirmed"}
// Response 200
{"success": true, "data": {"order_id": 42, "status": "Confirmed", "previous_status": "Pending"}}
// Error 400
{"success": false, "error": {"code": "INVALID_STATUS_TRANSITION", "message": "..."}}
```

### PATCH /api/orders/:id/rating

```json
// Request
{"rating": 4.5}
// Response 200
{"success": true, "data": {"order_id": 42, "rating": 4.5}}
```

---

## 4. Error Codes (new)

| Code | HTTP | Meaning |
|------|------|---------|
| `AI_SESSION_NOT_FOUND` | 404 | Session ID not in store |
| `AI_TOOL_ERROR` | 502 | Tool execution failed |
| `AI_MAX_ITERATIONS` | 502 | Tool loop hit 5-iteration cap |
| `INVALID_STATUS_TRANSITION` | 400 | Status change violates state machine |
| `ORDER_ALREADY_RATED` | 409 | Order already has a rating |

---

## 5. TDD Execution Order

### Phase 1: Order Status Transitions (C++)

| Step | Action | Files |
|------|--------|-------|
| 1.1 | RED: status machine + rating unit tests | `tests/test_order_status.cpp` |
| 1.2 | GREEN: implement OrderStatusMachine + service methods | `OrderStatusMachine.h`, `OrderService.*`, `ErrorCodes.h`, `JsonEnvelope.h` |
| 1.3 | GREEN: wire PATCH endpoints | `OrderController.*`, `Database.*` |

### Phase 2: Python Chat Engine

**New files:**
- `ai_service/src/fos_ai/services/session_store.py` (~80 lines) — `SessionStore` class: `dict[str, ChatSession]` with `threading.Lock`, UUID4 IDs, 30-min TTL, background eviction task
- `ai_service/src/fos_ai/services/chat_tools.py` (~150 lines) — tool definitions (Anthropic format), `ToolExecutor` dispatch: tool_name → service call, returns JSON-serializable result
- `ai_service/src/fos_ai/services/chat_engine.py` (~200 lines) — `ChatEngine.run(session, message, user_id)`: agentic loop (send messages → execute tool_use blocks → re-send, max 5 iterations)
- `ai_service/src/fos_ai/schemas_chat.py` (~80 lines) — `ChatRequest`, `ChatResponse`, `ChatMessage`, `StreamEvent`, `ChatSession`
- `ai_service/src/fos_ai/db/order_repo.py` (~40 lines) — `fetch_order_status(conn, order_id, user_id)` for `check_order_status` tool

**Tests:**
- `ai_service/tests/test_session_store.py` — create/get/update/TTL expiry/max cap
- `ai_service/tests/test_chat_tools.py` — tool schema valid, executor dispatches, unknown tool error
- `ai_service/tests/test_chat_engine.py` — single-turn text, single tool call, multi-tool, max-iteration cap, session continuity

| Step | Action | Files |
|------|--------|-------|
| 2.1 | RED→GREEN: session store | `session_store.py`, `schemas_chat.py`, `test_session_store.py` |
| 2.2 | RED→GREEN: chat tools | `chat_tools.py`, `order_repo.py`, `test_chat_tools.py` |
| 2.3 | RED→GREEN: chat engine (agentic loop) | `chat_engine.py`, `test_chat_engine.py` |

### Phase 3: LLM Client Extension

**Modify:** `ai_service/src/fos_ai/services/llm_client.py`
- Add `messages()` method to `LlmClient` Protocol — accepts full `list[dict]` message history instead of single user string
- Add `messages_stream()` method — yields `StreamEvent` dataclasses (text_delta, tool_use, done)
- Implement on both `AnthropicLlmClient` (using `anthropic.Anthropic.messages.create` with `stream=True`) and `OpenAILlmClient` (using `openai.OpenAI.chat.completions.create` with `stream=True`)
- Existing `tool_call()` unchanged (parser.py still uses it)

| Step | Action | Files |
|------|--------|-------|
| 3.1 | RED→GREEN: multi-turn + streaming | `llm_client.py`, `test_llm_client.py` |

### Phase 4: Chat Router + C++ Proxy

**New files:**
- `ai_service/src/fos_ai/routers/chat.py` (~100 lines) — `POST /ai/chat`: reads `X-User-Id`, gets/creates session, calls `ChatEngine.run()`, returns JSON or SSE based on `stream` field
- C++ changes:
  - `AiController.h/cc` — add `chat()` handler: for `stream=true`, pipe SSE bytes via chunked transfer; for `stream=false`, forward JSON normally
  - `HealthController.h/cc` — remove `aiChat` 501 stub (route moves to AiController)
  - `deps.py` — add `SessionStore` singleton, init in lifespan

| Step | Action | Files |
|------|--------|-------|
| 4.1 | RED→GREEN: chat router | `routers/chat.py`, `test_chat_router.py`, `deps.py`, `main.py` |
| 4.2 | C++ AiController::chat + SSE proxy | `AiController.*`, `HealthController.*` |

### Phase 5: Evaluation Harness

**New files:**
- `eval/conftest.py` — shared fixtures (menu, embedder, corpus, mock LLM)
- `eval/data/search_cases.json` — labeled query→food_id pairs (~15 cases)
- `eval/data/recommend_cases.json` — user history→expected recs (~10 cases)
- `eval/data/parse_cases.json` — NL text→expected draft fields (~10 cases)
- `eval/test_search_quality.py` — MRR (Mean Reciprocal Rank) + Hit@5 metrics
- `eval/test_recommend_quality.py` — filter-seen + cuisine-affinity checks
- `eval/test_parse_quality.py` — field match with mock LLM (tests resolution logic, not LLM)
- Run with: `uv run pytest eval/ -m eval`

| Step | Action | Files |
|------|--------|-------|
| 5.1 | Eval framework + labeled data | `eval/`, test cases, metrics |

---

## 6. Commit Plan

| # | Message | Phase |
|---|---------|-------|
| 1 | `feat(service): implement order status state machine and rating` | 1 |
| 2 | `feat(api): add PATCH order status and rating endpoints` | 1 |
| 3 | `feat(ai): implement session store with TTL` | 2 |
| 4 | `feat(ai): implement chat tool definitions and executor` | 2 |
| 5 | `feat(ai): implement multi-turn chat engine with tool calling` | 2 |
| 6 | `feat(ai): add multi-turn messages and streaming to LlmClient` | 3 |
| 7 | `feat(ai): implement POST /ai/chat with SSE streaming` | 4 |
| 8 | `feat(api): implement /api/ai/chat proxy with SSE streaming` | 4 |
| 9 | `test(eval): add AI quality evaluation harness` | 5 |
| 10 | `docs: update README and mark Sprint 5 DONE` | 5 |

---

## 7. Risks

| Risk | Mitigation |
|------|-----------|
| Drogon SSE proxy may buffer | Investigate chunked callback; fallback to JSON-only |
| Anthropic vs OpenAI tool_result format divergence | Extend format converter, test both providers |
| Session memory growth | Cap at 1000 sessions, 429 if full |
| LLM hallucinating tool names | Executor returns error as tool_result, LLM self-corrects |

---

## 8. Definition of Done

- [ ] `POST /api/ai/chat` works end-to-end with multi-turn + 2+ tools
- [ ] SSE streaming delivers text + tool progress events
- [ ] Chat works with both Anthropic and OpenAI (one live, other mocked)
- [ ] Session persistence across turns; TTL eviction verified
- [ ] `PATCH /api/orders/:id/status` enforces state machine (admin-only)
- [ ] `PATCH /api/orders/:id/rating` works for delivered orders
- [ ] `eval/` harness runs with `pytest -m eval`, produces quality scores
- [ ] All existing tests pass: ctest 83+, pytest 60+
- [ ] New tests: 15+ pytest (chat) + 10+ ctest (status/rating)
- [ ] README updated with chat docs
- [ ] Pushed to origin
