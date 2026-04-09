# Food Order System

A full-featured food ordering console application built with modern C++17, featuring MySQL database integration, user authentication with password hashing, role-based access control, and an admin management panel.

## Features

### Customer Features
- **Browse Restaurants** - View 14 restaurants across 10 cuisine types
- **Place Orders** - Select food items with preferences, special instructions, and delivery options
- **Order Management** - View, reorder, modify, and delete past orders
- **Order Status Tracking** - Track orders through 6 stages: Pending -> Confirmed -> Preparing -> Delivering -> Delivered / Cancelled
- **Rating System** - Rate completed orders (1.0 - 5.0)
- **Search & Filter** - Search restaurants by keyword, filter food by price range
- **Personal Analytics** - View total orders, total spent, and favorite restaurant

### Admin Features
- **Manage Restaurants** - Add / delete restaurants
- **Manage Menu** - Add / delete food items, update prices
- **Manage Riders** - Add / delete delivery riders
- **Manage Users** - View all users, create admin accounts
- **View All Orders** - Monitor all system orders

### Technical Highlights
- **MySQL Database** - Relational data storage with foreign keys and cascading deletes
- **Prepared Statements** - `mysql_stmt_*` API for SQL injection prevention
- **Password Hashing** - SHA-256 with random salt (no plaintext passwords)
- **Factory + Registry Pattern** - Extensible food type creation without if-else chains
- **Smart Pointers** - `unique_ptr` / `shared_ptr` for automatic memory management (zero leaks)
- **Custom Exceptions** - Typed exception hierarchy (`DatabaseException`, `AuthException`, `OrderException`)
- **Logging System** - 4-level logger (DEBUG/INFO/WARN/ERROR) with file output support
- **Config System** - File-based config with environment variable override
- **Unit Tests** - 55 GoogleTest cases covering core logic (HashUtil, Food, Delivery, Order, Config)
- **Input Validation** - Robust input handling, no crashes on invalid input
- **Cross-platform** - Works on macOS, Linux, and Windows

## OOP Design

### Class Hierarchy

```
Food (abstract)
  |-- ChineseFood
  |     |-- SichuanCuisine
  |     |-- CantoneseCuisine
  |-- WesternFood
  |     |-- ItalianCuisine
  |     |-- FrenchCuisine
  |-- ArabicFood
  |     |-- LebaneseCuisine
  |     |-- MoroccanCuisine
  |-- MexicanFood
  |     |-- TexMexCuisine
  |     |-- TraditionalMexicanCuisine
  |-- JapaneseFood
        |-- SushiCuisine
        |-- RamenCuisine

Delivery (abstract)
  |-- DirectDelivery
  |-- StandardDelivery
  |-- SaverDelivery
```

### Design Patterns

| Pattern | Class | Purpose |
|---------|-------|---------|
| **Factory + Registry** | `FoodFactory` | Creates Food objects by cuisine type string, avoids large if-else |
| **Singleton** | `Database`, `Logger`, `Config` | Single MySQL connection, centralized logging and config |
| **Strategy** | `Delivery` | Interchangeable delivery options with different fees and times |
| **Polymorphism** | `Food`, `Delivery` | Virtual `display()`, `clone()`, `getTypeName()` across all types |
| **RAII** | Smart pointers | `unique_ptr<Delivery>` in Order, `shared_ptr<Food>` in Restaurant |
| **Exception Hierarchy** | `Exceptions.h` | Typed exceptions for DB, Auth, Order, Validation errors |

### Database Schema (ER Diagram)

```
users ----< orders ----< order_items
              |
restaurants --+
              |
riders -------+
```

- `users` - Authentication with hashed passwords and roles (customer/admin)
- `restaurants` - Name and cuisine type
- `foods` - Menu items linked to restaurants (with preferences)
- `orders` - Order metadata, status, delivery, payment, rating
- `order_items` - Individual food items within an order
- `riders` - Delivery rider contact information

## Prerequisites

- **C++ Compiler** with C++17 support (GCC 7+, Clang 5+, MSVC 2017+)
- **CMake** 3.16 or later
- **MySQL Server** 5.7+ or 8.0+
- **MySQL Client Library** (`libmysqlclient-dev`)

### Install Dependencies

```bash
# macOS
brew install cmake mysql-client

# Ubuntu / Debian
sudo apt install cmake libmysqlclient-dev mysql-server

# CentOS / RHEL
sudo yum install cmake mysql-devel mysql-server
```

## Quick Start

### 1. Setup Database

```bash
# Start MySQL server (if not running)
# macOS: brew services start mysql
# Linux: sudo systemctl start mysql

# Create database and load schema + seed data
mysql -u root -p -e "CREATE DATABASE food_order_system;"
mysql -u root -p food_order_system < src/db/schema.sql
```

### 2. Build

```bash
mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
cmake --build .
```

### 3. Run Tests

```bash
cd build
ctest --output-on-failure
```

55 unit tests cover: SHA-256 hashing, Food/FoodFactory, Delivery, Order logic, Config parser.

### 4. Run

```bash
# Set database credentials
export DB_HOST=127.0.0.1
export DB_USER=root
export DB_PASS=yourpassword
export DB_NAME=food_order_system

# Run the application
./FoodOrderSystem
```

Or use the setup script:

```bash
chmod +x setup.sh
./setup.sh
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | `127.0.0.1` | MySQL server host |
| `DB_USER` | `root` | MySQL username |
| `DB_PASS` | *(empty)* | MySQL password |
| `DB_NAME` | `food_order_system` | Database name |
| `DB_PORT` | `3306` | MySQL server port |

## Project Structure

```
FoodOrderSystem/
  CMakeLists.txt              # Build configuration
  setup.sh                    # One-click setup script
  config.example              # Example config file
  README.md                   # This file
  CLAUDE.md                   # Development conventions
  src/
    main.cpp                  # Entry point (Config + Logger init)
    ui/
      Color.h                 # ANSI terminal colors
    model/
      Food.h/cpp              # Food base + 10 subclasses
      FoodFactory.h/cpp       # Factory + Registry
      Delivery.h/cpp          # 3 delivery strategies
    core/
      FoodOrderSystem.h/cpp   # Main business logic
      Order.h/cpp             # Order with 6-state tracking
      Restaurant.h/cpp        # Restaurant with menu
    auth/
      User.h/cpp              # User model with roles
      LoginSystem.h/cpp       # Login + Registration flow
      HashUtil.h/cpp          # SHA-256 hashing
    db/
      Database.h/cpp          # MySQL singleton (prepared statements)
      schema.sql              # DDL + seed data
    util/
      InputHelper.h/cpp       # Input validation utilities
      Exceptions.h            # Custom exception hierarchy
      Logger.h                # Logging (DEBUG/INFO/WARN/ERROR)
      Config.h                # Config file + env var reader
  tests/
    test_hashutil.cpp         # SHA-256 + salt tests
    test_food.cpp             # Food classes + FoodFactory
    test_delivery.cpp         # Delivery types + factory
    test_order.cpp            # Order logic + pricing
    test_config.cpp           # Config parser tests
```

## Seed Data

The schema includes seed data for immediate use:

- **14 Restaurants** across 10 cuisine types (Sichuan, Cantonese, Italian, French, Lebanese, Moroccan, TexMex, Traditional Mexican, Sushi, Ramen)
- **70 Food Items** with prices, descriptions, and preferences
- **10 Delivery Riders** with contact information

Register a new account through the application to get started. The first user can be promoted to admin via:

```sql
UPDATE users SET role='admin' WHERE username='your_username';
```

## License

This project is developed as a course assignment.
