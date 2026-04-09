# Task Plan: FoodOrderSystem Advanced Upgrade

## Goal
Upgrade the C++ course project from CSV-based console app to a MySQL-backed, modern C++ system with proper design patterns, memory safety, and advanced features.

## Phases
- [x] Phase 1: Modern C++ & Memory Safety
  - [x] 1.1 Replace raw pointers with smart pointers (unique_ptr/shared_ptr)
  - [x] 1.2 Remove `using namespace std` from all headers
  - [x] 1.3 Replace `srand/rand` with `<random>` (mt19937)
  - [x] 1.4 Add cin input validation (InputHelper with retry)
  - [x] 1.5 Replace `system("cls")` with cross-platform utility
  - [x] 1.6 Add CMakeLists.txt build system
- [x] Phase 2: Design Pattern Refactor
  - [x] 2.1 FoodFactory with registry pattern (eliminated if-else chain)
  - [x] 2.2 Separate UI layer from business logic (src/ui/, src/core/, src/model/)
  - [x] 2.3 Add password hashing (SHA-256 with salt)
  - [x] 2.4 Add user registration
- [x] Phase 3: MySQL Database Integration
  - [x] 3.1 Add Database singleton class (libmysqlclient)
  - [x] 3.2 Create SQL schema with seed data
  - [x] 3.3 Replace all CSV operations with SQL queries
  - [x] 3.4 Add setup.sh script
- [x] Phase 4: Advanced Features
  - [x] 4.1 Order status tracking (6 states)
  - [x] 4.2 Admin panel (manage restaurants/menus/riders/users)
  - [x] 4.3 Rating system for orders
  - [x] 4.4 Search & filter (by keyword, price range)
  - [x] 4.5 Order history analytics (total spent, favorite restaurant, order count)
- [x] Phase 5: Build & Verify - Clean build, 0 warnings

## Architecture (Final)
```
src/
  main.cpp                    # Entry point, DB connection
  ui/
    Color.h                   # ANSI color constants (namespace)
  core/
    FoodOrderSystem.h/cpp     # Business logic + menus
    Order.h/cpp               # Order with status tracking
    Restaurant.h/cpp          # Restaurant with shared_ptr menu
  model/
    Food.h/cpp                # Food hierarchy with clone()
    FoodFactory.h/cpp         # Factory + Registry pattern
    Delivery.h/cpp            # Delivery with factory function
  auth/
    User.h/cpp                # User with role & password verify
    LoginSystem.h/cpp         # Login + Registration
    HashUtil.h/cpp            # SHA-256 + salt
  db/
    Database.h/cpp            # MySQL singleton
    schema.sql                # DDL + seed data
  util/
    InputHelper.h/cpp         # Safe input + cross-platform clear
CMakeLists.txt
setup.sh
```

## Key Improvements Over Original
1. **MySQL database** instead of CSV files
2. **Factory + Registry pattern** eliminates 10-way if-else chain
3. **Smart pointers** (unique_ptr/shared_ptr) - zero memory leaks
4. **Password hashing** (SHA-256 with random salt)
5. **User registration** (not hardcoded)
6. **Order status tracking** (6 states)
7. **Admin panel** (full CRUD for restaurants, menu, riders, users)
8. **Rating system** for orders
9. **Search & filter** (keyword, price range)
10. **Analytics** (total spent, favorite restaurant)
11. **Input validation** (no crashes on bad input)
12. **Cross-platform** (clear screen, CMake build)
13. **Proper project structure** (src/ with subdirectories)
14. **No `using namespace std` in headers**
15. **Modern C++17** (structured bindings, constexpr, auto)

## Status
**COMPLETE** - All phases implemented. Build clean with 0 warnings.
