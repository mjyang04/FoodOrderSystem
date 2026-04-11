# Sprint 2.5 — Hardening Backlog

**Status:** planned
**Created:** 2026-04-11
**Owner:** mj
**Entry gate for:** Sprint 3 (orders)
**Context:** post-Sprint-2 triple review (cpp-reviewer + security-reviewer +
code-reviewer). Commit A `982bf88` landed the Sprint 2 service layer + JWT.
Commit B `a93cbf3` resolved the four "must-fix" findings (S-H1, S-H4, S-M4,
C-H3). This document captures the remaining review output as a separate
hardening sprint that must be completed **before** Sprint 3 order endpoints
start writing data under real concurrency.

---

## Entry criteria for Sprint 3

Two items in this backlog are **hard blockers** for Sprint 3. Everything
else is nice-to-have polish that Sprint 3 can layer in as it goes.

- **H-CONCURRENCY** — `Database` singleton thread safety (see below)
- **H-DI** — service-layer dependency injection seam (see below)

If these are not resolved, Sprint 3 will either (a) crash under the first
multi-threaded load test, or (b) ship with zero service-layer tests and
compound the same architectural debt into the order module.

---

## HIGH — must land before Sprint 3

### H-CONCURRENCY — make `Database` safe under `HTTP_THREADS > 1`
**Source:** cpp-reviewer H2, code-reviewer M7
**Files:** `src/db/Database.cpp`, `src/api/main_api.cpp`

The current `Database` singleton holds a single `MYSQL*` connection. Sprint 1
pinned `HTTP_THREADS=1` as a soft hint in `config.example`, but nothing in
code enforces it — a misconfigured deployment will race on the raw handle.
Sprint 3 adds order writes, which is the point where "soft hint" becomes
"memory corruption".

**Decision required, pick one:**
1. **Mutex wrapper (cheap, 1 day):** wrap every `Database::*` method with
   `std::lock_guard<std::mutex>`. Keeps the repository interface stable,
   serializes all DB access — fine for a course project / resume demo.
2. **Drogon DbClient pool (correct, 3-5 days):** rewrite the repository
   layer against `drogon::orm::DbClient` with a real connection pool.
   Unlocks true concurrency but touches every query.

**Recommendation:** option 1 for Sprint 2.5, option 2 as an explicit Sprint 4
item ("concurrency uplift"). Document the choice in the commit message.

**Exit check:** set `HTTP_THREADS=4`, run `hey -n 500 -c 20
http://localhost:8080/api/restaurants` → zero segfaults, zero torn responses.

---

### H-DI — break the static coupling to `Database::instance()`
**Source:** code-reviewer H1
**Files:** `src/service/AuthService.{h,cpp}`,
`src/service/RestaurantService.{h,cpp}`, plus new interface headers

Every service method currently calls `Database::instance()` directly, so
service unit tests are physically impossible without a live MySQL. Sprint 2
had to skip service tests because of this, and Sprint 3 orders will be much
harder to test than auth was.

**Plan:**
- Introduce `src/db/IUserRepo.h` and `src/db/IRestaurantRepo.h` (pure virtual
  interfaces that mirror the subset of `Database` each service needs).
- Give `AuthService` / `RestaurantService` a constructor that takes
  `IUserRepo&` / `IRestaurantRepo&`. Keep the existing static methods as
  thin wrappers that forward to a default instance wired in `main_api.cpp`
  and `main.cpp`, so the controllers and CLI don't need to change yet.
- Add a tiny `tests/fakes/FakeUserRepo.h` that records calls in memory, and
  write the first three service-layer tests:
  - `AuthService::registerUser` happy path
  - `AuthService::authenticate` wrong password → INVALID_CREDENTIALS
  - `AuthService::registerUser` on disconnected repo → DB_UNAVAILABLE

**Exit check:** `ctest` count rises from 55 → 58+, and the new tests run
without a MySQL server available.

---

## MEDIUM — should land in Sprint 2.5, may slip to Sprint 3 opening PR

