#include "JwtAuthFilter.h"

#include <string>

#include "api/JsonEnvelope.h"
#include "service/JwtService.h"

using namespace drogon;
using fos::api::errorResponse;
using fos::service::JwtService;

namespace {
constexpr const char* kBearerPrefix = "Bearer ";
constexpr std::size_t kBearerPrefixLen = 7;
} // namespace

void JwtAuthFilter::doFilter(const HttpRequestPtr& req,
                             FilterCallback&& fcb,
                             FilterChainCallback&& fccb)
{
    const auto& authHeader = req->getHeader("authorization");
    if (authHeader.size() <= kBearerPrefixLen ||
        authHeader.compare(0, kBearerPrefixLen, kBearerPrefix) != 0)
    {
        fcb(errorResponse(
            k401Unauthorized,
            "MISSING_TOKEN",
            "Authorization header with 'Bearer <token>' is required."));
        return;
    }

    const std::string token = authHeader.substr(kBearerPrefixLen);
    auto result = JwtService::verifyToken(token);
    if (!result)
    {
        fcb(errorResponse(
            k401Unauthorized,
            result.error().code,
            result.error().message));
        return;
    }

    // Stash the decoded claims on the request so downstream handlers can
    // read the authenticated user without re-parsing the token.
    const auto& claims = result.value();
    auto attrs = req->getAttributes();
    attrs->insert("user_id", claims.userId);
    attrs->insert("username", claims.username);
    attrs->insert("user_role", static_cast<int>(claims.role));

    fccb();
}
