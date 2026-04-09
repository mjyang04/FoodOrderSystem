#include "LoginSystem.h"
#include "../db/Database.h"
#include "../ui/Color.h"
#include "../util/InputHelper.h"
#include <iostream>

User LoginSystem::login()
{
    auto& db = Database::instance();

    while (true)
    {
        InputHelper::clearScreen();
        std::cout << Color::BOLD << Color::BLUE
                  << "========================================\n"
                  << "    Welcome to Food Order System\n"
                  << "========================================\n"
                  << Color::RESET;
        std::cout << "1. Login\n2. Register\n3. Exit\n";
        int choice = InputHelper::readInt("Choose: ", 1, 3);

        if (choice == 3)
        {
            std::cout << Color::GREEN << "Goodbye!" << Color::RESET << std::endl;
            std::exit(0);
        }

        if (choice == 2)
        {
            registerUser();
            continue;
        }

        // Login
        std::string username = InputHelper::readString("Username: ");
        std::string password = InputHelper::readString("Password: ");

        User user = db.findUserByUsername(username);
        if (user.getId() == 0 || !user.verifyPassword(password))
        {
            InputHelper::clearScreen();
            std::cout << Color::RED << "Invalid username or password. Please try again."
                      << Color::RESET << std::endl;
            continue;
        }

        InputHelper::clearScreen();
        std::cout << Color::GREEN << "Login successful! Welcome, " << user.getUsername()
                  << (user.isAdmin() ? " [Admin]" : "") << Color::RESET << std::endl;
        return user;
    }
}

bool LoginSystem::registerUser()
{
    auto& db = Database::instance();
    InputHelper::clearScreen();

    std::cout << Color::BOLD << Color::CYAN << "=== User Registration ===" << Color::RESET << std::endl;
    std::string username = InputHelper::readString("Choose a username: ");

    if (db.userExists(username))
    {
        std::cout << Color::RED << "Username already exists." << Color::RESET << std::endl;
        return false;
    }

    std::string password = InputHelper::readString("Choose a password: ");
    std::string confirm = InputHelper::readString("Confirm password: ");

    if (password != confirm)
    {
        std::cout << Color::RED << "Passwords do not match." << Color::RESET << std::endl;
        return false;
    }

    if (db.createUser(username, password))
    {
        std::cout << Color::GREEN << "Registration successful! You can now log in."
                  << Color::RESET << std::endl;
        return true;
    }

    std::cout << Color::RED << "Registration failed." << Color::RESET << std::endl;
    return false;
}
