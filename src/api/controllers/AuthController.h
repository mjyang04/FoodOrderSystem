#pragma once

#include <drogon/HttpController.h>

// AuthController — registration and login endpoints.
//
// Routes:
//   POST /api/auth/register  -> { user_id, username, role }
//   POST /api/auth/login     -> { token, user: { id, username, role } }
//
// Both endpoints accept a JSON body { "username": str, "password": str }.
// Responses follow the unified JSON envelope declared in api/JsonEnvelope.h.
// Registration always creates a CUSTOMER; administrative bootstrap is handled
// out-of-band via the CLI and/or seed SQL.
class AuthController : public drogon::HttpController<AuthController>
{
public:
    METHOD_LIST_BEGIN
    ADD_METHOD_TO(AuthController::registerUser, "/api/auth/register", drogon::Post);
    ADD_METHOD_TO(AuthController::login,        "/api/auth/login",    drogon::Post);
    METHOD_LIST_END

    void registerUser(
        const drogon::HttpRequestPtr& req,
        std::function<void(const drogon::HttpResponsePtr&)>&& callback);

    void login(
        const drogon::HttpRequestPtr& req,
        std::function<void(const drogon::HttpResponsePtr&)>&& callback);
};
