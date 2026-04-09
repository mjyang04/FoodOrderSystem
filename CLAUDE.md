# FoodOrderSystem - Project Instructions

## Project Overview

A C++ food ordering system with MySQL database backend. This is a course project demonstrating OOP, design patterns, database integration, and software engineering practices.

**Language:** C++17
**Build System:** CMake 3.16+
**Database:** MySQL (libmysqlclient, prepared statements)
**Testing:** GoogleTest (via FetchContent)
**Platform:** Cross-platform (macOS, Linux, Windows)

## Build & Run

```bash
# Configure and build
mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
cmake --build .

# Setup database
mysql -u root -p -e "CREATE DATABASE food_order_system;"
mysql -u root -p food_order_system < src/db/schema.sql

# Run (set DB credentials via environment or config file)
DB_PASS=yourpassword ./FoodOrderSystem

# Run unit tests
ctest --output-on-failure
```

## Project Structure

```
src/
  main.cpp              # Entry point, Config + Logger init
  ui/Color.h            # ANSI color constants
  model/                # Data models
    Food.h/cpp          # Food base class + 10 cuisine subclasses
    FoodFactory.h/cpp   # Factory + Registry pattern
    Delivery.h/cpp      # Delivery options (3 types)
  core/                 # Business logic
    FoodOrderSystem.h/cpp  # Main system coordinator
    Order.h/cpp         # Order with status tracking
    Restaurant.h/cpp    # Restaurant with menu
  auth/                 # Authentication
    User.h/cpp          # User model with roles
    LoginSystem.h/cpp   # Login + Registration
    HashUtil.h/cpp      # SHA-256 password hashing
  db/                   # Database layer
    Database.h/cpp      # MySQL singleton (prepared statements)
    schema.sql          # DDL + seed data
  util/                 # Utilities
    InputHelper.h/cpp   # Safe input, cross-platform clear
    Exceptions.h        # Custom exception hierarchy
    Logger.h            # Logging system (DEBUG/INFO/WARN/ERROR)
    Config.h            # Config file + env var reader
tests/                  # Unit tests (GoogleTest)
  test_hashutil.cpp     # SHA-256, salt, password hashing
  test_food.cpp         # Food classes + FoodFactory
  test_delivery.cpp     # Delivery types + factory
  test_order.cpp        # Order logic, status, pricing
  test_config.cpp       # Config parser
config.example          # Example config file
```

## Architecture Conventions

- **No `using namespace std` in headers** - always use `std::` prefix
- **Smart pointers only** - `unique_ptr` for ownership, `shared_ptr` for menu items
- **Factory + Registry pattern** for Food creation (see `FoodFactory`)
- **Singleton** for database connection (see `Database`), logger, config
- **Custom exceptions** - `DatabaseException`, `AuthException`, `OrderException`, etc.
- **Prepared statements** - `createUser()`, `createOrder()`, `findUserByUsername()` use `mysql_stmt_*`
- **Member variables** use trailing underscore: `name_`, `price_`
- **File limit**: keep each file under 400 lines

## Key Design Patterns

| Pattern | Location | Purpose |
|---------|----------|---------|
| Factory + Registry | `FoodFactory` | Create Food by cuisine type string |
| Singleton | `Database`, `Logger`, `Config` | Single instances |
| Strategy | `Delivery` hierarchy | Interchangeable delivery options |
| Polymorphism | `Food` hierarchy | 5 cuisine families, 10 concrete types |

## Database

- Schema auto-initializes via `Database::initializeSchema()`
- Connection configured via config file or env vars: `DB_HOST`, `DB_USER`, `DB_PASS`, `DB_NAME`, `DB_PORT`
- Critical queries use prepared statements (`mysql_stmt_*`) to prevent SQL injection
- Seed data in `schema.sql` includes 14 restaurants, 70 food items, 10 riders

## Testing

- 55 unit tests across 5 test files
- Run: `cd build && ctest --output-on-failure`
- Covers: HashUtil, Food/FoodFactory, Delivery, Order, Config
- GoogleTest fetched automatically via CMake FetchContent

## Error Handling

- Custom exception hierarchy in `util/Exceptions.h`
- Base: `AppException` -> `DatabaseException`, `AuthException`, `OrderException`, `ValidationException`
- Specific: `ConnectionException`, `QueryException`, `UserExistsException`, `InvalidCredentialsException`, etc.

## Logging

- `Logger` singleton with 4 levels: DEBUG, INFO, WARNING, ERROR
- Macros: `LOG_DEBUG()`, `LOG_INFO()`, `LOG_WARN()`, `LOG_ERROR()`
- Outputs to stderr + optional log file
- Level and file configurable via `LOG_LEVEL` and `LOG_FILE`

## Code Style

- C++17 standard
- `PascalCase` for classes, `camelCase` for methods, `snake_case_` for members
- Comments in English
- Error handling via custom exceptions (see `util/Exceptions.h`)
- Input validation in `InputHelper` namespace (never trust raw `cin`)
