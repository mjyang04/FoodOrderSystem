#include "AuthController.h"

#include "api/JsonBody.h"
#include "api/JsonEnvelope.h"
#include "auth/User.h"
#include "service/AuthService.h"
#include "service/DefaultServices.h"
#include "service/JwtService.h"

using namespace drogon;
using fos::api::errorResponse;
using fos::api::requireJsonObject;
using fos::api::requireStringField;
using fos::api::statusForError;
using fos::api::successResponse;
using fos::service::defaultAuthService;
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

// Pull {username, password} from a JSON body via the shared helpers. Thin
// wrapper that centralizes the auth-specific field list so register/login
// stay in sync. Sprint 3 controllers should call requireJsonObject /
// requireStringField / requireIntField directly.
bool extractCredentials(
    const HttpRequestPtr& req,
    const std::function<void(const HttpResponsePtr&)>& callback,
    std::string& username,
    std::string& password)
{
    auto bodyPtr = requireJsonObject(req, callback);
    if (!bodyPtr) return false;
    const Json::Value& body = *bodyPtr;

    if (!requireStringField(body, "username", username, callback)) return false;
    if (!requireStringField(body, "password", password, callback)) return false;
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
    auto result = defaultAuthService().registerUser(username, password, UserRole::CUSTOMER);
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

    auto result = defaultAuthService().authenticate(username, password);
    if (!result)
    {
        callback(errorResponse(
            statusForError(result.error().code),
            result.error().code,
            result.error().message));
        return;
    }

    const User& user = result.value();
    auto tokenResult = JwtService::issueToken(
        user.getId(), user.getUsername(), user.getRole());
    if (!tokenResult)
    {
        callback(errorResponse(
            statusForError(tokenResult.error().code),
            tokenResult.error().code,
            tokenResult.error().message));
        return;
    }

    Json::Value data;
    data["token"] = tokenResult.value();
    data["user"] = userToJson(user);
    callback(successResponse(data));
}
