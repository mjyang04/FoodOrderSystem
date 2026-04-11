# Sprint 3 — Order Endpoints

**Branch:** `feature/rest-api`
**Entry gate:** Sprint 2.5 closed on 2026-04-12 (2 HIGH + 7 MEDIUM + 9 LOW, ctest 58/58).
**Goal:** Ship the HTTP surface for orders, built on top of the Sprint 2.5 hardened service/repo layer.

---

## 1. Scope

### In scope (Sprint 3 MVP)
- `POST /api/orders` — authenticated customer creates an order. Body:
  ```json
  {
    "restaurant_id": 1,
    "items": [{"food_id": 10, "quantity": 2}],
    "delivery_option": "Standard"
  }
  ```
  Validates restaurant exists, every `food_id` belongs to that restaurant, computes total, persists atomically, returns the new order id + summary.
- `GET /api/orders/:id` — authenticated user reads one order. A customer may only read their own orders; an admin may read any order.
- `GET /api/orders` — authenticated user lists their own orders. Capped at 200 rows (L-PAGINATION pattern). Admin gets every order.
- `OrderService` unit tests against a `FakeOrderRepo` + `FakeRestaurantRepo`, covering success paths and every error branch.

### Out of scope (defer to Sprint 3.5+)
- `PATCH /api/orders/:id/status` — admin state transitions. Nice to have, but not required for the MVP demo.
- Real pagination (`?page=`, `?limit=`) — the 200-row cap is a hard ceiling for now.
- Rate limiting, CORS, bcrypt/Argon2 hash upgrade, global request logging (Sprint 2.5 deferred items).
- Rider auto-assignment, payment integration, discount promo codes.
- Refactoring the legacy CLI `core/Order` — it stays untouched; Sprint 3 adds a parallel DTO path.

---

## 2. Design decisions (answered before coding)

### D1. Domain model — OrderDto, not core/Order
**Decision:** Introduce `fos::service::OrderDto` + `NewOrderDto` + `OrderItemDto` as plain C++17 structs under `src/service/OrderDto.h`. `OrderService` speaks DTOs exclusively. The legacy `core/Order` class stays exactly as it is and continues to serve the CLI.

**Rationale:**
- `core/Order` holds `unique_ptr<Delivery>`, `shared_ptr<Food>` menu references, and CLI-oriented display methods (`displaySummary`, `displayConfirmation`). Threading that through a Drogon worker pool means either duplicating the model into a second parallel shape at the controller boundary anyway, or pulling CLI logic into the HTTP path. Cleaner to commit to a DTO now.
- DTOs are trivially copyable, easy to serialize to JSON, and free of the CLI `Delivery` hierarchy — which Sprint 3 does not need (delivery option is a string).
- Keeps the "no CLI in the HTTP path" line that H-DI drew in Sprint 2.5.

### D2. Transaction boundary — inside the Repo
**Decision:** `IOrderRepo::createOrder(NewOrderDto)` is a single atomic operation. The concrete `Database` implementation wraps the `orders` + `order_items` inserts in a MySQL transaction (`START TRANSACTION` / `COMMIT` / `ROLLBACK`). `OrderService` knows nothing about transactions.

**Rationale:**
- Matches the H-DI abstraction level: Service owns policy (validation, pricing, authorization), Repo owns persistence (atomicity, connection management).
- Makes `FakeOrderRepo` trivial to implement — it just stores the DTO in a vector with no transaction machinery.
- Sprint 2.5 already has `std::recursive_mutex` guarding `Database`, so nested mutex acquisition in a helper is safe.

### D3. Food membership validation — reuse `IRestaurantRepo::getFoodsByRestaurant`
**Decision:** `OrderService::createOrder` calls `IRestaurantRepo::findRestaurantById` + `getFoodsByRestaurant` to build a `food_id → Food*` lookup, then walks the request items and fails with `MENU_ITEM_MISMATCH` on the first id that is not in the set. No new Repo interface methods for Sprint 3.

**Rationale:**
- Menu sizes are small (5–10 items per restaurant in seed data), so loading once per create is trivially fast.
- Avoids adding an `IFoodRepo` or a `findFoodById(int)` call that would need a second index. If Sprint 4 introduces a food-search endpoint, we revisit.
- Uses the indexed lookup path added in M-GETMENU — no O(N) scan regression.

### D4. Authorization — owner-or-admin, checked in the Service
**Decision:** `OrderService::getOrder(orderId, requestingUserId, isAdmin)` and `listOrders(requestingUserId, isAdmin)` take the caller identity as arguments. On a mismatch, return `err::kForbidden`. The HTTP controller builds these arguments from `AuthContext`.

**Rationale:**
- Keeps authorization decisions out of the Repo (persistence has no business knowing about user roles).
- Makes the policy unit-testable with a FakeOrderRepo: a test can seed an order owned by user 1 and assert that requesting it as user 2 returns `FORBIDDEN` without needing an HTTP layer.

---

## 3. Module layout

```
src/
├── db/
│   ├── IOrderRepo.h          # NEW — pure virtual interface (DTO-based)
│   ├── Database.h            # MODIFIED — inherit IOrderRepo, new methods
│   └── Database.cpp          # MODIFIED — IOrderRepo impl (new methods, legacy ones untouched)
├── service/
│   ├── OrderDto.h            # NEW — OrderDto, NewOrderDto, OrderItemDto structs
│   ├── OrderService.h        # NEW — createOrder / getOrder / listOrders
│   ├── OrderService.cpp      # NEW
│   ├── ErrorCodes.h          # MODIFIED — kOrderNotFound, kMenuItemMismatch, kForbidden, kEmptyOrder, kInvalidQuantity
│   ├── DefaultServices.h     # MODIFIED — defaultOrderService()
│   └── DefaultServices.cpp   # MODIFIED
├── api/
│   ├── JsonEnvelope.h        # MODIFIED — statusForError entries for new codes
│   ├── JsonBody.h            # reuse as-is
│   └── controllers/
│       ├── OrderController.h # NEW
│       └── OrderController.cc# NEW — all protected, uses readAuthContext(req)
└── ...

tests/
├── fakes/
│   ├── FakeOrderRepo.h       # NEW — mirrors FakeUserRepo pattern
│   └── FakeRestaurantRepo.h  # NEW — for OrderService's restaurant dependency
└── test_order_service.cpp    # NEW — service-layer unit tests
```

