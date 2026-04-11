#pragma once

// AuthService — stdin-free authentication and registration API.
//
// This is the contract that HTTP controllers (and the future LLM function
// calling layer) call into. It wraps Database::{createUser, findUserByUsername,
// userExists} with input validation and a Result<T> error protocol.
//
// Error codes returned via Result<T>::error().code:
//   VALIDATION_ERROR     - Input failed length/charset validation
//   USER_EXISTS          - Username is already taken (register only)
//   INVALID_CREDENTIALS  - Unknown user or password mismatch (auth only)
//   DB_UNAVAILABLE       - Database singleton is not connected
//   DB_ERROR             - Generic database failure (query failed, etc.)

#include <string>

#include "auth/User.h"
#include "service/Result.h"

namespace fos::service {

class AuthService
{
public:
    // Register a new user. Returns the new user id on success.
    static Result<int> registerUser(const std::string& username,
                                    const std::string& password,
                                    UserRole role = UserRole::CUSTOMER);

    // Authenticate a user. Returns the full User record on success.
    static Result<User> authenticate(const std::string& username,
                                     const std::string& password);

private:
    static Result<void> validateUsername(const std::string& username);
    static Result<void> validatePassword(const std::string& password);
};

} // namespace fos::service
