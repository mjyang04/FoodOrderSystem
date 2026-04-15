#pragma once

#include <drogon/HttpController.h>

// AiController — proxy to the Python fos_ai microservice.
//
// Routes (all gated on JwtAuthFilter):
//   POST /api/ai/parse-order  -> fos_ai POST /ai/parse-order
//   GET  /api/ai/search       -> fos_ai GET  /ai/search
//   GET  /api/ai/recommend    -> fos_ai GET  /ai/recommend
//   POST /api/ai/chat         -> fos_ai POST /ai/chat (Sprint 5)
//   GET  /api/ai/stats        -> fos_ai GET  /ai/stats (Sprint 6 Phase 5,
//                                admin-only, aggregated LLM + cache metrics)
//
// The controller extracts the authenticated userId from JwtAuthFilter,
// forwards it as an X-User-Id header to the Python service (which binds
// to loopback only and trusts this header), and translates upstream
// errors into the standard JSON envelope with AI-specific error codes.
//
// For chat with stream=true, the upstream SSE body is forwarded as
// text/event-stream (buffered pass-through — Drogon HttpClient delivers
// the full body before callback; true server-push streaming is a Sprint 6
// upgrade).
class AiController : public drogon::HttpController<AiController>
{
public:
    METHOD_LIST_BEGIN
    ADD_METHOD_TO(AiController::parseOrder,
                  "/api/ai/parse-order", drogon::Post, "JwtAuthFilter");
    ADD_METHOD_TO(AiController::searchMenu,
                  "/api/ai/search", drogon::Get, "JwtAuthFilter");
    ADD_METHOD_TO(AiController::recommend,
                  "/api/ai/recommend", drogon::Get, "JwtAuthFilter");
    ADD_METHOD_TO(AiController::chat,
                  "/api/ai/chat", drogon::Post, "JwtAuthFilter");
    ADD_METHOD_TO(AiController::stats,
                  "/api/ai/stats", drogon::Get, "JwtAuthFilter");
    METHOD_LIST_END

    void parseOrder(
        const drogon::HttpRequestPtr& req,
        std::function<void(const drogon::HttpResponsePtr&)>&& callback);

    void searchMenu(
        const drogon::HttpRequestPtr& req,
        std::function<void(const drogon::HttpResponsePtr&)>&& callback);

    void recommend(
        const drogon::HttpRequestPtr& req,
        std::function<void(const drogon::HttpResponsePtr&)>&& callback);

    void chat(
        const drogon::HttpRequestPtr& req,
        std::function<void(const drogon::HttpResponsePtr&)>&& callback);

    void stats(
        const drogon::HttpRequestPtr& req,
        std::function<void(const drogon::HttpResponsePtr&)>&& callback);
};
