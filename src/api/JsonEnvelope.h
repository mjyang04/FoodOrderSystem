#pragma once

// Unified JSON response envelope for the FoodOrderSystem REST API.
//
// Every response body follows the shape:
//   {
//     "success": bool,
//     "data":    <any | null>,
//     "error":   { "code": string, "message": string, ... } | null
//   }
//
// Controllers should construct responses via successResponse() /
// errorResponse() to guarantee clients can parse the envelope consistently.

#include <drogon/HttpResponse.h>
#include <drogon/HttpTypes.h>
#include <json/value.h>

#include <string>

#include "service/ErrorCodes.h"

namespace fos::api {

inline Json::Value makeEnvelope(bool success,
                                const Json::Value& data,
                                const Json::Value& error)
{
    Json::Value envelope;
    envelope["success"] = success;
    envelope["data"] = data;
    envelope["error"] = error;
    return envelope;
}

inline drogon::HttpResponsePtr successResponse(
    const Json::Value& data,
    drogon::HttpStatusCode code = drogon::k200OK)
{
    auto resp = drogon::HttpResponse::newHttpJsonResponse(
        makeEnvelope(true, data, Json::nullValue));
    resp->setStatusCode(code);
    return resp;
}

inline drogon::HttpResponsePtr errorResponse(
    drogon::HttpStatusCode code,
    const std::string& errorCode,
    const std::string& message)
{
    Json::Value error;
    error["code"] = errorCode;
    error["message"] = message;
    auto resp = drogon::HttpResponse::newHttpJsonResponse(
        makeEnvelope(false, Json::nullValue, error));
    resp->setStatusCode(code);
    return resp;
}

// Canonical service-error -> HTTP status mapping.
//
// Every controller should route service-layer errors through this single
// function instead of inlining its own if/else ladder. Keyed off the
// `fos::service::err::k*` string constants so a new error code only needs
// to be added here once.
//
// Unknown codes default to 400 BadRequest — callers that want a different
// fallback should branch on the code themselves before calling this.
inline drogon::HttpStatusCode statusForError(const std::string& code)
{
    namespace err = fos::service::err;
    if (code == err::kValidationError)    return drogon::k400BadRequest;
    if (code == err::kInvalidCredentials) return drogon::k401Unauthorized;
    if (code == err::kMissingToken)       return drogon::k401Unauthorized;
    if (code == err::kInvalidToken)       return drogon::k401Unauthorized;
    if (code == err::kUserExists)         return drogon::k409Conflict;
    if (code == err::kRestaurantNotFound) return drogon::k404NotFound;
    // Sprint 3: order lifecycle error codes. kOrderNotFound also covers the
    // "not your order" case — see OrderService::getOrder and plan Q1 for the
    // existence-leak collapse rationale. kForbidden stays reserved in the
    // vocabulary even though Sprint 3 does not emit it, so Sprint 4+ admin
    // endpoints can distinguish 403 from 404 without re-drafting the map.
    if (code == err::kOrderNotFound)      return drogon::k404NotFound;
    if (code == err::kEmptyOrder)         return drogon::k400BadRequest;
    if (code == err::kInvalidQuantity)    return drogon::k400BadRequest;
    if (code == err::kMenuItemMismatch)   return drogon::k400BadRequest;
    if (code == err::kForbidden)          return drogon::k403Forbidden;
    if (code == err::kDbUnavailable)      return drogon::k503ServiceUnavailable;
    if (code == err::kDbError)            return drogon::k500InternalServerError;
    if (code == err::kJwtNotConfigured)   return drogon::k500InternalServerError;
    // Sprint 4: AI/LLM layer codes. See plan/sprint_4_ai_layer.md §5.
    if (code == err::kAiUnavailable)      return drogon::k503ServiceUnavailable;
    if (code == err::kAiBadRequest)       return drogon::k400BadRequest;
    if (code == err::kAiUpstreamError)    return drogon::k502BadGateway;
    if (code == err::kAiLlmRefused)       return drogon::k422UnprocessableEntity;
    // Sprint 5: order status + chat codes.
    if (code == err::kInvalidStatusTransition) return drogon::k400BadRequest;
    if (code == err::kOrderAlreadyRated)       return drogon::k409Conflict;
    if (code == err::kAiSessionNotFound)       return drogon::k404NotFound;
    if (code == err::kAiToolError)             return drogon::k502BadGateway;
    if (code == err::kAiMaxIterations)         return drogon::k502BadGateway;
    return drogon::k400BadRequest;
}

} // namespace fos::api
