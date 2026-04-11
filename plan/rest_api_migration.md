# REST API Migration Plan

**Branch:** `feature/rest-api`
**Goal:** Transform the CLI-only FoodOrderSystem into a Drogon-based HTTP backend while
keeping the CLI alive as a demonstration client. Preserve clean extension points for a
future AI/LLM layer (Sprint 5+, separate plan).

## Guiding Principles

1. **Service layer is the contract.** All business logic lives in `src/service/*`.
   Controllers (HTTP) and the legacy CLI both call services — no `std::cin` in services.
   This is what lets the future LLM layer call the exact same methods via function
   calling.
2. **Immutable request/response DTOs.** Controllers translate HTTP ↔ DTO ↔ service calls.
3. **Thread-safe DB.** Replace the single-connection singleton with Drogon's built-in
   MySQL client (backed by a connection pool). Legacy `Database` gets wrapped or
   re-implemented as a thin adapter.
4. **AI/LLM hooks (reserved now, implemented later):**
   - Every service method must be callable without a request context.
   - Emit a structured event for each state-changing action (order created, status
     changed, rating submitted). Events go through an `EventBus` abstraction whose
     default impl is a no-op logger. Later we swap in a Redis Stream / Kafka producer
     and the LLM consumer reads from there.
   - Reserve `/api/ai/chat` and `/api/ai/recommend` route prefixes, returning
     `501 Not Implemented` from day one so the routing tree is stable.
   - Service interfaces expose machine-readable JSON schemas (used later for LLM
     function calling).

## Target Architecture

```
┌────────────────────┐        ┌────────────────────┐
│  CLI client        │        │  HTTP client       │
│  (refactored CLI)  │        │  (curl, Postman,   │
│                    │        │   future web UI)   │
└─────────┬──────────┘        └─────────┬──────────┘
          │                             │
          │                       ┌─────▼──────────┐
          │                       │ Drogon HTTP    │
          │                       │ Controllers    │
          │                       │ (src/api/)     │
          │                       └─────┬──────────┘
          │                             │
          └──────────┬──────────────────┘
                     │
           ┌─────────▼──────────┐
           │  Service Layer     │ ← AI/LLM layer will also plug in here
           │  (src/service/)    │
           │  - AuthService     │
           │  - OrderService    │
           │  - RestaurantSvc   │
           │  - MenuService     │
           └─────────┬──────────┘
                     │
           ┌─────────▼──────────┐     ┌──────────────┐
           │  Repository Layer  │────▶│  EventBus    │
           │  (src/repo/)       │     │  (no-op now) │
           └─────────┬──────────┘     └──────────────┘
                     │
           ┌─────────▼──────────┐
           │  MySQL (Drogon     │
           │  DbClient pool)    │
           └────────────────────┘
```

## Sprint Breakdown

### Sprint 1 — Skeleton & Health Check (1–2 days) **← STARTING NOW**

**Deliverable:** `curl http://localhost:8080/health` returns `{"status":"ok","db":"ok"}`

- [ ] Add Drogon + nlohmann_json via CMake FetchContent (or find_package fallback)
- [ ] Create `src/api/` for Drogon controllers
- [ ] Create `src/service/` directory with empty headers for future services
- [ ] Create `src/dto/` for request/response structs + JSON serialization
- [ ] Add `HealthController` with `GET /health` and `GET /api/ai/chat` (501 stub)
- [ ] Refactor `main.cpp` to launch Drogon app; move legacy CLI entry into
      a secondary binary `fos_cli` behind a `--cli` flag or a second executable target
- [ ] Add `config.example` keys: `HTTP_HOST`, `HTTP_PORT`, `HTTP_THREADS`
- [ ] Add `tests/test_health.cpp` (integration test: boot app, hit /health)

**Exit check:** `curl localhost:8080/health` returns JSON + CI stays green.

---

### Sprint 2 — Auth + User/Restaurant Reads (2–3 days)

**Deliverable:** Register → login → JWT → read menu works end to end.

- [ ] Create `AuthService` (wraps HashUtil + Database user ops, no stdin)
- [ ] Create `RestaurantService` + `MenuService`
- [ ] JWT library: `jwt-cpp` (header-only). `config.example` gets `JWT_SECRET`
- [ ] Endpoints:
  - `POST /api/auth/register` → `{username, password}` → `{userId}`
  - `POST /api/auth/login` → `{username, password}` → `{token, role}`
  - `GET /api/restaurants` → list
  - `GET /api/restaurants/{id}/menu` → list of foods
- [ ] Global JWT filter (Drogon `HttpFilter`) that populates a per-request user context
- [ ] Unified error envelope: `{ "success": bool, "data": ..., "error": { "code", "message" } }`
- [ ] Unit tests for services, integration tests for endpoints

