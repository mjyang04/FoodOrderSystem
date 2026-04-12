#pragma once

#include <drogon/HttpController.h>

// HealthController exposes liveness/readiness and reserved AI/LLM endpoints.
//
// Routes:
//   GET  /health              -> { status, db, version }
//   POST /api/ai/chat         -> 501, reserved shape for future LLM chat
//
// Sprint 4 moved /api/ai/recommend and /api/ai/search and /api/ai/parse-order
// to AiController (real proxy to fos_ai). The /api/ai/chat stub stays here
// as a 501 reservation until Sprint 5 implements multi-turn chat.
class HealthController : public drogon::HttpController<HealthController>
{
public:
    METHOD_LIST_BEGIN
    ADD_METHOD_TO(HealthController::health, "/health", drogon::Get);
    ADD_METHOD_TO(HealthController::aiChat, "/api/ai/chat", drogon::Post, drogon::Get);
    METHOD_LIST_END

    void health(const drogon::HttpRequestPtr& req,
                std::function<void(const drogon::HttpResponsePtr&)>&& callback);

    void aiChat(const drogon::HttpRequestPtr& req,
                std::function<void(const drogon::HttpResponsePtr&)>&& callback);
};
