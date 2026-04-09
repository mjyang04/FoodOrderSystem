#include <iostream>
#include <string>
#include "db/Database.h"
#include "auth/LoginSystem.h"
#include "core/FoodOrderSystem.h"
#include "ui/Color.h"
#include "util/Config.h"
#include "util/Logger.h"

int main()
{
    // Load config (file -> env var -> defaults)
    auto& config = Config::instance();
    config.loadFromFile("config");  // Optional: load from config file

    // Setup logger
    auto& logger = Logger::instance();
    std::string logLevel = config.getString("LOG_LEVEL", "INFO");
    if (logLevel == "DEBUG") logger.setLevel(LogLevel::DEBUG);
    else if (logLevel == "WARNING") logger.setLevel(LogLevel::WARNING);
    else if (logLevel == "ERROR") logger.setLevel(LogLevel::ERROR);
    else logger.setLevel(LogLevel::INFO);

    std::string logFile = config.getString("LOG_FILE", "");
    if (!logFile.empty()) logger.setLogFile(logFile);

    // Read database config
    std::string dbHost = config.getString("DB_HOST", "127.0.0.1");
    std::string dbUser = config.getString("DB_USER", "root");
    std::string dbPass = config.getString("DB_PASS", "");
    std::string dbName = config.getString("DB_NAME", "food_order_system");
    unsigned int dbPort = static_cast<unsigned int>(config.getInt("DB_PORT", 3306));

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
