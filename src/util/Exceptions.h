#ifndef EXCEPTIONS_H
#define EXCEPTIONS_H

#include <stdexcept>
#include <string>

// Base exception for the application
class AppException : public std::runtime_error
{
public:
    explicit AppException(const std::string& msg) : std::runtime_error(msg) {}
};

// Database-related errors
class DatabaseException : public AppException
{
public:
    explicit DatabaseException(const std::string& msg) : AppException("Database error: " + msg) {}
};

class ConnectionException : public DatabaseException
{
public:
    explicit ConnectionException(const std::string& msg) : DatabaseException("Connection failed: " + msg) {}
};

class QueryException : public DatabaseException
{
public:
    explicit QueryException(const std::string& msg) : DatabaseException("Query failed: " + msg) {}
};

// Authentication errors
class AuthException : public AppException
{
public:
    explicit AuthException(const std::string& msg) : AppException("Auth error: " + msg) {}
};

class InvalidCredentialsException : public AuthException
{
public:
    InvalidCredentialsException() : AuthException("Invalid username or password") {}
};

class UserExistsException : public AuthException
{
public:
    explicit UserExistsException(const std::string& username)
        : AuthException("User already exists: " + username) {}
};

// Order errors
class OrderException : public AppException
{
public:
    explicit OrderException(const std::string& msg) : AppException("Order error: " + msg) {}
};

class OrderNotFoundException : public OrderException
{
public:
    explicit OrderNotFoundException(int orderId)
        : OrderException("Order not found: #" + std::to_string(orderId)) {}
};

class InvalidOrderStateException : public OrderException
{
public:
    explicit InvalidOrderStateException(const std::string& msg)
        : OrderException("Invalid state transition: " + msg) {}
};

// Input validation errors
class ValidationException : public AppException
{
public:
    explicit ValidationException(const std::string& msg) : AppException("Validation error: " + msg) {}
};

#endif // EXCEPTIONS_H
