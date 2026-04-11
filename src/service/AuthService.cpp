#include "service/AuthService.h"

#include <cctype>

#include "db/Database.h"
#include "service/ErrorCodes.h"
#include "util/Logger.h"

namespace fos::service {

namespace {

constexpr std::size_t kMinUsernameLen = 3;
constexpr std::size_t kMaxUsernameLen = 32;
constexpr std::size_t kMinPasswordLen = 6;
constexpr std::size_t kMaxPasswordLen = 128;

} // namespace

Result<void> AuthService::validateUsername(const std::string& username)
{
    if (username.size() < kMinUsernameLen || username.size() > kMaxUsernameLen)
    {
        return Result<void>::failure(
            err::kValidationError,
            "Username must be 3-32 characters long.");
    }
    for (char c : username)
    {
        const auto uc = static_cast<unsigned char>(c);
        if (!std::isalnum(uc) && c != '_' && c != '-')
        {
            return Result<void>::failure(
                err::kValidationError,
                "Username may only contain letters, digits, '_' or '-'.");
        }
    }
    return Result<void>::success();
}

Result<void> AuthService::validatePassword(const std::string& password)
{
    if (password.size() < kMinPasswordLen || password.size() > kMaxPasswordLen)
    {
        return Result<void>::failure(
            err::kValidationError,
            "Password must be 6-128 characters long.");
    }
    return Result<void>::success();
}

Result<int> AuthService::registerUser(const std::string& username,
                                      const std::string& password,
                                      UserRole role)
{
    if (auto v = validateUsername(username); !v)
    {
        return Result<int>::failure(v.error().code, v.error().message);
    }
    if (auto v = validatePassword(password); !v)
    {
        return Result<int>::failure(v.error().code, v.error().message);
    }

    auto& db = Database::instance();
    if (!db.isConnected())
    {
        return Result<int>::failure(
            err::kDbUnavailable,
            "Database is not connected; cannot register users.");
    }

    if (db.userExists(username))
    {
        return Result<int>::failure(
            err::kUserExists,
            "Username is already taken.");
    }

    if (!db.createUser(username, password, role))
    {
        LOG_ERROR("AuthService: createUser failed for '" << username << "'");
        return Result<int>::failure(
            err::kDbError,
            "Could not create user due to a database error.");
    }

    // Fetch back the row to return the new id.
    User created = db.findUserByUsername(username);
    if (created.getId() == 0)
    {
        LOG_ERROR("AuthService: created user '" << username
                   << "' but subsequent lookup returned id=0");
        return Result<int>::failure(
            err::kDbError,
            "User was created but could not be retrieved.");
    }
    return Result<int>::success(created.getId());
}

Result<User> AuthService::authenticate(const std::string& username,
                                       const std::string& password)
{
    // Validation failures on the authenticate path are surfaced as
    // INVALID_CREDENTIALS rather than VALIDATION_ERROR so we never leak which
    // half of the credential pair was wrong.
    if (!validateUsername(username).ok() || !validatePassword(password).ok())
    {
        return Result<User>::failure(
            err::kInvalidCredentials,
            "Invalid username or password.");
    }

    auto& db = Database::instance();
    if (!db.isConnected())
    {
        return Result<User>::failure(
            err::kDbUnavailable,
            "Database is not connected; cannot authenticate.");
    }

    User user = db.findUserByUsername(username);
    if (user.getId() == 0 || !user.verifyPassword(password))
    {
        return Result<User>::failure(
            err::kInvalidCredentials,
            "Invalid username or password.");
    }

    return Result<User>::success(user);
}

} // namespace fos::service
