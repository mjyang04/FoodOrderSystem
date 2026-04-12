#pragma once

#include <drogon/HttpController.h>

// AiController — Sprint 4 proxy to the Python fos_ai microservice.
//
// Routes (all gated on JwtAuthFilter):
//   POST /api/ai/parse-order  -> forward to fos_ai POST /ai/parse-order
//   GET  /api/ai/search       -> forward to fos_ai GET  /ai/search
//   GET  /api/ai/recommend    -> forward to fos_ai GET  /ai/recommend
//
// The controller extracts the authenticated userId from JwtAuthFilter,
// forwards it as an X-User-Id header to the Python service (which binds
// to loopback only and trusts this header), and translates upstream
// errors into the standard JSON envelope with AI-specific error codes.
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
};
