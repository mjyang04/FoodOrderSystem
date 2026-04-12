#!/usr/bin/env bash
# Sprint 4 E2E Smoke Test Script
#
# Prerequisites:
#   1. MySQL running with food_order_system DB populated (schema.sql applied)
#   2. config file in project root with DB_PASS, JWT_SECRET set
#   3. ANTHROPIC_API_KEY or OPENAI_API_KEY set in environment
#   4. fos_api built: cmake --build build
#   5. ai_service dependencies installed: cd ai_service && uv sync
#
# Usage:
#   ./scripts/smoke_test_sprint4.sh
#
# The script starts both services, runs the test matrix, then shuts down.

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API_URL="http://127.0.0.1:8080"
AI_URL="http://127.0.0.1:8000"
PASS=0
FAIL=0
SKIP=0

log_pass() { echo -e "${GREEN}[PASS]${NC} $1"; ((PASS++)); }
log_fail() { echo -e "${RED}[FAIL]${NC} $1"; ((FAIL++)); }
log_skip() { echo -e "${YELLOW}[SKIP]${NC} $1"; ((SKIP++)); }
log_info() { echo -e "[INFO] $1"; }

cleanup() {
    log_info "Shutting down services..."
    [ -n "${AI_PID:-}" ] && kill "$AI_PID" 2>/dev/null || true
    [ -n "${API_PID:-}" ] && kill "$API_PID" 2>/dev/null || true
    wait 2>/dev/null || true
    log_info "Cleanup complete."
}
trap cleanup EXIT

# ---- 0. Pre-flight checks ----
log_info "=== Pre-flight checks ==="

if [ ! -f "$PROJECT_ROOT/build/fos_api" ]; then
    echo "ERROR: build/fos_api not found. Run: cmake --build build"
    exit 1
fi

if ! command -v uv &>/dev/null; then
    echo "ERROR: uv not found. Install: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# ---- 1. Run unit tests ----
log_info "=== Unit tests ==="

log_info "Running C++ ctest..."
cd "$PROJECT_ROOT/build"
if ctest --output-on-failure -j4 2>&1 | tail -1 | grep -q "tests passed"; then
    CTEST_COUNT=$(ctest -N 2>&1 | tail -1 | grep -oE '[0-9]+')
    log_pass "ctest: $CTEST_COUNT tests passed"
else
    log_fail "ctest: some tests failed"
fi

log_info "Running Python pytest..."
cd "$PROJECT_ROOT/ai_service"
if uv run pytest tests/ -q --tb=line 2>&1 | tail -1 | grep -q "passed"; then
    PYTEST_COUNT=$(uv run pytest tests/ -q --tb=line 2>&1 | tail -1 | grep -oE '[0-9]+ passed')
    log_pass "pytest: $PYTEST_COUNT"
else
    log_fail "pytest: some tests failed"
fi
cd "$PROJECT_ROOT"

# ---- 2. Start fos_ai (Python) ----
log_info "=== Starting fos_ai on $AI_URL ==="

export DB_HOST="${DB_HOST:-127.0.0.1}"
export DB_USER="${DB_USER:-root}"
export DB_PASS="${DB_PASS:-}"
export DB_NAME="${DB_NAME:-food_order_system}"
export DB_PORT="${DB_PORT:-3306}"
export LLM_PROVIDER="${LLM_PROVIDER:-anthropic}"
export AI_BIND_HOST="127.0.0.1"
export AI_BIND_PORT="8000"

cd "$PROJECT_ROOT/ai_service"
uv run uvicorn fos_ai.main:app --host 127.0.0.1 --port 8000 &
AI_PID=$!
cd "$PROJECT_ROOT"

# Wait for fos_ai to become ready
log_info "Waiting for fos_ai health..."
for i in $(seq 1 30); do
    if curl -s "$AI_URL/health" 2>/dev/null | grep -q '"ready"'; then
        break
    fi
    sleep 1
