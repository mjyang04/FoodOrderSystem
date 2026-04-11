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

} // namespace fos::api
