# FoodOrderSystem - Project Instructions

## Project Overview

A C++ food ordering system with MySQL database backend. This is a course project demonstrating OOP, design patterns, and database integration.

**Language:** C++17
**Build System:** CMake 3.16+
**Database:** MySQL (libmysqlclient)
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

# Run (set DB credentials via environment)
DB_PASS=yourpassword ./FoodOrderSystem
```

## Project Structure

```
src/
  main.cpp              # Entry point, DB connection setup
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
    Database.h/cpp      # MySQL singleton
    schema.sql          # DDL + seed data
  util/                 # Utilities
    InputHelper.h/cpp   # Safe input, cross-platform clear
```

## Architecture Conventions

- **No `using namespace std` in headers** - always use `std::` prefix
- **Smart pointers only** - `unique_ptr` for ownership, `shared_ptr` for menu items
- **Factory + Registry pattern** for Food creation (see `FoodFactory`)
- **Singleton** for database connection (see `Database`)
- **Member variables** use trailing underscore: `name_`, `price_`
- **File limit**: keep each file under 400 lines

## Key Design Patterns

| Pattern | Location | Purpose |
|---------|----------|---------|
| Factory + Registry | `FoodFactory` | Create Food by cuisine type string |
| Singleton | `Database` | Single MySQL connection |
| Strategy | `Delivery` hierarchy | Interchangeable delivery options |
| Polymorphism | `Food` hierarchy | 5 cuisine families, 10 concrete types |

## Database

- Schema auto-initializes via `Database::initializeSchema()`
- Connection configured via environment variables: `DB_HOST`, `DB_USER`, `DB_PASS`, `DB_NAME`, `DB_PORT`
- All SQL uses `mysql_real_escape_string()` to prevent injection
- Seed data in `schema.sql` includes 14 restaurants, 70 food items, 10 riders

## Code Style

- C++17 standard
- `PascalCase` for classes, `camelCase` for methods, `snake_case_` for members
- Comments in English
- Error handling via exceptions (`std::runtime_error`, `std::invalid_argument`)
- Input validation in `InputHelper` namespace (never trust raw `cin`)
