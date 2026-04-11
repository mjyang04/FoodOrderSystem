#pragma once

#include <drogon/HttpController.h>

// HealthController exposes liveness/readiness and reserved AI/LLM endpoints.
//
// Routes:
//   GET  /health              -> { status, db, version }
//   POST /api/ai/chat         -> 501, reserved shape for future LLM chat
//   POST /api/ai/recommend    -> 501, reserved shape for future LLM recommend
//
// The /api/ai/* endpoints intentionally return 501 Not Implemented with a
// "reserved_shape" body so that future clients can already start against the
// stable routing surface while the AI/LLM layer is built in a later sprint.
class HealthController : public drogon::HttpController<HealthController>
{
public:
    METHOD_LIST_BEGIN
    ADD_METHOD_TO(HealthController::health, "/health", drogon::Get);
    ADD_METHOD_TO(HealthController::aiChat, "/api/ai/chat", drogon::Post, drogon::Get);
    ADD_METHOD_TO(HealthController::aiRecommend, "/api/ai/recommend", drogon::Post, drogon::Get);
    METHOD_LIST_END

    void health(const drogon::HttpRequestPtr& req,
                std::function<void(const drogon::HttpResponsePtr&)>&& callback);

    void aiChat(const drogon::HttpRequestPtr& req,
                std::function<void(const drogon::HttpResponsePtr&)>&& callback);

    void aiRecommend(const drogon::HttpRequestPtr& req,
                     std::function<void(const drogon::HttpResponsePtr&)>&& callback);
};