done

AI_HEALTH=$(curl -s "$AI_URL/health" 2>/dev/null || echo '{}')
if echo "$AI_HEALTH" | grep -q '"ready":true'; then
    CORPUS_SIZE=$(echo "$AI_HEALTH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('corpus_size',0))" 2>/dev/null || echo "?")
    log_pass "fos_ai /health ready, corpus_size=$CORPUS_SIZE"
elif echo "$AI_HEALTH" | grep -q '"ready":false'; then
    log_fail "fos_ai /health returned ready=false (DB or corpus issue)"
else
    log_fail "fos_ai did not start within 30s"
    log_info "Continuing with C++ API only..."
fi

# ---- 3. Start fos_api (C++) ----
log_info "=== Starting fos_api on $API_URL ==="

export AI_SERVICE_URL="$AI_URL"
export JWT_SECRET="${JWT_SECRET:-smoke_test_secret_key_for_testing_only}"

"$PROJECT_ROOT/build/fos_api" &
API_PID=$!
sleep 2

if curl -s "$API_URL/health" | grep -q '"success"'; then
    log_pass "fos_api /health responding"
else
    log_fail "fos_api did not start"
    exit 1
fi

# ---- 4. Register + Login ----
log_info "=== Auth setup ==="

REGISTER_RESP=$(curl -s -X POST "$API_URL/api/auth/register" \
    -H "Content-Type: application/json" \
    -d '{"username":"smoke_test_user","password":"Test1234!"}' 2>/dev/null)