### M-GETMENU — replace O(N) full-table scan in `RestaurantService::getMenu`
**Source:** cpp-reviewer (performance half of H1), code-reviewer H2
**Files:** `src/service/RestaurantService.cpp`, `src/db/Database.{h,cpp}`

`getMenu(id)` currently calls `db.getAllRestaurants()` and linearly scans
the vector. Add `Database::findRestaurantById(int)` using a prepared
statement, use it here. Do this before Sprint 3 wires orders to menus or
the N+1 problem compounds.

---

### M-STATUS-MAP — move `statusForError()` into `api/JsonEnvelope.h`
**Source:** code-reviewer M2
**Files:** `src/api/JsonEnvelope.h`, `src/api/controllers/*.cc`

`AuthController` has a full mapping; `RestaurantController` has a partial
inlined one. Sprint 3's `OrderController` will be a third drift site. Hoist
a single `statusForError(const std::string&)` into `JsonEnvelope.h` and
have every controller call it. Keyed off the `err::k*` constants from
`service/ErrorCodes.h`.

---

### M-LISTALL-PROTOCOL — return `Result<vector<Restaurant>>` from `listAll`
**Source:** code-reviewer M3
**Files:** `src/service/RestaurantService.{h,cpp}`,
`src/api/controllers/RestaurantController.cc`

`listAll()` currently swallows "DB unreachable" into an empty vector. The
HTTP client cannot distinguish "no restaurants" from "503". Align with the
`getMenu` protocol: return `Result<vector<Restaurant>>` and let the
controller emit 503 on `DB_UNAVAILABLE`.

---

### M-BODY-CAP — add Content-Length guard before JSON parse
**Source:** security-reviewer M3
**Files:** `src/api/controllers/AuthController.cc` (and future controllers)

`req->getJsonObject()` runs without a per-endpoint size check. Add an
explicit `if (req->getBody().size() > 4096) return 400;` on both auth
endpoints before calling `getJsonObject()`. Consider lifting into
`api/JsonEnvelope.h` as `requireJsonBody(req, maxBytes)` helper so Sprint 3
orders can reuse it.

---

### M-BEARER-CASE — accept case-insensitive `Bearer` scheme
**Source:** security-reviewer M2
**Files:** `src/api/filters/JwtAuthFilter.cc`

RFC 7235 §2.1 says the auth-scheme token is case-insensitive. The current
filter rejects `bearer <token>` with 401. Case-fold the first 7 characters
before comparing.

---

### M-FILTER-SMOKE — exercise `JwtAuthFilter` before Sprint 3 relies on it
**Source:** code-reviewer M5
**Files:** new `src/api/controllers/AuthController` endpoint `/api/auth/me`,
or new unit test

`JwtAuthFilter` is compiled but unreachable — we will only discover
Drogon's attribute-storage edge cases the moment Sprint 3 tries to read
claims from a protected handler. Either:
- Add a trivial `/api/auth/me` endpoint that echoes the decoded claims
  and gate it on `JwtAuthFilter`, or
- Write a unit test that constructs a `HttpRequest` with a Bearer header
  and runs `doFilter` against a configured `JwtService`.

Recommendation: the endpoint. It also validates the `ADD_METHOD_TO` filter
registration syntax end to end, which is the part most likely to surprise
us.

---

### M-JSONBODY-HELPER — promote `extractCredentials` into `api/JsonBody.h`
**Source:** code-reviewer M6
**Files:** new `src/api/JsonBody.h`, `src/api/controllers/AuthController.cc`

The "validate JSON body and pull required string fields" helper is
currently in an anonymous namespace in `AuthController.cc`. Sprint 3
orders will need the same pattern plus numeric fields. Promote it to a
shared header before copy-paste begins.

---

## LOW — Sprint 3 polish, no blocker

### L-PASSWORD-STRENGTH — raise password minimum to 8 characters
**Source:** security-reviewer M1
**Files:** `src/service/AuthService.cpp`

