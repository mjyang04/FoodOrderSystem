#pragma once

// AuthService — stdin-free authentication and registration API.
//
// This is the contract that HTTP controllers (and the future LLM function
// calling layer) call into. It wraps the IUserRepo operations with input
// validation and a Result<T> error protocol.
//
// Sprint 2.5 (H-DI) turned this into an instance class that takes an
// IUserRepo& in its constructor so it can be unit-tested against an
// in-memory fake without a live MySQL server. For the production HTTP
// path, call DefaultServices::defaultAuthService() — it wires the
// singleton to the real Database instance.
//
// Error codes returned via Result<T>::error().code:
//   VALIDATION_ERROR     - Input failed length/charset validation
//   USER_EXISTS          - Username is already taken (register only)
//   INVALID_CREDENTIALS  - Unknown user or password mismatch (auth only)
//   DB_UNAVAILABLE       - Underlying repo is not connected
//   DB_ERROR             - Generic repository failure (query failed, etc.)

#include <string>

#include "auth/User.h"
#include "db/IUserRepo.h"
#include "service/Result.h"

namespace fos::service {

class AuthService
{
public:
    explicit AuthService(IUserRepo& repo) : repo_(repo) {}

    // Register a new user. Returns the new user id on success.
    Result<int> registerUser(const std::string& username,
                             const std::string& password,
                             UserRole role = UserRole::CUSTOMER);

    // Authenticate a user. Returns the full User record on success.
    Result<User> authenticate(const std::string& username,
                              const std::string& password);

private:
    Result<void> validateUsername(const std::string& username);
    Result<void> validatePassword(const std::string& password);

    IUserRepo& repo_;
};

} // namespace fos::service
