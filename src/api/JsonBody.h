#pragma once

// JsonBody — shared helpers for parsing and validating JSON request bodies.
//
// Every controller that reads a JSON body should route through these helpers
// instead of calling req->getJsonObject() directly, because:
//
//   1. They enforce a per-endpoint body size cap BEFORE handing bytes to
//      jsoncpp's parser. The default cap is 4 KiB, which covers every
//      credential/order payload in this project and prevents a client from
//      pushing jsoncpp into quadratic territory with a pathological blob.
//      (Sprint 2.5 backlog item M-BODY-CAP.)
//
//   2. They centralize the "validate JSON body then pull required fields"
//      pattern that AuthController grew in Sprint 2. Sprint 3's
//      OrderController will need the same shape plus numeric fields —
//      extracting the helpers now prevents three-way copy-paste drift.
//      (Sprint 2.5 backlog item M-JSONBODY-HELPER.)
//
// On failure every helper writes an `errorResponse` via the supplied callback
// and returns a falsy value (nullptr / false), so the caller can `return`
// immediately without constructing the response itself.

#include <drogon/HttpRequest.h>
#include <drogon/HttpResponse.h>
#include <drogon/HttpTypes.h>
#include <json/value.h>

#include <cstddef>
#include <functional>
#include <memory>
#include <string>

#include "api/JsonEnvelope.h"

namespace fos::api {

// Default per-endpoint body size cap. Every payload in the current and
// planned REST surface (credentials, order line items) fits well under this.
inline constexpr std::size_t kDefaultJsonBodyCap = 4096;

// Parse and validate a JSON object body with a size cap.
//
// Returns a non-null shared pointer to the parsed Json::Value on success.
// On any failure (body too large, not valid JSON, not a JSON object) writes
// the appropriate error response via `callback` and returns nullptr.
inline std::shared_ptr<Json::Value> requireJsonObject(
    const drogon::HttpRequestPtr& req,
    const std::function<void(const drogon::HttpResponsePtr&)>& callback,
    std::size_t maxBytes = kDefaultJsonBodyCap)
{
    if (req->getBody().size() > maxBytes)
    {
        callback(errorResponse(
            drogon::k413RequestEntityTooLarge,
            "PAYLOAD_TOO_LARGE",
            "Request body exceeds the maximum allowed size."));
        return nullptr;
    }

    auto bodyPtr = req->getJsonObject();
    if (!bodyPtr)
    {
        callback(errorResponse(
            drogon::k400BadRequest,
            "INVALID_JSON",
            "Request body must be a valid JSON object."));
        return nullptr;
    }
    return bodyPtr;
}

// Pull a required string field out of a JSON object.
//
// On success returns true and writes the value into `out`. On missing field
// or wrong type writes a 400 VALIDATION_ERROR via `callback` and returns
// false. The field name is echoed in the error message so API clients know
// which field to fix.
inline bool requireStringField(
    const Json::Value& body,
    const char* field,
    std::string& out,
    const std::function<void(const drogon::HttpResponsePtr&)>& callback)
{
    if (!body.isMember(field) || !body[field].isString())
    {
        callback(errorResponse(
            drogon::k400BadRequest,
            "VALIDATION_ERROR",
            std::string("Field '") + field +
                "' is required and must be a string."));
        return false;
    }
    out = body[field].asString();
    return true;
}

// Pull a required int field out of a JSON object. Accepts only JSON numbers
// that fit in `int` — a numeric string is not auto-coerced. Sprint 3 order
// endpoints will use this for `restaurant_id` and line-item quantities.
inline bool requireIntField(
    const Json::Value& body,
    const char* field,
    int& out,
    const std::function<void(const drogon::HttpResponsePtr&)>& callback)
{
    if (!body.isMember(field) || !body[field].isInt())
    {
        callback(errorResponse(
            drogon::k400BadRequest,
            "VALIDATION_ERROR",
            std::string("Field '") + field +
                "' is required and must be an integer."));
        return false;
    }
    out = body[field].asInt();
    return true;
}

} // namespace fos::api
