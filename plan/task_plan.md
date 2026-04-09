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
- [x] Phase 6: Engineering Improvements
  - [x] 6.1 Unit tests (GoogleTest) - 55 tests across 5 files
  - [x] 6.2 Prepared statements (mysql_stmt_*) for createUser, createOrder, findUser
  - [x] 6.3 Custom exception hierarchy (Exceptions.h)
  - [x] 6.4 Logging system (Logger.h) - 4 levels, file output
  - [x] 6.5 Config system (Config.h) - file + env var reader
  - [x] 6.6 Updated CLAUDE.md, README.md

## Status
**COMPLETE** - All phases implemented. 55/55 tests passing.