**Exit check:** Register + login + fetch menu works via curl. Invalid token returns 401.

---

### Sprint 3 — Orders + Caching + AI Hooks Reserved (3–4 days)

**Deliverable:** Order lifecycle + Redis-cached menu + AI endpoint stubs.

- [ ] Create `OrderService` (create, list, update status, rate, delete)
- [ ] Endpoints:
  - `POST /api/orders` (customer)
  - `GET /api/orders` (own orders) + admin scope for `?all=true`
  - `GET /api/orders/{id}`
  - `PATCH /api/orders/{id}/status`
  - `PATCH /api/orders/{id}/rating`
  - `DELETE /api/orders/{id}`
- [ ] Polymorphic JSON for `Delivery` (tag field: `standard` / `express` / `premium`)
- [ ] Integrate `redis-plus-plus` (CMake FetchContent). Connection pool config.
- [ ] Cache:
  - `restaurant:all` with TTL 60s
  - `restaurant:{id}:menu` with TTL 60s
  - Invalidate on admin menu mutation
- [ ] Define `EventBus` interface + `NoopEventBus` (default) + `LoggingEventBus`.
      Fire `OrderCreated`, `OrderStatusChanged`, `OrderRated`. These are the hooks the
      LLM layer will later subscribe to.
- [ ] `/api/ai/chat` and `/api/ai/recommend` return 501 with a body that lists the
      currently reserved shape, so future clients can already start against the stub

**Exit check:** Full order lifecycle via curl. Menu second-hit served from Redis
(verified via log). Event bus logs state transitions.

---

### Sprint 4 — Ops Polish: Docker, Metrics, Load Test, README (2 days)

**Deliverable:** `docker compose up` boots app + mysql + redis + grafana (optional).

- [ ] Multi-stage `Dockerfile` (builder stage compiles, runtime stage slim)
- [ ] `docker-compose.yml` with `app`, `mysql`, `redis` services + healthchecks
- [ ] `/metrics` endpoint (Prometheus exposition format). Counters for request count,
      order creation count, cache hit/miss, DB errors.
- [ ] Structured logging: switch Logger to emit JSON lines when `LOG_FORMAT=json`.
      Include request id (generated in a Drogon filter).
- [ ] Load test with `wrk`, capture:
  - baseline QPS and P99 for `GET /api/restaurants`
  - after-cache QPS and P99
  - `POST /api/orders` sustained throughput
- [ ] Rewrite root `README.md`:
  - architecture diagram
  - quickstart (`docker compose up`)
  - API reference (or link to Postman collection)
  - benchmark numbers table
  - roadmap that mentions the reserved AI/LLM layer

**Exit check:** Fresh clone + `docker compose up` yields a running API. README has real
numbers, not placeholders.

---

### Sprint 5 — AI/LLM Layer (SEPARATE plan file, later)

Hooks reserved in earlier sprints:
- `/api/ai/chat` route slot
- `EventBus` for async consumption
- Service methods callable without a request context
- DTO JSON shapes will become LLM tool schemas

A future `plan/ai_llm_layer.md` will cover: Claude API integration, function calling
tool definitions, natural-language order placement, pgvector/Qdrant embedding for
menu recommendation, RAG over FAQ/order status.

## Risks / Open Questions

1. **Drogon macOS install**: need `brew install drogon` or `FetchContent`. The latter
   compiles from source (slow first build but reproducible). Start with FetchContent,
   fall back to `find_package`.
2. **Database singleton refactor**: Drogon's `DbClient` replaces the raw
   `mysql_stmt_*` layer. We will wrap the existing `Database` methods in a new
   `LegacyDbAdapter` that uses Drogon's pool underneath, OR rewrite the repository
   methods in Sprint 2. Decision: **rewrite incrementally** per service — the
   existing `Database` stays usable for the CLI path during the migration.
3. **Polymorphic Delivery JSON**: must be tag-based (`"type": "express"`) — plain
   pointer serialization won't survive the wire.
4. **Test strategy**: integration tests will need a test MySQL. Use a dedicated
   `food_order_system_test` database. Sanitize between tests via `TRUNCATE`.
5. **Thread-safe Logger/Config singletons**: verify they are safe under concurrent
   access. Logger is currently stderr + optional file — needs a mutex on file writes.

## Definition of Done (whole plan)

- REST API covers register/login/browse/order/admin flows
- All endpoints return unified JSON envelope
- JWT auth enforced on protected routes
- Redis caching measurable via wrk benchmark
- Docker Compose boots the full stack
- README has architecture diagram + benchmark numbers
- AI/LLM hook points (events, /api/ai/*, service-layer access) are in place and
  documented in this file