---

## 4. Error codes (new additions to `service::err`)

| Code                | HTTP | Meaning |
|---------------------|------|---------|
| `ORDER_NOT_FOUND`   | 404  | No order row with that id, OR caller is not the owner (hide existence from non-owners per security best practice — **open question, see Q1 below**) |
| `EMPTY_ORDER`       | 400  | Request had zero items |
| `INVALID_QUANTITY`  | 400  | Some item had quantity ≤ 0 |
| `MENU_ITEM_MISMATCH`| 400  | A `food_id` does not belong to the requested `restaurant_id` |
| `FORBIDDEN`         | 403  | Caller is authenticated but not authorized for this specific resource (e.g. non-admin trying to read a foreign user's order — if we choose the explicit 403 option) |

**Q1 (to decide during implementation):** 403 or 404 for cross-user reads? OWASP generally favors "act as if the resource does not exist" (→ 404) to avoid leaking existence, but that makes debugging harder and blurs the policy line. **Default: return 404 `ORDER_NOT_FOUND` on both missing-row and wrong-owner, and reserve 403 `FORBIDDEN` for future admin-only endpoints.** Revisit if the grader specifically wants 403.

---

## 5. TDD execution order

Each step MUST leave ctest green before moving to the next one.

**Step 1 — RED: write failing service tests**
- Create `src/service/OrderDto.h` with empty-but-declared structs
- Create `src/db/IOrderRepo.h` with pure virtual interface
- Create `tests/fakes/FakeOrderRepo.h` + `tests/fakes/FakeRestaurantRepo.h`
- Create `tests/test_order_service.cpp` — covers:
  - `createOrder` happy path (one restaurant, two items, correct total)
  - `createOrder` empty-items → `EMPTY_ORDER`
  - `createOrder` quantity ≤ 0 → `INVALID_QUANTITY`
  - `createOrder` unknown restaurant → `RESTAURANT_NOT_FOUND`
  - `createOrder` food_id not in restaurant → `MENU_ITEM_MISMATCH`
  - `createOrder` repo disconnected → `DB_UNAVAILABLE`
  - `getOrder` happy path (owner reads own order)
  - `getOrder` non-owner → `ORDER_NOT_FOUND`
  - `getOrder` admin reads any order → success
  - `getOrder` missing id → `ORDER_NOT_FOUND`
  - `listOrders` customer sees only own orders
  - `listOrders` admin sees all orders
- Add test file to `TEST_SOURCES` in `CMakeLists.txt`
- Build should compile (empty OrderService placeholder) but tests fail.

**Step 2 — GREEN: implement OrderService**
- Create `OrderService.h/.cpp` — make every test in step 1 pass
- ctest: all 58 existing + ~12 new = 70/70 green

**Step 3 — Wire Database**
- Add IOrderRepo inheritance to `Database`
- Implement `createOrder(NewOrderDto)` with a real MySQL transaction
- Implement `findOrderById(int)` and `listOrdersByUser(int, limit)` using prepared statements
- Legacy `Database::createOrder(const Order&)` stays untouched
- Register `defaultOrderService()` in DefaultServices
- Build only (no new unit tests — repo is the integration seam, covered by manual smoke)

**Step 4 — HTTP controller**
- Create `OrderController.h/.cc` with `createOrder` / `getOrder` / `listOrders`
- Register routes in `main_api.cpp` with `JwtAuthFilter`
- Extend `JsonEnvelope::statusForError` with the new codes

**Step 5 — Smoke test + commit**
- Run a manual `curl` against a local `fos_api` to verify the happy path end-to-end
- ctest: still 70/70
- Commit each step as its own conventional commit

---

## 6. Commit plan

| # | Commit | Scope |
|---|--------|-------|
| 1 | `test(service): add failing OrderService tests (RED)` | Step 1 |
| 2 | `feat(service): implement OrderService to pass order tests` | Step 2 |
| 3 | `feat(db): implement IOrderRepo on Database with transaction` | Step 3 |
| 4 | `feat(api): add /api/orders endpoints gated on JwtAuthFilter` | Step 4 |
| 5 | (optional) any follow-up fix from smoke test | Step 5 |

No Co-Authored-By lines (per global rule).

---

## 7. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Menu validation pulls the full food list per create | Acceptable at current scale (seed data: ~5 foods/restaurant). Measure if it becomes a hotspot. |
| MySQL transaction error handling is ugly in C API | Follow the existing `createOrder` pattern in `Database.cpp:515` — it already uses `mysql_stmt_*` with explicit cleanup. |
| Delivery option is a free-form string | Whitelist in OrderService: `{"Standard", "Express", "Scheduled"}` matches the existing `Delivery` hierarchy. Unknown → `VALIDATION_ERROR`. |
| `OrderDto` diverging from `core/Order` forever | Accept the duplication. Sprint 4/5 can unify if it becomes painful. |
| Food price changes between menu load and order commit | Out of scope — price is captured at order creation time from whatever `getFoodsByRestaurant` returned. Real systems would snapshot the price row inside the transaction. |
