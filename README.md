# Food Order System

A full-stack food ordering system with a C++17 REST API, Python AI microservice (PyTorch + LLM), MySQL database, JWT authentication, and a legacy interactive CLI.

## Architecture

```
Client (curl / Postman / web UI)
        |   Authorization: Bearer <jwt>
        v
+-----------------------------------------------+
|  fos_api  (C++17, Drogon)  :8080              |
|                                                |
|  JwtAuthFilter -> AuthContext { userId, role }  |
|       |                                        |
|       +-- AuthController     POST /api/auth/*  |
|       +-- RestaurantController GET /api/restaurants |
|       +-- OrderController    POST/GET /api/orders  |
|       +-- AiController       /api/ai/*  ----+  |
|       +-- HealthController   GET /health    |  |
+--------------------------------------+------+--+
                                       | HTTP (loopback)
                                       | X-User-Id header
                                       v
+-----------------------------------------------+
|  fos_ai  (Python 3.11, FastAPI)  :8000        |
|                                                |
|  POST /ai/parse-order -> parser.py -> LLM     |
|  GET  /ai/search      -> search.py -> PyTorch |
|  GET  /ai/recommend   -> recommender.py       |
|  POST /ai/chat        -> chat_engine.py       |
|       ReAct loop, 4 tools, SSE streaming      |
|                                                |
|  Startup: load MiniLM model, encode menu,     |
|           init SessionStore (30-min TTL)      |
+-----------------------------------------------+
        |   read-only SELECT
        v
+-----------------------------------------------+
|  MySQL  food_order_system                      |
|  users, restaurants, foods, orders, riders     |
+-----------------------------------------------+
```

**Trust boundary:** JWT validation happens in C++ (`JwtAuthFilter`). The Python service binds to loopback only and trusts the `X-User-Id` header forwarded by `AiController`.

## Features

### REST API (fos_api)
- **Authentication** — register, login (JWT), role-based access (customer/admin)
- **Restaurants** — list all, get by ID with menu
- **Orders** — create, list (own/all for admin), get by ID
- **AI proxy** — forwards to fos_ai with JWT-extracted userId

### AI Service (fos_ai)
- **Parse Order** — natural language to structured order draft via LLM tool-calling (Anthropic/OpenAI)
- **Semantic Search** — encode query with MiniLM, cosine similarity against pre-encoded menu corpus
- **Recommendations** — content-based (user profile from order history) with cold-start popularity fallback
- **Conversational Chat** — multi-turn agent with ReAct-style tool loop over `search_menu`, `create_order_draft`, `check_order_status`, `get_recommendations`; SSE streaming; in-memory session store with TTL eviction

### Legacy CLI (fos_cli)
- Interactive console with menus, order management, admin panel
- Same MySQL backend as the REST API

### Technical Highlights
- **Dual LLM provider** — Anthropic SDK + OpenAI API behind a unified `LlmClient` Protocol
- **Raw PyTorch embeddings** — mean-pooling + L2-normalization, no `sentence-transformers` wrapper
- **Microservice architecture** — C++ gateway + Python ML service, separate failure domains
- **Prepared statements** — `mysql_stmt_*` for SQL injection prevention
- **JWT auth** — HS256 tokens, configurable TTL
- **208 tests** — 101 GoogleTest (C++) + 107 pytest (Python) + 4 quality-gated eval cases (Hit@5 ≥ 0.80, MRR ≥ 0.60)

## Prerequisites

