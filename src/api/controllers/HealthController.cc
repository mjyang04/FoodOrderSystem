#include "HealthController.h"

#include "api/JsonEnvelope.h"
#include "db/Database.h"

// Sprint 2.5 (L-CONTROLLER-NS): targeted using-declarations instead of
// `using namespace drogon;` — keeps the global namespace clean and makes
// the drogon surface this TU actually depends on explicit.
using drogon::HttpRequestPtr;
using drogon::HttpResponse;
using drogon::HttpResponsePtr;
using drogon::k200OK;
using drogon::k501NotImplemented;
using drogon::k503ServiceUnavailable;
using fos::api::makeEnvelope;

void HealthController::health(const HttpRequestPtr& req,
                               std::function<void(const HttpResponsePtr&)>&& callback)
{
    (void)req;

    const bool dbOk = Database::instance().isConnected();

    Json::Value data;
    data["status"] = dbOk ? "ok" : "degraded";
    data["db"] = dbOk ? "ok" : "error";
    data["version"] = "3.1.0";
    data["service"] = "fos_api";

    auto resp = HttpResponse::newHttpJsonResponse(
        makeEnvelope(dbOk, data, Json::nullValue));
    resp->setStatusCode(dbOk ? k200OK : k503ServiceUnavailable);
    callback(resp);
}

void HealthController::aiChat(const HttpRequestPtr& req,
                               std::function<void(const HttpResponsePtr&)>&& callback)
{
    (void)req;

    // Reserved contract — intentionally returned as 501 so clients can already
    // start integrating against the stable routing surface.
    Json::Value request;
    request["message"] = "string (user utterance)";
    request["session_id"] = "string (optional, preserves conversation state)";
    request["user_id"] = "int (optional, for personalized responses)";

    Json::Value response;
    response["reply"] = "string (assistant reply text)";
    response["session_id"] = "string";
    response["tool_calls"] = Json::arrayValue;

    Json::Value reserved;
    reserved["endpoint"] = "/api/ai/chat";
    reserved["description"] =
        "Natural-language chat interface over the food ordering system. "
        "Will be implemented in the AI/LLM layer sprint and will use Claude "
        "function calling to invoke the same service methods backing the REST API.";
    reserved["request"] = request;
    reserved["response"] = response;

    Json::Value error;
    error["code"] = "NOT_IMPLEMENTED";
    error["message"] = "AI chat endpoint is reserved; see error.reserved_shape.";
    error["reserved_shape"] = reserved;

    auto resp = HttpResponse::newHttpJsonResponse(
        makeEnvelope(false, Json::nullValue, error));
    resp->setStatusCode(k501NotImplemented);
    callback(resp);
}

void HealthController::aiRecommend(const HttpRequestPtr& req,
                                    std::function<void(const HttpResponsePtr&)>&& callback)
{
    (void)req;

    Json::Value request;
    request["user_id"] = "int (required)";
    request["limit"] = "int (optional, default 10)";
    request["context"] = "object (optional: {mood, budget, cuisine_hint})";

    Json::Value item;
    item["food_id"] = "int";
    item["restaurant_id"] = "int";
    item["score"] = "float in [0, 1]";
    item["reason"] = "string (human-readable explanation)";

    Json::Value response;
    response["items"] = Json::Value(Json::arrayValue);
    response["items"].append(item);
    response["strategy"] = "string (embedding|history|hybrid)";

    Json::Value reserved;
    reserved["endpoint"] = "/api/ai/recommend";
    reserved["description"] =
        "Personalized food recommendation. Will use embeddings over menu items "
        "plus user order history; implemented in the AI/LLM layer sprint.";
    reserved["request"] = request;
    reserved["response"] = response;

    Json::Value error;
    error["code"] = "NOT_IMPLEMENTED";
    error["message"] = "AI recommend endpoint is reserved; see error.reserved_shape.";
    error["reserved_shape"] = reserved;

    auto resp = HttpResponse::newHttpJsonResponse(
        makeEnvelope(false, Json::nullValue, error));
    resp->setStatusCode(k501NotImplemented);
    callback(resp);
}
