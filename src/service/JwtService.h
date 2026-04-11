#pragma once

// JwtService — issue and verify JSON Web Tokens for FoodOrderSystem.
//
// Tokens are signed with HS256 using a process-wide secret configured from
// JWT_SECRET (config file or environment variable) at startup. The secret is
// never persisted; it lives for the lifetime of the fos_api process.
//
// Claim layout:
//   iss  = "fos_api"
//   sub  = <user id as decimal string>
//   iat  = <unix seconds>
//   exp  = iat + ttlHours*3600
//   role = "ADMIN" | "CUSTOMER"
//   username = <string>
//
// verifyToken() never throws — all jwt-cpp exceptions are mapped to an
// INVALID_TOKEN Result::failure.

#include <string>

#include "auth/User.h"
#include "service/Result.h"

namespace fos::service {

struct JwtClaims
{
    int userId = 0;
    std::string username;
    UserRole role = UserRole::CUSTOMER;
    long long issuedAtEpoch = 0;
    long long expiresAtEpoch = 0;
};

class JwtService
{
public:
    // Configure the signing secret and default TTL. Must be called once at
    // startup before any issue/verify calls.
    static void configure(std::string secret, int ttlHours);

    // Sign a new token for the given user. Returns an empty string if
    // configure() has not been called yet.
    static std::string issueToken(int userId,
                                  const std::string& username,
                                  UserRole role);

    // Verify a Bearer token and extract claims. Error codes:
    //   JWT_NOT_CONFIGURED  - configure() was never called
    //   MISSING_TOKEN       - empty token string
    //   INVALID_TOKEN       - signature mismatch, expired, or malformed
    static Result<JwtClaims> verifyToken(const std::string& token);

private:
    static std::string& secret_();
    static int& ttlHours_();
};

} // namespace fos::service
