#include "service/JwtService.h"

#include <chrono>
#include <exception>

#include <jwt-cpp/jwt.h>

#include "util/Logger.h"

namespace fos::service {

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
    secret_() = std::move(secret);
    ttlHours_() = ttlHours > 0 ? ttlHours : 24;
}

std::string JwtService::issueToken(int userId,
                                   const std::string& username,
                                   UserRole role)
{
    if (secret_().empty())
    {
        LOG_ERROR("JwtService::issueToken called before configure() — "
                  "JWT_SECRET is missing from config");
        return {};
    }

    const auto now = std::chrono::system_clock::now();
    const auto exp = now + std::chrono::hours{ttlHours_()};
    const std::string roleStr =
        (role == UserRole::ADMIN) ? "ADMIN" : "CUSTOMER";

    try
    {
        return jwt::create()
            .set_issuer("fos_api")
            .set_type("JWT")
            .set_subject(std::to_string(userId))
            .set_payload_claim("username", jwt::claim(std::string{username}))
            .set_payload_claim("role", jwt::claim(roleStr))
            .set_issued_at(now)
            .set_expires_at(exp)
            .sign(jwt::algorithm::hs256{secret_()});
    }
    catch (const std::exception& ex)
    {
        LOG_ERROR("JwtService::issueToken exception: " << ex.what());
        return {};
    }
}

Result<JwtClaims> JwtService::verifyToken(const std::string& token)
{
    if (secret_().empty())
    {
        return Result<JwtClaims>::failure(
            "JWT_NOT_CONFIGURED",
            "JWT secret is not configured on the server.");
    }
    if (token.empty())
    {
        return Result<JwtClaims>::failure(
            "MISSING_TOKEN",
            "Authorization token is missing.");
    }

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
        catch (const std::exception&)
        {
            return Result<JwtClaims>::failure(
                "INVALID_TOKEN",
                "Token subject is not a valid user id.");
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
        return Result<JwtClaims>::failure(
            "INVALID_TOKEN",
            std::string("Token verification failed: ") + ex.what());
    }
}

} // namespace fos::service