LOGIN_RESP=$(curl -s -X POST "$API_URL/api/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"username":"smoke_test_user","password":"Test1234!"}' 2>/dev/null)

JWT=$(echo "$LOGIN_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('data',{}).get('token',''))" 2>/dev/null || echo "")

if [ -n "$JWT" ] && [ "$JWT" != "" ]; then
    log_pass "Auth: registered + logged in, got JWT"
else
    log_fail "Auth: could not get JWT"
    log_info "Login response: $LOGIN_RESP"
    log_info "Skipping authenticated endpoint tests"
    JWT=""
fi

AUTH_HEADER="Authorization: Bearer $JWT"

# ---- 5. Semantic search ----
log_info "=== Semantic search tests ==="

if [ -n "$JWT" ]; then
    # Happy path
    SEARCH_RESP=$(curl -s -w "\n%{http_code}" "$API_URL/api/ai/search?q=spicy+chicken&limit=3" \
        -H "$AUTH_HEADER" 2>/dev/null)
    SEARCH_CODE=$(echo "$SEARCH_RESP" | tail -1)
    SEARCH_BODY=$(echo "$SEARCH_RESP" | sed '$d')

    if [ "$SEARCH_CODE" = "200" ]; then
        COUNT=$(echo "$SEARCH_BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('data',{}).get('count',0))" 2>/dev/null || echo 0)
        log_pass "GET /api/ai/search?q=spicy+chicken -> 200, count=$COUNT"
    else
        log_fail "GET /api/ai/search -> $SEARCH_CODE"
    fi

    # Empty query
    EMPTY_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL/api/ai/search?q=" \
        -H "$AUTH_HEADER" 2>/dev/null)
    if [ "$EMPTY_CODE" = "400" ] || [ "$EMPTY_CODE" = "422" ]; then
        log_pass "GET /api/ai/search?q= -> $EMPTY_CODE (rejected)"
    else
        log_fail "GET /api/ai/search?q= -> $EMPTY_CODE (expected 400/422)"
    fi

    # No JWT
    NO_AUTH_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL/api/ai/search?q=test" 2>/dev/null)
    if [ "$NO_AUTH_CODE" = "401" ]; then
        log_pass "GET /api/ai/search (no JWT) -> 401"
    else
        log_fail "GET /api/ai/search (no JWT) -> $NO_AUTH_CODE (expected 401)"
    fi
else
    log_skip "Search tests (no JWT)"
fi

# ---- 6. Recommendations ----
log_info "=== Recommend tests ==="

if [ -n "$JWT" ]; then
    REC_RESP=$(curl -s -w "\n%{http_code}" "$API_URL/api/ai/recommend?limit=3" \
        -H "$AUTH_HEADER" 2>/dev/null)
    REC_CODE=$(echo "$REC_RESP" | tail -1)
    REC_BODY=$(echo "$REC_RESP" | sed '$d')

    if [ "$REC_CODE" = "200" ]; then
        STRATEGY=$(echo "$REC_BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('data',{}).get('strategy','?'))" 2>/dev/null || echo "?")
        log_pass "GET /api/ai/recommend -> 200, strategy=$STRATEGY"
    else
        log_fail "GET /api/ai/recommend -> $REC_CODE"
    fi
else
    log_skip "Recommend tests (no JWT)"
fi

# ---- 7. Parse-order ----
log_info "=== Parse-order tests ==="

if [ -n "$JWT" ]; then
    PARSE_RESP=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/api/ai/parse-order" \
        -H "$AUTH_HEADER" \
        -H "Content-Type: application/json" \
        -d '{"text":"两份宫保鸡丁加一份麻婆豆腐","restaurant_hint_id":1}' 2>/dev/null)
    PARSE_CODE=$(echo "$PARSE_RESP" | tail -1)

    if [ "$PARSE_CODE" = "200" ]; then
        log_pass "POST /api/ai/parse-order -> 200"
    elif [ "$PARSE_CODE" = "502" ]; then
        log_skip "POST /api/ai/parse-order -> 502 (LLM API key not set)"
    else
        log_fail "POST /api/ai/parse-order -> $PARSE_CODE"
    fi

    # Empty text
    EMPTY_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API_URL/api/ai/parse-order" \
        -H "$AUTH_HEADER" \
        -H "Content-Type: application/json" \
        -d '{"text":""}' 2>/dev/null)
    if [ "$EMPTY_CODE" = "400" ] || [ "$EMPTY_CODE" = "422" ]; then
        log_pass "POST /api/ai/parse-order (empty text) -> $EMPTY_CODE"
    else
        log_fail "POST /api/ai/parse-order (empty text) -> $EMPTY_CODE"
    fi
else
    log_skip "Parse-order tests (no JWT)"
fi

# ---- 8. AI chat stub ----
log_info "=== Chat stub test ==="

CHAT_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API_URL/api/ai/chat" \
    -H "Content-Type: application/json" \
    -d '{}' 2>/dev/null)
if [ "$CHAT_CODE" = "501" ]; then
    log_pass "POST /api/ai/chat -> 501 (still reserved)"
else
    log_fail "POST /api/ai/chat -> $CHAT_CODE (expected 501)"
fi

# ---- 9. fos_ai down scenario ----
log_info "=== AI service down test ==="

if [ -n "$JWT" ]; then
    # Kill fos_ai temporarily
    kill "$AI_PID" 2>/dev/null || true
    wait "$AI_PID" 2>/dev/null || true
    sleep 1

    DOWN_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL/api/ai/search?q=test" \
        -H "$AUTH_HEADER" 2>/dev/null)
    if [ "$DOWN_CODE" = "503" ]; then
        log_pass "GET /api/ai/search (fos_ai down) -> 503 AI_UNAVAILABLE"
    else
        log_fail "GET /api/ai/search (fos_ai down) -> $DOWN_CODE (expected 503)"
    fi
    AI_PID=""  # Prevent double-kill in cleanup
else
    log_skip "AI service down test (no JWT)"
fi

# ---- Summary ----
echo ""
echo "==============================="
echo -e "  PASS: ${GREEN}$PASS${NC}"
echo -e "  FAIL: ${RED}$FAIL${NC}"
echo -e "  SKIP: ${YELLOW}$SKIP${NC}"
echo "==============================="

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