- **C++ Compiler** with C++17 support (GCC 7+, Clang 5+, MSVC 2017+)
- **CMake** 3.16+
- **MySQL Server** 5.7+ or 8.0+
- **Python** 3.11+ with [uv](https://docs.astral.sh/uv/)
- **Drogon** framework (fetched automatically by CMake if not found)

## Quick Start

### 1. Database Setup

```bash
mysql -u root -p -e "CREATE DATABASE food_order_system;"
mysql -u root -p food_order_system < src/db/schema.sql
```

### 2. Build C++ (fos_api + fos_cli + tests)

```bash
mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
cmake --build .
ctest --output-on-failure   # 83 tests
```

### 3. Install Python AI Service

```bash
cd ai_service
uv sync                     # install dependencies
uv run pytest tests/ -q           # 107 unit tests
uv run pytest eval/ -m eval -s    # 4 quality-gated eval cases (Hit@5, MRR)
```

### 4. Configure

```bash
cp config.example config

# Edit config with your DB password and JWT secret:
#   DB_PASS=yourpassword
#   JWT_SECRET=$(openssl rand -hex 32)

# For AI features, set one of:
export ANTHROPIC_API_KEY=sk-ant-...
# or
export LLM_PROVIDER=openai
export OPENAI_API_KEY=sk-...
```

### 5. Run Both Services

```bash
# Terminal 1: Python AI service
cd ai_service
uv run uvicorn fos_ai.main:app --host 127.0.0.1 --port 8000

# Terminal 2: C++ REST API
./build/fos_api
```

### 6. Try It

```bash
# Health check
curl http://localhost:8080/health

# Register + login
curl -X POST http://localhost:8080/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"demo","password":"Demo1234!"}'

TOKEN=$(curl -s -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"demo","password":"Demo1234!"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['token'])")

# Semantic search
curl "http://localhost:8080/api/ai/search?q=spicy+chicken&limit=3" \
  -H "Authorization: Bearer $TOKEN"

# Recommendations (cold start)
curl "http://localhost:8080/api/ai/recommend?limit=5" \
  -H "Authorization: Bearer $TOKEN"

# Parse order (requires LLM API key)
curl -X POST http://localhost:8080/api/ai/parse-order \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"two kung pao chicken and one mapo tofu","restaurant_hint_id":1}'
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | `127.0.0.1` | MySQL server host |
| `DB_USER` | `root` | MySQL username |
| `DB_PASS` | *(empty)* | MySQL password |
| `DB_NAME` | `food_order_system` | Database name |
| `DB_PORT` | `3306` | MySQL server port |
| `JWT_SECRET` | *(empty)* | HS256 signing key (required for auth) |
| `JWT_TTL_HOURS` | `24` | Token expiry in hours |
| `HTTP_HOST` | `0.0.0.0` | fos_api bind address |
| `HTTP_PORT` | `8080` | fos_api listen port |
| `AI_SERVICE_URL` | `http://127.0.0.1:8000` | fos_ai base URL for proxy |
| `LLM_PROVIDER` | `anthropic` | `anthropic` or `openai` |
| `ANTHROPIC_API_KEY` | *(empty)* | Anthropic API key |
| `OPENAI_API_KEY` | *(empty)* | OpenAI API key (or compatible endpoint) |
| `ANTHROPIC_MODEL` | `claude-haiku-4-5-20251001` | Anthropic model ID |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model ID |

## Project Structure

```
FoodOrderSystem/
  CMakeLists.txt              # C++ build (fos_api, fos_cli, fos_tests, fos_ai_tests)
  config.example              # Config template
  src/
    main.cpp                  # CLI entry point
    api/
      main_api.cpp            # REST API entry point (Drogon)
      AuthContext.h/cpp        # JWT claims wrapper
      JsonEnvelope.h           # Unified JSON response envelope
      JsonBody.h               # Request body validation helpers
      controllers/
        HealthController.h/cc  # GET /health, POST /api/ai/chat (501 stub)
        AuthController.h/cc    # POST /api/auth/register, /login, GET /me
        RestaurantController.h/cc  # GET /api/restaurants
        OrderController.h/cc   # POST/GET /api/orders
        AiController.h/cc      # AI proxy -> fos_ai (Sprint 4)
      filters/
        JwtAuthFilter.h/cc     # JWT Bearer validation
    service/
      ErrorCodes.h             # All error code constants (incl. AI codes)
      AuthService.h/cpp        # User registration + login
      OrderService.h/cpp       # Order CRUD with transactions
      RestaurantService.h/cpp  # Restaurant queries
      JwtService.h/cpp         # JWT sign + verify (HS256)
    model/ core/ auth/ db/ util/  # Domain layer (see CLAUDE.md)
  ai_service/                  # Python AI microservice
    pyproject.toml             # uv-managed, Python 3.11+
    src/fos_ai/
      main.py                  # FastAPI app with lifespan
      config.py                # pydantic-settings
      deps.py                  # Singletons (embedder, corpus, LLM client)
      schemas.py               # Request/response models
      ml/
        embedding.py           # PyTorch MiniLM embedder (384-dim)
        corpus.py              # Pre-encoded menu corpus
      services/
        llm_client.py          # Dual LLM provider (Anthropic + OpenAI)
        parser.py              # NL -> OrderDraft via tool-calling
        search.py              # Cosine top-k semantic search
        recommender.py         # Content-based + cold-start fallback
      routers/
        health.py parse.py search.py recommend.py
      db/
        menu_repo.py           # Read-only MySQL menu access
    tests/                     # 60 pytest cases
  tests/                       # 83 GoogleTest cases (C++)
  scripts/
    smoke_test_sprint4.sh      # E2E smoke test script
  plan/                        # Sprint planning documents
```

## Design Patterns

| Pattern | Location | Purpose |
|---------|----------|---------|
| Factory + Registry | `FoodFactory` | Create Food by cuisine type string |
| Singleton | `Database`, `Logger`, `Config` | Single instances, thread-safe access |
| Strategy | `Delivery` hierarchy | Interchangeable delivery options |
| Protocol | `LlmClient` | Provider-agnostic LLM abstraction |
| Proxy | `AiController` | C++ gateway forwards to Python AI service |
| Content-Based Filtering | `recommender.py` | User profile from order history embeddings |
| Repository | `menu_repo.py` | Data access abstraction for menu |

## Seed Data

- **14 restaurants** across 10 cuisine types
- **70 food items** with prices, descriptions, and preferences
- **10 delivery riders**

## License

This project is developed as a course assignment.
