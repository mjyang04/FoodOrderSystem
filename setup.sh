#!/bin/bash
# Food Order System - Setup Script
# This script sets up MySQL database and builds the project

set -e

echo "=== Food Order System Setup ==="
echo ""

# Check dependencies
command -v mysql >/dev/null 2>&1 || { echo "MySQL client not found. Install: brew install mysql"; exit 1; }
command -v cmake >/dev/null 2>&1 || { echo "CMake not found. Install: brew install cmake"; exit 1; }

# MySQL configuration
read -p "MySQL Host [127.0.0.1]: " DB_HOST
DB_HOST=${DB_HOST:-127.0.0.1}

read -p "MySQL User [root]: " DB_USER
DB_USER=${DB_USER:-root}

read -sp "MySQL Password: " DB_PASS
echo ""

read -p "Database Name [food_order_system]: " DB_NAME
DB_NAME=${DB_NAME:-food_order_system}

# Create database and load schema
echo ""
echo "Creating database and loading schema..."
mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" -e "CREATE DATABASE IF NOT EXISTS $DB_NAME;" 2>/dev/null
mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" < src/db/schema.sql 2>/dev/null
echo "Database setup complete."

# Create default admin user via the application
echo ""
echo "Creating default admin user..."
mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" -e "
INSERT IGNORE INTO users (username, password_hash, salt, role)
VALUES ('admin', 'placeholder', 'placeholder', 'admin');
" 2>/dev/null
echo "Note: Register a new admin account through the app for proper password hashing."

# Build
echo ""
echo "Building project..."
mkdir -p build
cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
cmake --build .
cd ..

echo ""
echo "=== Setup Complete ==="
echo ""
echo "To run the application:"
echo "  export DB_HOST=$DB_HOST"
echo "  export DB_USER=$DB_USER"
echo "  export DB_PASS=<your_password>"
echo "  export DB_NAME=$DB_NAME"
echo "  ./build/FoodOrderSystem"
echo ""
echo "Or simply:"
echo "  DB_PASS=<your_password> ./build/FoodOrderSystem"
