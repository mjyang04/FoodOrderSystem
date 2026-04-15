#pragma once

#include <drogon/HttpController.h>

// AuthController — registration and login endpoints.
//
// Routes:
//   POST /api/auth/register  -> { user_id, username, role }
//   POST /api/auth/login     -> { token, user: { id, username, role } }
//   GET  /api/auth/me        -> { id, username, role }   [JwtAuthFilter]
//
// register/login accept a JSON body { "username": str, "password": str }.
// me is gated on JwtAuthFilter — it returns whatever the filter stashed on
// the request attributes, which is the cheapest way to exercise the
// filter end-to-end (Sprint 2.5 M-FILTER-SMOKE).
// Responses follow the unified JSON envelope declared in api/JsonEnvelope.h.
// Registration always creates a CUSTOMER; administrative bootstrap is handled
// out-of-band via the CLI and/or seed SQL.
class AuthController : public drogon::HttpController<AuthController>
{
public:
    METHOD_LIST_BEGIN
    ADD_METHOD_TO(AuthController::registerUser, "/api/auth/register", drogon::Post);
    ADD_METHOD_TO(AuthController::login,        "/api/auth/login",    drogon::Post);
    ADD_METHOD_TO(AuthController::me,           "/api/auth/me",       drogon::Get, "JwtAuthFilter");
    METHOD_LIST_END

    void registerUser(
        const drogon::HttpRequestPtr& req,
        std::function<void(const drogon::HttpResponsePtr&)>&& callback);

    void login(
        const drogon::HttpRequestPtr& req,
        std::function<void(const drogon::HttpResponsePtr&)>&& callback);

    // Protected read of the decoded JWT claims. Returns whatever the
    // JwtAuthFilter stashed on the request attributes; the filter is the
    // one responsible for rejecting missing / invalid tokens with 401.
    void me(
        const drogon::HttpRequestPtr& req,
        std::function<void(const drogon::HttpResponsePtr&)>&& callback);
};
