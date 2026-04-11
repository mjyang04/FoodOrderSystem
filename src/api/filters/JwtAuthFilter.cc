#include "JwtAuthFilter.h"

#include <cctype>
#include <cstddef>
#include <string>

#include "api/JsonEnvelope.h"
#include "service/ErrorCodes.h"
#include "service/JwtService.h"

using namespace drogon;
using fos::api::errorResponse;
using fos::service::JwtService;
namespace err = fos::service::err;

namespace {
// RFC 7235 §2.1: the auth-scheme token is case-insensitive. Sprint 2.5
// (M-BEARER-CASE) relaxed this from a literal "Bearer " match to a case-
// folded compare so clients sending "bearer <token>" (lowercase) are not
// rejected with 401. The prefix length stays fixed at 7 because the scheme
// must still be followed by a single space separator before the token.
constexpr std::size_t kBearerPrefixLen = 7;

// Returns true iff `header` starts with a case-insensitive "bearer "
// scheme-plus-space prefix. Space separator is required and must be an
// ASCII space to match the existing substr(7) extraction below.
bool hasBearerPrefix(const std::string& header)
{
    if (header.size() <= kBearerPrefixLen) return false;
    static constexpr char kScheme[] = {'b', 'e', 'a', 'r', 'e', 'r'};
    for (std::size_t i = 0; i < sizeof(kScheme); ++i)
    {
        const unsigned char c = static_cast<unsigned char>(header[i]);
        if (static_cast<char>(std::tolower(c)) != kScheme[i]) return false;
    }
    return header[sizeof(kScheme)] == ' ';
}
} // namespace

void JwtAuthFilter::doFilter(const HttpRequestPtr& req,
                             FilterCallback&& fcb,
                             FilterChainCallback&& fccb)
{
    const auto& authHeader = req->getHeader("authorization");
    if (!hasBearerPrefix(authHeader))
    {
        fcb(errorResponse(
            k401Unauthorized,
            err::kMissingToken,
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
