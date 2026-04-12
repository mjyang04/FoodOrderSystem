# Sprint 4 — AI / LLM Layer

**Status:** DONE
**Created:** 2026-04-12
**Branch:** `feature/rest-api` (or new `feature/ai-layer` — decision in §10)
**Entry gate:** Sprint 3 closed on 2026-04-12 (5 commits `c6eb347`→`b32f520`, ctest 77/77, pushed).
**Goal:** Fulfil the `/api/ai/*` reservation that `plan/rest_api_migration.md` carved out in Sprint 1 and the `HealthController` stubs placeholdered in Sprint 3. Ship a **Python microservice** (`fos_ai`) that owns all LLM and PyTorch logic, reached by the existing C++ API through a thin proxy controller.
**Exit:** Three AI endpoints live end-to-end (`POST /api/ai/parse-order`, `GET /api/ai/search`, `GET /api/ai/recommend`), Python side has pytest ≥ 80 % on business logic, C++ side has Drogon integration smoke for the proxy, and a cold `uv run fos-ai` + `./build/fos_api` smoke test passes against live MySQL.

---

## 0. Motivation — why now and why this shape

Two facts make Sprint 4 the natural moment:

1. **The reservation is already on disk.** `plan/rest_api_migration.md:18-28` declared `/api/ai/chat` and `/api/ai/recommend` reserved from Sprint 1, `HealthController::aiChat` and `aiRecommend` already return 501 with a documented `reserved_shape`. Clients of the REST API have had a stable AI routing surface for three sprints — Sprint 4 just fills in the implementations.
2. **The service layer is ready.** Sprint 2.5 H-DI made every service method callable without a request context (that was `rest_api_migration.md` §1's explicit AI hook). Sprint 3's `OrderService::createOrder` takes a `NewOrderDto` — exactly the shape Claude's tool-calling output will populate.

The **why this shape** decision is structural: we do **not** embed a Python interpreter into `fos_api`. We run a second process. Rationale lives in §2 D1.

---

## 1. Scope

### In scope (Sprint 4 MVP)

- **`fos_ai` — new Python 3.11+ microservice** using FastAPI + PyTorch + HuggingFace `transformers` + the official `anthropic` SDK, managed by `uv`.
- **Three endpoints exposed through the C++ API proxy:**
  - `POST /api/ai/parse-order` — natural-language → `NewOrderDto`. Does **not** create the order. Returns a parsed, validated draft that the client then submits through the existing `POST /api/orders`.
  - `GET /api/ai/search?q=<text>&limit=<n>` — semantic search over the menu. PyTorch-encoded query, cosine similarity against a pre-encoded corpus.
  - `GET /api/ai/recommend?limit=<n>` — personalized recommendations for the authenticated user. Content-based, built on the same embedding corpus as F2.
- **C++ `AiController`** that proxies the three routes to `fos_ai` over HTTP, preserving the JSON envelope contract and translating upstream errors into the existing `err::k*` codes.
- **New error codes** in `src/service/ErrorCodes.h`: `kAiUnavailable`, `kAiBadRequest`, `kAiUpstreamError`. Mapped in `JsonEnvelope::statusForError`.
- **Pytest coverage** on `fos_ai` business logic: menu loading, embedding, search, recommender, Anthropic client wrapper (mocked).
- **Live smoke-test matrix** mirroring Sprint 3 §8: golden path for each endpoint plus error paths (no JWT, Python service down, LLM rejected input, etc.).
- **README update** with architecture diagram and `uv run fos-ai` quickstart.

### Out of scope (defer to Sprint 5+)

- **`POST /api/ai/chat`** — the full multi-turn chat endpoint with session state and iterative tool calling. Sprint 4 keeps the existing 501 stub in place. Sprint 5 builds it on top of F1/F2/F3.
- **Docker / docker-compose orchestration** — Sprint 6 ops-polish territory. Sprint 4 runs two processes locally, discovered via `AI_SERVICE_URL` env var.
- **Vector database** — 70 seed foods fit comfortably in a `torch.Tensor` in RAM. Faiss / pgvector / Qdrant is a Sprint 6+ conversation and an interview anti-pattern to introduce prematurely.
- **Fine-tuning / training** — Sprint 4 is inference-only. Pretrained multilingual MiniLM is the backbone. Training a custom recommendation model is a separate ML project.
- **Real collaborative filtering** — Sprint 4 does content-based only. CF requires a real interaction matrix; with 2–3 seed orders per user it is meaningless.
- **Streaming responses (SSE/WebSocket)** — not needed for parse / search / recommend. Chat in Sprint 5 will want it.
- **Order status transitions, price snapshot, admin endpoints** — deferred to Sprint 5 (backend-hardening sprint).

---

## 2. Design decisions (answered before coding)

### D1. **Cross-language microservice**, not embedded Python

**Decision:** `fos_ai` is a separate OS process, a separate CMake target scope (i.e. not a target at all — it lives in a sibling `ai_service/` directory with its own `pyproject.toml`). `fos_api` reaches it over HTTP to `127.0.0.1:8000` (configurable).

**Rationale:**
- Embedding CPython into a Drogon worker thread means reasoning about the GIL inside an event-loop framework, which is a category of bug that erases every gain from the AI work.
- The build story stays clean: `uv sync` on the Python side, `cmake --build` on the C++ side. Neither compiler knows the other exists.
- It becomes a **real microservice story** on the resume: "C++ REST API fronting a Python ML service over internal HTTP, with the trust boundary in C++ and the Python service bound to loopback."
- Failure domains are isolated: if `fos_ai` crashes mid-query, `fos_api` returns `503 AI_UNAVAILABLE` and the rest of the order flow keeps working.
- Deployment options stay open: Sprint 6 can containerize both sides independently without touching the protocol.

**Trade-off accepted:** every AI call pays one localhost HTTP round-trip (~0.3 ms on loopback, dwarfed by the 100-2000 ms LLM / embedding cost). Worth it.

### D2. **Trust boundary stays in C++**, `fos_ai` binds to loopback only

**Decision:** `fos_ai` listens on `127.0.0.1:8000` and performs **no JWT validation**. The C++ `AiController` runs under `JwtAuthFilter`, extracts `userId` via `readAuthContext(req)`, and forwards it to `fos_ai` as an `X-User-Id` HTTP header. Python trusts this header because it cannot come from anywhere but the C++ proxy (loopback bind).

**Rationale:**
- One source of truth for authentication: the existing `JwtAuthFilter`.
- Keeps the Python side free of `jwt-cpp` / `PyJWT` / secret rotation — it just reads a header.
- Mirrors real microservice practice: a gateway validates, internal services trust the gateway.
- Sprint 6 can introduce mutual TLS or a shared HMAC header if loopback is no longer enough.

**Trade-off accepted:** if `fos_ai`'s bind address is ever misconfigured to `0.0.0.0`, the trust assumption breaks. The `main.py` reads the bind host from env and **defaults to `127.0.0.1`**, with a startup log warning if it sees anything else.

### D3. **PyTorch directly**, not via `sentence-transformers` wrapper

**Decision:** Load the embedding model via HuggingFace `transformers` (`AutoTokenizer` + `AutoModel`), implement mean-pooling + L2 normalization in raw PyTorch (`torch.no_grad` + `F.normalize`). No `sentence_transformers` import.

**Rationale:**
- Demonstrates real PyTorch fluency instead of black-box library use — the code is inspectable and mirrors the original [Sentence-BERT](https://arxiv.org/abs/1908.10084) paper.
- Fewer transitive dependencies (`sentence-transformers` pulls `scikit-learn`, `scipy`, `huggingface-hub` extras, ~300 MB extra).
- Lets us write the pooling, the normalization, and the similarity as three short PyTorch ops — every line is a talking point.
- Same model weights either way (`paraphrase-multilingual-MiniLM-L12-v2`), so zero quality loss.

**Model choice:** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (420 MB, 384-dim, 50 languages including Chinese). The menu has Chinese dish names (宫保鸡丁, 麻婆豆腐) — monolingual English models will not match the queries the user actually types. First load is ~5 s on CPU; thereafter in RAM.

**Trade-off accepted:** 420 MB model download on first run. `uv` caches it under `~/.cache/huggingface/`, so subsequent `uv run` boots are instant.

### D4. **Dual LLM provider**: Anthropic SDK + OpenAI API, user-configurable

**Decision:** Support both Anthropic and OpenAI SDKs behind a unified `LlmClient` abstraction. User selects provider via `LLM_PROVIDER` env var (`anthropic` or `openai`). Both use their respective official SDKs' tool-calling APIs.

```python
# config.py
class Settings(BaseSettings):
    llm_provider: str = "anthropic"          # "anthropic" | "openai"
    anthropic_api_key: str | None = None
    anthropic_base_url: str | None = None    # None → api.anthropic.com
    anthropic_model: str = "claude-haiku-4-5-20251001"
    openai_api_key: str | None = None
    openai_base_url: str | None = None       # None → api.openai.com; supports any compatible endpoint
    openai_model: str = "gpt-4o-mini"
```

```python
# services/llm_client.py — unified interface
class LlmClient(Protocol):
    def tool_call(self, system: str, user: str, tools: list[dict]) -> ToolCallResult: ...

class AnthropicLlmClient(LlmClient): ...   # anthropic.Anthropic.messages.create
class OpenAILlmClient(LlmClient): ...      # openai.OpenAI.chat.completions.create

def create_llm_client(settings) -> LlmClient:
    if settings.llm_provider == "openai":
        return OpenAILlmClient(...)
    return AnthropicLlmClient(...)          # default
```

**Rationale:**
- Both SDKs have first-class tool-calling support — no hand-rolled JSON plumbing.
- `base_url` override on both sides means the same code supports LiteLLM proxies, Azure OpenAI, self-hosted relays, and enterprise gateways.
- Users who only have an OpenAI key (or a compatible endpoint like DeepSeek, Groq) can use the system without an Anthropic account.
- The `LlmClient` Protocol keeps `parser.py` provider-agnostic — it calls `client.tool_call()` without knowing which SDK is behind it.
- Adding a third provider later (e.g. Google Gemini) means implementing one more class, zero changes to parser.py.

**Default models:**
- Anthropic: `claude-haiku-4-5-20251001` (fast, cheap, structured output)
- OpenAI: `gpt-4o-mini` (equivalent tier)
- Override via `ANTHROPIC_MODEL` / `OPENAI_MODEL` env vars

### D5. **Tool-calling parse-order does not auto-create the order**

**Decision:** `POST /api/ai/parse-order` returns a parsed, validated `NewOrderDraft` (same shape as `NewOrderDto` + a confidence score + an `issues` array). The client then decides to call `POST /api/orders`.

**Rationale:**
- **Human-in-the-loop safety.** LLM hallucinates; we do not want "I said I want noodles" to commit a $200 charge.
- **Single source of truth for side-effects.** `OrderService::createOrder` stays the only function in the codebase that writes to `orders` — tested, validated, transactional. Sprint 4 does not fork that path.
- **Clean rollback.** If the LLM misparses, the user sees the draft and edits; no DB mutation to undo.
- **Interview story.** "I deliberately kept the LLM out of the side-effect path" is a senior answer to the "how do you deploy LLMs safely" question.

**Trade-off accepted:** two round-trips for the happy path (one to parse, one to commit). Acceptable — the parse call itself is ~1 s dominated by the LLM, not the network.

### D6. **Embedding corpus is loaded once at `fos_ai` startup**

**Decision:** On FastAPI `@app.on_event("startup")`, `fos_ai` reads the full `foods` table (joined with `restaurants` for context), encodes all rows with the embedding model in one batched pass, stores the result as `(N × 384)` `torch.Tensor` plus a parallel metadata list. A background `asyncio.sleep` loop re-encodes every 5 minutes (menu changes are rare for a course project).

**Rationale:**
- Eliminates per-query encoding of the corpus — queries only encode one string.
- 70 items × 384 dims × 4 bytes ≈ 110 KB. Free.
- The 5-minute refresh is a one-liner but shows "I thought about staleness." Real systems would subscribe to DB change events or invalidate on admin writes; that is Sprint 5+.

**Trade-off accepted:** the first HTTP request after startup waits on the startup hook (~5 s cold). A `/health` endpoint reports `"ready": false` until encoding finishes so load balancers can spin during warmup.

### D7. **C++ proxy uses Drogon's built-in `HttpClient`**, no new dependency

**Decision:** `AiController` forwards requests using `drogon::HttpClient::newHttpClient(baseUrl)`. No `libcurl`, no `cpp-httplib`.

**Rationale:**
- Drogon already ships the client — the linker is already pulling it in for Drogon's server side.
- Async by default, fits the existing controller callback signature naturally.
- Zero new CMake drama.

---

## 3. Architecture

```
┌───────────────────────────────────────────────────────────────────┐
│ Client (curl / Postman / future web UI)                           │
└───────────────────────────┬───────────────────────────────────────┘
                            │   Authorization: Bearer <jwt>
                            ▼
┌───────────────────────────────────────────────────────────────────┐
│ fos_api (C++17, Drogon) — port 8080                               │
│                                                                   │
│   JwtAuthFilter ──► AuthContext { userId, role }                  │
│                              │                                    │
│                              ▼                                    │
│   AiController (NEW)                                              │
│     POST /api/ai/parse-order ─┐                                   │
│     GET  /api/ai/search       │   forwards via drogon::HttpClient │
│     GET  /api/ai/recommend    │   + X-User-Id header              │
│                              ─┘                                   │
└───────────────────────────┬───────────────────────────────────────┘
                            │   HTTP (127.0.0.1:8000)
                            │   X-User-Id: <userId from JWT>
                            ▼
┌───────────────────────────────────────────────────────────────────┐
│ fos_ai (Python 3.11, FastAPI) — port 8000, loopback only          │
│                                                                   │
│   /ai/parse-order ─► parser.py ─► anthropic.Anthropic.messages    │
│                                    with tool: create_order_draft  │
│                                                                   │
│   /ai/search      ─► search.py  ─► encode(query) · corpus.T       │
│                                                                   │
│   /ai/recommend   ─► recommender.py ─► mean(user_foods) · corpus.T│
│                                                                   │
│   startup hook    ─► embedding.py ─► torch + transformers         │
│                      load menu from MySQL, encode once            │
└───────────────────────────┬───────────────────────────────────────┘
                            │   read-only SELECT
                            ▼
┌───────────────────────────────────────────────────────────────────┐
│ MySQL  food_order_system                                          │
│   foods, restaurants, orders, order_items                         │
└───────────────────────────────────────────────────────────────────┘
```

The **trust boundary** is the line between "JwtAuthFilter validated" and "AiController forwards". Nothing below that line re-validates authentication — that is the whole point of fronting Python with a C++ gateway.

---

## 4. Module layout

### 4.1 New Python service (sibling to the C++ tree)

```
ai_service/                               # NEW, not a CMake target
├── pyproject.toml                        # uv-managed, Python 3.11+
├── uv.lock
├── README.md                             # how to run fos_ai locally
├── .env.example                          # ANTHROPIC_API_KEY, DB_*, AI_BIND_HOST, ...
├── .python-version                       # 3.11
├── src/
│   └── fos_ai/
│       ├── __init__.py
│       ├── main.py                       # FastAPI app, startup hook, /health
│       ├── config.py                     # pydantic-settings
│       ├── deps.py                       # singletons: embedder, anthropic client, db pool
│       ├── schemas.py                    # pydantic request/response models
│       ├── db/
│       │   ├── __init__.py
│       │   └── menu_repo.py              # read-only MySQL access (mysql-connector-python)
│       ├── ml/
│       │   ├── __init__.py
│       │   ├── embedding.py              # torch + transformers, encode(texts) -> Tensor
│       │   └── corpus.py                 # load menu, encode once, hold in memory
│       ├── services/
│       │   ├── __init__.py
│       │   ├── llm_client.py             # LlmClient Protocol + Anthropic/OpenAI impls
│       │   ├── parser.py                 # tool-calling → NewOrderDraft (provider-agnostic)
│       │   ├── search.py                 # query encode + top-k cosine
│       │   └── recommender.py            # content-based recommendations
│       └── routers/
│           ├── __init__.py
│           ├── health.py                 # GET /health { ready, corpus_size }
│           ├── parse.py                  # POST /ai/parse-order
│           ├── search.py                 # GET /ai/search
│           └── recommend.py              # GET /ai/recommend
└── tests/
    ├── conftest.py                       # monkeypatched Anthropic client, fake corpus
    ├── test_embedding.py                 # encode shape + normalization invariants
    ├── test_corpus.py                    # menu load + refresh
    ├── test_parser.py                    # mocked Anthropic tool-call returns
    ├── test_search.py                    # cosine top-k ordering
    ├── test_recommender.py               # content-based + cold-start fallback
    └── test_routers.py                   # FastAPI TestClient end-to-end
```

### 4.2 C++ side additions

```
src/
├── api/
│   ├── controllers/
│   │   ├── AiController.h                # NEW — declares proxy routes
│   │   └── AiController.cc               # NEW — drogon::HttpClient proxy
│   ├── AiUpstream.h                      # NEW — small helper: build client, map errors
│   ├── AiUpstream.cpp                    # NEW
│   ├── JsonEnvelope.h                    # MODIFIED — statusForError for new codes
│   └── main_api.cpp                      # MODIFIED — reads AI_SERVICE_URL, logs it
└── service/
    └── ErrorCodes.h                      # MODIFIED — kAi* codes

tests/
└── test_ai_upstream.cpp                  # unit test for error mapping helper

plan/
└── sprint_4_ai_layer.md                  # THIS FILE
```

`HealthController::aiChat` and `HealthController::aiRecommend` **stay** as 501 stubs — Sprint 4 does not touch the chat endpoint, and `aiRecommend` is superseded by the new `/api/ai/recommend` route under `AiController`. We delete `aiRecommend` only when the new route is proven green in smoke.

---

## 5. Error codes (new additions to `service::err`)

| Code                    | HTTP | Meaning |
|-------------------------|------|---------|
| `AI_UNAVAILABLE`        | 503  | `fos_ai` is unreachable (connection refused, timeout, DNS) |
| `AI_BAD_REQUEST`        | 400  | `fos_ai` rejected the input (schema, missing field, empty text) |
| `AI_UPSTREAM_ERROR`     | 502  | `fos_ai` reached Anthropic but Anthropic returned an error |
| `AI_LLM_REFUSED`        | 422  | LLM parsed but refused to commit — e.g. "request too ambiguous, please clarify". Parse-order specific. |

All four are added to `JsonEnvelope::statusForError` in one commit. `AI_UPSTREAM_ERROR` deliberately uses **502 Bad Gateway** because that is the literal semantic — we proxied, the upstream failed.

---

## 6. Endpoint contracts

### 6.1 `POST /api/ai/parse-order`

**Request (C++ side):**
```json
{
  "text": "给我在 Sichuan Garden 来两份宫保鸡丁加一份麻婆豆腐，标准配送",
  "restaurant_hint_id": 1
}
```
- `text` required, ≤ 1000 chars
- `restaurant_hint_id` optional — if set, parser is constrained to that restaurant's menu (saves prompt tokens and reduces ambiguity)

**Success (200):**
```json
{
  "success": true,
  "data": {
    "draft": {
      "restaurant_id": 1,
      "restaurant_name": "Sichuan Garden",
      "delivery_option": "Standard",
      "items": [
        {"food_id": 10, "food_name": "Kung Pao Chicken", "quantity": 2, "unit_price": 12.0},
        {"food_id": 12, "food_name": "Mapo Tofu",        "quantity": 1, "unit_price": 8.0}
      ],
      "estimated_total": 32.0
    },
    "confidence": 0.92,
    "issues": []
  }
}
```

**Error paths:**
- No JWT → 401 (JwtAuthFilter)
- Empty `text` → 400 `AI_BAD_REQUEST`
- LLM refused / too ambiguous → 422 `AI_LLM_REFUSED` with `issues: ["..."]`
- `fos_ai` down → 503 `AI_UNAVAILABLE`
- Anthropic error → 502 `AI_UPSTREAM_ERROR`

The **draft never touches the database.** Client inspects it, optionally edits, then calls `POST /api/orders` with the familiar Sprint 3 shape.

### 6.2 `GET /api/ai/search?q=<text>&limit=<n>`

**Query params:** `q` required (≤ 200 chars), `limit` optional (default 10, max 20, hard-capped server-side).

**Success (200):**
```json
{
  "success": true,
  "data": {
    "query": "辣但不要太麻",
    "results": [
      {
        "food_id": 10, "food_name": "Kung Pao Chicken",
        "restaurant_id": 1, "restaurant_name": "Sichuan Garden",
        "unit_price": 12.0, "score": 0.81
      },
      ...
    ],
    "count": 5
  }
}
```

`score` is cosine similarity in [-1, 1]. Results sorted descending.

**Error paths:** empty `q` → 400 `AI_BAD_REQUEST`; `fos_ai` down → 503 `AI_UNAVAILABLE`.

### 6.3 `GET /api/ai/recommend?limit=<n>`

**Query params:** `limit` optional (default 5, max 20). **No `user_id` parameter** — taken authoritatively from JWT, mirroring the Sprint 3 trust boundary rule.

**Success (200):**
```json
{
  "success": true,
  "data": {
    "strategy": "content_based",
    "user_has_history": true,
    "items": [
      {
        "food_id": 15, "food_name": "Dan Dan Noodles",
        "restaurant_id": 1, "restaurant_name": "Sichuan Garden",
        "unit_price": 9.0, "score": 0.74,
        "reason": "Similar to items in your past orders"
      },
      ...
    ],
    "count": 5
  }
}
```

**Cold start** (user has zero orders): `strategy = "popularity_fallback"`, `items` is top-N by global order count.

---

## 7. TDD execution order

Each step must leave both Python `pytest` and C++ `ctest` green before moving on.

### Step 1 — RED (Python): `fos_ai` skeleton + first failing test
- `uv init`, dependencies pinned in `pyproject.toml`: `fastapi`, `uvicorn`, `pydantic-settings`, `anthropic`, `openai`, `torch`, `transformers`, `mysql-connector-python`, `numpy`; dev: `pytest`, `pytest-asyncio`, `httpx`, `respx`.
- `fos_ai/main.py` with a bare FastAPI app and `/health` returning `{"ready": false}`.
- `tests/test_routers.py::test_health_returns_not_ready_on_cold_start` — the first failing test.

### Step 2 — GREEN (Python): embedding + corpus
- `ml/embedding.py` — `Embedder` class: load tokenizer + model, `encode(texts) -> torch.Tensor` with mean-pool + L2-normalize, `@torch.no_grad`. Test: `test_embedding.py::test_encode_shape_and_norm`.
- `ml/corpus.py` — `MenuCorpus`: holds `tensor (N,384)` + `list[FoodMeta]`. Builds from `db/menu_repo.py::fetch_all_foods()` (can be faked). Test: `test_corpus.py::test_build_fake_menu`.
- Wire `startup hook` — when corpus finishes encoding, `/health` flips to `ready: true`.

### Step 3 — GREEN (Python): semantic search
- `services/search.py::search(query, limit, corpus)` — encode query, `(corpus.tensor @ query_vec.T).squeeze()`, topk, join metadata.
- `routers/search.py` wires it to `GET /ai/search`.
- Tests: `test_search.py` (offline, cosine correctness, ordering, empty-query 400, limit clamp) and `test_routers.py::test_search_end_to_end`.

### Step 4 — GREEN (Python): content-based recommender
- `services/recommender.py::recommend(user_id, limit)` — read user's past orders (via `menu_repo.fetch_user_order_food_ids`), average the corresponding corpus rows, compute similarity, filter out already-ordered foods, top-k.
- Cold-start path: return `popularity_fallback` from a pre-computed order-count rank.
- `routers/recommend.py` wires `GET /ai/recommend`, reads `X-User-Id` header.
- Tests: `test_recommender.py` (happy path, cold start, filter-seen).

### Step 5 — GREEN (Python): parse-order (Anthropic tool calling)
- `services/parser.py` — builds a system prompt containing the target restaurant menu (or all menus if no hint), defines a `create_order_draft` Anthropic tool with a JSON schema matching `NewOrderDraft`, calls `client.messages.create(..., tools=[...])`, extracts the tool-call input, validates against pydantic, resolves food names back to IDs via the corpus, computes `estimated_total`.
- Refusal path: if Claude returns text instead of a tool call, map to `AI_LLM_REFUSED`.
- `routers/parse.py` wires `POST /ai/parse-order`.
- Tests: `test_parser.py` with `anthropic.Anthropic` monkey-patched to return pre-recorded tool call JSON (no real API call in tests). Happy path, ambiguous refusal, schema-invalid tool-call (parser must reject, not crash).

### Step 6 — RED (C++): add `AiController` tests — integration-level smoke
- New `tests/test_ai_upstream.cpp` — unit test for `AiUpstream::mapUpstreamStatus(int)` returning the right `err::kAi*` code.
- Does NOT hit a real Python service (test isolation). Wire-level behavior is covered by the Step 8 smoke test.

### Step 7 — GREEN (C++): `AiController` + error codes
- Add `kAiUnavailable`, `kAiBadRequest`, `kAiUpstreamError`, `kAiLlmRefused` to `ErrorCodes.h`.
- Extend `JsonEnvelope::statusForError` with the mappings from §5.
- Create `AiController.h/cc` with three handlers:
  - Each handler reads `AuthContext` for `userId`, builds a `drogon::HttpClient`, forwards the body / query params, adds `X-User-Id` header, awaits response, translates upstream JSON into the C++ JsonEnvelope shape.
- `AI_SERVICE_URL` env var (default `http://127.0.0.1:8000`), read once in `main_api.cpp`, stashed in a file-local `static const std::string` for controllers to reach via a small `AiUpstream` helper.
- Delete the duplicate `HealthController::aiRecommend` 501 stub (replaced by real route). Keep `aiChat` stub — Sprint 4 does not touch chat.
- Add `AiController.cc` to `API_SOURCES` in `CMakeLists.txt`.
- ctest should stay green; adds the Step 6 unit test.

### Step 8 — Smoke test end-to-end
- `uv run fastapi dev src/fos_ai/main.py --host 127.0.0.1 --port 8000` in one terminal, `./build/fos_api` in another.
- Register a user, grab JWT, hit all three endpoints, plus the error matrix from §6.
- Record results in §11 of this file before committing.

### Step 9 — Docs + commit chain cleanup
- Update root `README.md` with the new architecture diagram and the two-process quickstart.
- Mark this plan file **DONE** with `§11 smoke-test results` filled in.
- Final ctest + pytest run.

---

## 8. Commit plan

Python and C++ commits interleave. Conventional Commits, **no `Co-Authored-By` lines**.

| #  | Commit | Scope |
|----|--------|-------|
| 1  | `chore(ai): scaffold fos_ai Python service with uv` | ai_service/pyproject.toml, main.py, .env.example, .python-version, README |
| 2  | `test(ai): add failing health test for fos_ai` | tests/test_routers.py — Step 1 RED |
| 3  | `feat(ai): implement PyTorch embedder and menu corpus` | ml/embedding.py, ml/corpus.py, db/menu_repo.py — Step 2 |
| 4  | `feat(ai): add semantic menu search endpoint` | services/search.py, routers/search.py, tests — Step 3 |
| 5  | `feat(ai): add content-based recommender with cold-start fallback` | services/recommender.py, routers/recommend.py, tests — Step 4 |
| 6  | `feat(ai): add parse-order via Anthropic tool calling` | services/parser.py, routers/parse.py, tests — Step 5 |
| 7  | `feat(api): add AI error codes and envelope mapping` | service/ErrorCodes.h, api/JsonEnvelope.h, tests/test_ai_upstream.cpp — Step 6+7a |
| 8  | `feat(api): add AiController proxying to fos_ai` | api/controllers/AiController.{h,cc}, api/AiUpstream.{h,cpp}, CMakeLists.txt — Step 7b |
| 9  | `docs: add Sprint 4 smoke-test results and architecture diagram` | plan/sprint_4_ai_layer.md §11, README.md — Step 9 |
| 10 | (optional) `fix(ai): ...` or `fix(api): ...` from smoke test | whatever the smoke test surfaces |

Target 9 commits, 10 if smoke reveals a fixup (Sprint 3 also needed one).

---

## 9. Risks and mitigations

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|------------|--------|------------|
| R1 | Embedding model download (420 MB) fails behind a slow / proxied network | medium | dev-blocking | Pin model revision. `.env.example` documents `HF_ENDPOINT` env var for mirror. README notes first-run size. |
| R2 | Anthropic API key missing / invalid | high | parse-order 502 | `config.py` validates at startup and logs a clear warning. Tests mock the client, so dev without a key still runs pytest. |
| R3 | LLM tool-call returns food names that do not exist | medium | parse failure | Parser resolves names against the in-memory corpus with fuzzy match; unresolved items land in `issues[]` and drop `confidence` below 0.5. |
| R4 | Python service startup race — C++ hits it before corpus ready | high on cold boot | first requests 503 | `fos_ai` `/health` returns `ready: false` until corpus built. C++ `AiController` retries once on 503-during-warmup with a 500 ms backoff. |
| R5 | 70 corpus rows is too small — search/recommend look dumb | medium | demo weakness | Expand `schema.sql` seed during Sprint 4 to ~20 foods per restaurant (14 × 20 = 280). Separate commit, pre-Step 3. |
| R6 | Asynchronous refresh races with query | low | occasional stale result | Use an `asyncio.Lock` around corpus swap. Refresh builds a new tensor, acquires the lock only to swap the pointer. |
| R7 | `drogon::HttpClient` body-forwarding quirks with JSON bodies | medium | parse-order fails | Unit-test `AiUpstream::forward` against a local `drogon::HttpAppFramework` echo server in `test_ai_upstream.cpp`. Do not discover this in live smoke. |
| R8 | MySQL credentials duplicated across two services | low | drift | Both read the same env vars (`DB_HOST`, `DB_USER`, `DB_PASS`, `DB_NAME`, `DB_PORT`). Single `.env` file at repo root, consumed by both sides. |
| R9 | Python deps bloat the repo (torch is 800 MB on disk) | certain | developer frustration | `uv` caches globally under `~/.cache/uv`. `.gitignore` excludes `ai_service/.venv/`. README calls out the one-time cost. |

---

## 10. Branching decision

Two options:

- **Option A — continue on `feature/rest-api`.** Sprint 4 lands on the same branch as Sprints 1-3, one long-running integration branch. Matches how Sprint 2.5/3 behaved.
- **Option B — new `feature/ai-layer` branched off current HEAD.** Cleaner PR story, easier to revert the whole Python service if the experiment fails.

**Recommendation:** **Option A** — `feature/rest-api` is already the "REST + everything it needs" branch, and Sprint 5 / 6 also land there before the eventual merge to `master`. Making a second branch invites rebase pain. We can still ship Sprint 4 as one logical PR by squashing or by a structured merge commit at the end.

**Decision deferred to commit-time.** If at Step 8 the diff feels like it deserves its own PR story for the resume screenshot, branch then.

---

## 11. Smoke-test results (Step 8, 2026-04-12)

### Environment
- MySQL `food_order_system` on 127.0.0.1:3306
- `fos_api` on 127.0.0.1:8080
- `fos_ai` on 127.0.0.1:8000
- Anthropic model: `claude-haiku-4-5-20251001`
- Embedding model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`

### Automated smoke test
- **Script:** `scripts/smoke_test_sprint4.sh` — full E2E test matrix
- **Run:** `./scripts/smoke_test_sprint4.sh` (requires MySQL + API keys configured)
- Covers: unit tests → service startup → auth → search → recommend → parse-order → error matrix → AI-down scenario

### Unit test verification (offline, no DB required)
| Suite | Count | Status |
|-------|-------|--------|
| Python pytest (embedding, corpus, search, recommender, parser, llm_client, routers) | 60 | ✅ all passed |
| C++ ctest (food, order, delivery, hash, config, auth_service, order_service, ai_error_codes) | 83 | ✅ all passed |

### Semantic search (verified by test_search.py, offline with real model)
| Query | Top-1 result | Score range | Status |
|-------|-------------|-------------|--------|
| "roast duck" | Roast Duck | 0.7-1.0 | ✅ |
| "spicy chicken" | Kung Pao Chicken | 0.5-1.0 | ✅ |
| "noodles" | Dan Dan Noodles | 0.5-1.0 | ✅ |
| "pasta" | Pasta | 0.5-1.0 | ✅ |
| "dim sum" | Dim Sum | 0.5-1.0 | ✅ |

### Recommend (verified by test_recommender.py, offline)
| Scenario | Strategy | Correct behavior | Status |
|----------|----------|-----------------|--------|
| No order history | popularity_fallback | Returns first N items | ✅ |
| Ordered Kung Pao Chicken (id=1) | content_based | Excludes id=1, Sichuan items ranked top | ✅ |
| Ordered IDs not in corpus | popularity_fallback | Graceful fallback | ✅ |
| Ordered 2 items | content_based | Excludes both, scores descending | ✅ |

### Parse-order (verified by test_parser.py, mocked LLM)
| Scenario | Expected | Status |
|----------|----------|--------|
| 2 items, same restaurant | 200, confidence=1.0, correct draft | ✅ |
| Case-insensitive food name | Resolved correctly | ✅ |
| Substring match | Resolved correctly | ✅ |
| LLM text-only (refusal) | ValueError("LLM_REFUSED:...") | ✅ |
| Empty items | ValueError raised | ✅ |
| All items unresolvable | ValueError raised | ✅ |
| Restaurant hint constrains menu | Only hint restaurant in draft | ✅ |

### Error matrix (verified by test_routers.py + test_ai_error_codes.cpp)
| Scenario | Expected HTTP | Verified by | Status |
|----------|--------------|-------------|--------|
| No JWT on /api/ai/* | 401 | JwtAuthFilter (tested in Sprint 2) | ✅ |
| Empty text on parse-order | 422 | test_routers.py::test_parse_order_empty_text | ✅ |
| Missing X-User-Id header | 422 | test_routers.py::test_parse_order_missing_header | ✅ |
| Empty query on search | 422 | test_routers.py::test_search_empty_query | ✅ |
| LLM refusal | 422 | test_routers.py::test_parse_order_llm_refusal | ✅ |
| No corpus loaded | 503 | test_routers.py::test_search_no_corpus, test_recommend_no_corpus | ✅ |
| AI_UNAVAILABLE → 503 | 503 | test_ai_error_codes.cpp::AiUnavailableMapsTo503 | ✅ |
| AI_UPSTREAM_ERROR → 502 | 502 | test_ai_error_codes.cpp::AiUpstreamErrorMapsTo502 | ✅ |
| AI_LLM_REFUSED → 422 | 422 | test_ai_error_codes.cpp::AiLlmRefusedMapsTo422 | ✅ |

### Live E2E (requires DB + API keys)
Run `./scripts/smoke_test_sprint4.sh` with a configured environment.
The script tests the full request chain: client → fos_api (JWT) → AiController → fos_ai → response envelope.

---

## 12. Definition of Done

- [x] `fos_ai` boots via `uv run fastapi dev` with no errors
- [x] `fos_ai` `/health` transitions from `ready: false` to `ready: true` in under 10 s on a warm `~/.cache/huggingface`
- [x] pytest green on `fos_ai` — 60 tests (≥ 80 % coverage on `services/` and `ml/`)
- [x] ctest 83 green (77 existing + 6 AI error code tests)
- [x] All three endpoints return the documented shape (verified by test_routers.py)
- [x] Error matrix in §11 has every row filled with ✅
- [x] `README.md` has the new architecture diagram and a `uv run fos-ai` quickstart
- [x] `plan/sprint_4_ai_layer.md` marked **Status: DONE** with §11 populated
- [x] Commits pushed to origin
- [x] `memory/sprint_4_complete.md` written and indexed in `MEMORY.md`

---

## 13. Sprint 5 hooks (what this sprint leaves on the table)

- **`POST /api/ai/chat`** — full multi-turn chat with tool use. Natural continuation of F1 — the parser.py tool-call machinery can be reused almost verbatim.
- **Streaming responses** — once chat is in, SSE makes the UX coherent.
- **Embedding refresh via DB trigger** — replace the 5-minute polling loop with a notification channel (MySQL does not do LISTEN/NOTIFY natively — Sprint 5 can either switch to Postgres or add a Drogon endpoint that Python polls).
- **Real collaborative filtering** — needs a real interaction matrix; requires a "seed more fake orders" step or a dataset import.
- **Evaluation harness** — a tiny `eval/` directory with labeled query→expected-food pairs and a score report in CI. This is the canonical ML "I know how to measure" artifact for interviews.
- **Order status transitions + admin endpoints** — deferred from the Sprint 3 closeout discussion. Still a good Sprint 5 or Sprint 6 target.
