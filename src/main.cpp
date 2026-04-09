#include <iostream>
#include <string>
#include <cstdlib>
#include "db/Database.h"
#include "auth/LoginSystem.h"
#include "core/FoodOrderSystem.h"
#include "ui/Color.h"

int main()
{
    // Read database config from environment variables (with defaults)
    std::string dbHost = std::getenv("DB_HOST") ? std::getenv("DB_HOST") : "127.0.0.1";
    std::string dbUser = std::getenv("DB_USER") ? std::getenv("DB_USER") : "root";
    std::string dbPass = std::getenv("DB_PASS") ? std::getenv("DB_PASS") : "";
    std::string dbName = std::getenv("DB_NAME") ? std::getenv("DB_NAME") : "food_order_system";
    unsigned int dbPort = std::getenv("DB_PORT") ? std::stoi(std::getenv("DB_PORT")) : 3306;

    // Connect to MySQL
    auto& db = Database::instance();
    if (!db.connect(dbHost, dbUser, dbPass, dbName, dbPort))
    {
        std::cerr << Color::RED
                  << "Failed to connect to MySQL database.\n"
                  << "Make sure MySQL is running and the database exists.\n\n"
                  << "Quick setup:\n"
                  << "  mysql -u root -p -e \"CREATE DATABASE food_order_system;\"\n"
                  << "  mysql -u root -p food_order_system < src/db/schema.sql\n\n"
                  << "Or set environment variables:\n"
                  << "  export DB_HOST=127.0.0.1\n"
                  << "  export DB_USER=root\n"
                  << "  export DB_PASS=yourpassword\n"
                  << "  export DB_NAME=food_order_system\n"
                  << Color::RESET << std::endl;
        return 1;
    }

    std::cout << Color::GREEN << "Database connected." << Color::RESET << std::endl;

    // Initialize schema (creates tables if they don't exist)
    db.initializeSchema();

    // Login or Register
    LoginSystem loginSystem;
    User currentUser = loginSystem.login();

    // Run the main system
    FoodOrderSystem system;
    system.setCurrentUser(currentUser);
    system.showMainMenu();

    db.disconnect();
    return 0;
}
