#include "AuthController.h"

#include "api/JsonEnvelope.h"
#include "auth/User.h"
#include "service/AuthService.h"
#include "service/JwtService.h"

using namespace drogon;
using fos::api::errorResponse;
using fos::api::successResponse;
using fos::service::AuthService;
using fos::service::JwtService;

namespace {

Json::Value userToJson(const User& user)
{
    Json::Value j;
    j["id"] = user.getId();
    j["username"] = user.getUsername();
    j["role"] = user.isAdmin() ? "ADMIN" : "CUSTOMER";
    return j;
}

// Map service-layer error codes to HTTP status codes.
HttpStatusCode statusForError(const std::string& code)
{
    if (code == "VALIDATION_ERROR")    return k400BadRequest;
    if (code == "INVALID_CREDENTIALS") return k401Unauthorized;
    if (code == "USER_EXISTS")         return k409Conflict;
    if (code == "DB_UNAVAILABLE")      return k503ServiceUnavailable;
    if (code == "DB_ERROR")            return k500InternalServerError;
    if (code == "JWT_NOT_CONFIGURED")  return k500InternalServerError;
    return k400BadRequest;
}

// Extract and minimally validate a {username, password} JSON body.
// On failure, writes an error response via callback and returns false.
bool extractCredentials(
    const HttpRequestPtr& req,
    const std::function<void(const HttpResponsePtr&)>& callback,
    std::string& username,
    std::string& password)
{
    const auto bodyPtr = req->getJsonObject();
    if (!bodyPtr)
    {
        callback(errorResponse(
            k400BadRequest,
            "INVALID_JSON",
            "Request body must be a valid JSON object."));
        return false;
    }
    const Json::Value& body = *bodyPtr;

    if (!body.isMember("username") || !body["username"].isString() ||
        !body.isMember("password") || !body["password"].isString())
    {
        callback(errorResponse(
            k400BadRequest,
            "VALIDATION_ERROR",
            "Both 'username' and 'password' are required string fields."));
        return false;
    }

    username = body["username"].asString();
    password = body["password"].asString();
    return true;
}

} // namespace

void AuthController::registerUser(
    const HttpRequestPtr& req,
    std::function<void(const HttpResponsePtr&)>&& callback)
{
    std::string username;
    std::string password;
    if (!extractCredentials(req, callback, username, password))
    {
        return;
    }

    // Role is forced to CUSTOMER via the HTTP entry point. Admin accounts
    // must be created through the CLI or seed SQL. Sprint 3 may introduce an
    // invite/bootstrap flow.
    auto result = AuthService::registerUser(username, password, UserRole::CUSTOMER);
    if (!result)
    {
        callback(errorResponse(
            statusForError(result.error().code),
            result.error().code,
            result.error().message));
        return;
    }

    Json::Value data;
    data["user_id"] = result.value();
    data["username"] = username;
    data["role"] = "CUSTOMER";
    callback(successResponse(data, k201Created));
}

void AuthController::login(
    const HttpRequestPtr& req,
    std::function<void(const HttpResponsePtr&)>&& callback)
{
    std::string username;
    std::string password;
    if (!extractCredentials(req, callback, username, password))
    {
        return;
    }

    auto result = AuthService::authenticate(username, password);
    if (!result)
    {
        callback(errorResponse(
            statusForError(result.error().code),
            result.error().code,
            result.error().message));
        return;
    }

    const User& user = result.value();
    const std::string token = JwtService::issueToken(
        user.getId(), user.getUsername(), user.getRole());
    if (token.empty())
    {
        callback(errorResponse(
            k500InternalServerError,
            "JWT_NOT_CONFIGURED",
            "JWT signing is not configured on the server."));
        return;
    }

    Json::Value data;
    data["token"] = token;
    data["user"] = userToJson(user);
    callback(successResponse(data));
}
