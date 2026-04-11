#pragma once

// AuthContext — type-safe wrapper around the JWT claims that JwtAuthFilter
// stashes onto the request attributes.
//
// Sprint 2.5 (L-AUTH-CONTEXT) introduced this header so Sprint 3 order
// handlers do not end up sprinkling `attrs->get<int>("user_role") == 1`
// checks throughout the code base — that is a magic-number compare against
// the numeric value of UserRole::ADMIN, which would silently break if the
// enum ever got reordered. Going through the struct + helper means the
// enum change only needs to land in one place (AuthContext.cpp).
//
// Usage (inside a protected controller handler):
//
//   auto ctx = fos::api::readAuthContext(req);
//   if (ctx.isAdmin()) { ... }
//
// The filter remains the single source of truth for "am I authenticated":
// if JwtAuthFilter did not reject the request, the claims are guaranteed
// to be present on the request attributes, and the returned AuthContext
// will be fully populated. On a non-authenticated request (which should
// never reach a gated handler) the getter returns zero-initialised
// defaults — callers must not rely on that path and should always let
// JwtAuthFilter enforce authentication upstream.

#include <string>

#include <drogon/HttpRequest.h>

#include "auth/User.h"

namespace fos::api {

struct AuthContext
{
    int userId = 0;
    std::string username;
    UserRole role = UserRole::CUSTOMER;

    bool isAdmin() const { return role == UserRole::ADMIN; }
};

// Reads the AuthContext that JwtAuthFilter stashed onto the request.
// Must only be called from a handler gated by JwtAuthFilter.
AuthContext readAuthContext(const drogon::HttpRequestPtr& req);

} // namespace fos::api
