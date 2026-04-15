#include "service/JwtService.h"

#include <chrono>
#include <exception>

#include <jwt-cpp/jwt.h>

#include "service/ErrorCodes.h"
#include "util/Logger.h"

namespace fos::service {

namespace {
// Minimum recommended secret length for HS256 == HMAC-SHA256 output size.
constexpr std::size_t kMinSecretLen = 32;
} // namespace

std::string& JwtService::secret_()
{
    static std::string s;
    return s;
}

int& JwtService::ttlHours_()
{
    static int h = 24;
    return h;
}

void JwtService::configure(std::string secret, int ttlHours)
{
    // NOTE: configure() must only be called once at startup before Drogon's
    // worker pool begins accepting requests. The function-local statics below
    // are not guarded by a mutex; see Sprint 2.5 backlog for the hardening
    // plan if we ever need to hot-reload the secret.
    if (!secret.empty() && secret.size() < kMinSecretLen)
    {
        LOG_WARN("JwtService: JWT_SECRET is only " << secret.size()
                 << " bytes. HS256 recommends at least "
                 << kMinSecretLen << " bytes of high-entropy input. "
                 << "Generate one with 'openssl rand -hex 32'.");
    }
    secret_() = std::move(secret);
    ttlHours_() = ttlHours > 0 ? ttlHours : 24;
}

Result<std::string> JwtService::issueToken(int userId,
                                           const std::string& username,
                                           UserRole role)
{
    if (secret_().empty())
    {
        LOG_ERROR("JwtService::issueToken called before configure() — "
                  "JWT_SECRET is missing from config");
        return Result<std::string>::failure(
            err::kJwtNotConfigured,
            "JWT signing is not configured on the server.");
    }

    const auto now = std::chrono::system_clock::now();
    const auto exp = now + std::chrono::hours{ttlHours_()};
    const std::string roleStr =
        (role == UserRole::ADMIN) ? "ADMIN" : "CUSTOMER";

    try
    {
        std::string token =
            jwt::create()
                .set_issuer("fos_api")
                .set_type("JWT")
                .set_subject(std::to_string(userId))
                .set_payload_claim("username",
                                   jwt::claim(std::string{username}))
                .set_payload_claim("role", jwt::claim(roleStr))
                .set_issued_at(now)
                .set_expires_at(exp)
                .sign(jwt::algorithm::hs256{secret_()});
        return Result<std::string>::success(std::move(token));
    }
    catch (const std::exception& ex)
    {
        // jwt-cpp sign failures are very unusual (OOM, internal bug). Log
        // the detail server-side but do NOT forward it to the caller.
        LOG_ERROR("JwtService::issueToken exception: " << ex.what());
        return Result<std::string>::failure(
            err::kInvalidToken,
            "Failed to sign token.");
    }
}

Result<JwtClaims> JwtService::verifyToken(const std::string& token)
{
    if (secret_().empty())
    {
        return Result<JwtClaims>::failure(
            err::kJwtNotConfigured,
            "JWT secret is not configured on the server.");
    }
    if (token.empty())
    {
        return Result<JwtClaims>::failure(
            err::kMissingToken,
            "Authorization token is missing.");
    }

    // Generic client-facing message for every verification failure below.
    // jwt-cpp exception details are logged server-side only — never echoed
    // in the HTTP response — to avoid leaking library internals and token
    // fragments (Sprint 2 security review finding S-H1).
    static constexpr const char* kGenericVerifyFailed =
        "Token is invalid or has expired.";

    try
    {
        auto decoded = jwt::decode(token);
        auto verifier = jwt::verify()
            .allow_algorithm(jwt::algorithm::hs256{secret_()})
            .with_issuer("fos_api");
        verifier.verify(decoded);

        JwtClaims claims;
        try
        {
            claims.userId = std::stoi(decoded.get_subject());
        }
        catch (const std::exception& ex)
        {
            LOG_WARN("JwtService::verifyToken: subject not numeric: "
                     << ex.what());
            return Result<JwtClaims>::failure(
                err::kInvalidToken, kGenericVerifyFailed);
        }

        if (decoded.has_payload_claim("username"))
        {
            claims.username =
                decoded.get_payload_claim("username").as_string();
        }
        if (decoded.has_payload_claim("role"))
        {
            const auto r =
                decoded.get_payload_claim("role").as_string();
            claims.role = (r == "ADMIN") ? UserRole::ADMIN
                                         : UserRole::CUSTOMER;
        }
        claims.issuedAtEpoch =
            std::chrono::duration_cast<std::chrono::seconds>(
                decoded.get_issued_at().time_since_epoch())
                .count();
        claims.expiresAtEpoch =
            std::chrono::duration_cast<std::chrono::seconds>(
                decoded.get_expires_at().time_since_epoch())
                .count();

        return Result<JwtClaims>::success(claims);
    }
    catch (const std::exception& ex)
    {
        LOG_WARN("JwtService::verifyToken failed: " << ex.what());
        return Result<JwtClaims>::failure(
            err::kInvalidToken, kGenericVerifyFailed);
    }
}

} // namespace fos::service