NIST SP 800-63B recommends 8 chars minimum. Bump `kMinPasswordLen` from
6 to 8 and update the error message. Course project, but costs nothing.

### L-RESULT-ERGONOMICS — `Result<T>::from_error(const ErrorInfo&)`
**Source:** code-reviewer L3
**Files:** `src/service/Result.h`

Propagating errors between different `Result<T>` instances currently
re-copies `code` and `message` through `failure(v.error().code, ...)`.
Add a single-argument `from_error(const ErrorInfo&)` factory.

### L-RESULT-ASSERT — assert on `Result::error()` when successful
**Source:** code-reviewer L5, cpp-reviewer M2
**Files:** `src/service/Result.h`

Calling `error()` on a successful `Result` silently returns an empty
`ErrorInfo`. Add `assert(!ok_)` in debug builds and a `[[nodiscard]]`
on `ok()` / `operator bool()` to catch misuse.

### L-CONFIG-WILDCARD — widen `.gitignore` to catch `config.*` variants
**Source:** security-reviewer L1
**Files:** `.gitignore`

Add `config.*` with an exception for `config.example`, so
`config.local` / `config.prod` / `config.staging` can never leak.

### L-TTL-WARN — warn on `JWT_TTL_HOURS > 168`
**Source:** security-reviewer L2
**Files:** `src/api/main_api.cpp`

A one-week cap is a reasonable operational default; anything longer
should at least trip a startup warning.

### L-PAGINATION — add server-side cap on `RestaurantService::listAll`
**Source:** security-reviewer L3
**Files:** `src/service/RestaurantService.cpp`

With 14 seed restaurants this is harmless, but adding
`SELECT ... LIMIT 200` now prevents accidentally shipping an
enumeration vector later.

### L-CONTROLLER-NS — drop `using namespace drogon;` in `.cc` files
**Source:** cpp-reviewer M5
**Files:** three controllers + `JwtAuthFilter.cc`

Replace with targeted `using drogon::HttpStatusCode;` etc. Consistency
with "no `using namespace std` in headers" spirit.

### L-AUTH-CONTEXT — type-safe getter for JWT claims on request attrs
**Source:** code-reviewer L2
**Files:** new `src/api/AuthContext.h`, `src/api/filters/JwtAuthFilter.cc`

Claims are currently stored as `int`/`string` in request attributes and
Sprint 3 handlers will compare against magic `1` for the ADMIN role.
Introduce a `struct AuthContext { int userId; string username; UserRole
role; };` and a `readAuthContext(const HttpRequestPtr&)` helper.

### L-FETCHCONTENT-HOIST — `include(FetchContent)` is called twice
**Source:** code-reviewer L4
**Files:** `CMakeLists.txt`

Harmless; hoist to the top.

---

## Deferred to Sprint 3 proper (NOT in this sprint)

Rate limiting, CORS policy, password-hash upgrade from SHA-256 to
bcrypt/Argon2, and global request logging middleware — all of these are
Sprint 3 design decisions, not Sprint 2.5 cleanups.

- **I1 rate limiting** — needs a design call (token bucket vs fixed
  window, per-IP vs per-user). Belongs in the Sprint 3 planning doc.
- **I2 CORS** — depends on whether we ship a browser SPA. Belongs with
  the frontend scope decision.
- **I3 password hash upgrade** — pre-existing Sprint 0 design; a real
  security uplift, not a review fix. Open a separate ticket.

---

## Review provenance

The review that produced this backlog ran on 2026-04-11 across three
agents in parallel immediately after the Sprint 2 green build:

- `cpp-reviewer` — C++17 / RAII / template correctness
- `security-reviewer` — OWASP / JWT / credential handling
- `code-reviewer` — architecture / layering / error-code taxonomy

One of cpp-reviewer's HIGH findings (claimed use-after-free in
`RestaurantService::getMenu`) was **verified false** after re-reading the
code — the vector is a function-local `const auto`, alive through the
`return` statement. The performance concern it surfaced (O(N) scan)
remains valid and is tracked as M-GETMENU above.
