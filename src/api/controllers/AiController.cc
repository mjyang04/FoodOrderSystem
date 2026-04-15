#include "AiController.h"

#include "api/AuthContext.h"
#include "api/JsonBody.h"
#include "api/JsonEnvelope.h"
#include "service/ErrorCodes.h"

#include <drogon/HttpClient.h>

#include <cstdlib>
#include <functional>
#include <string>

// Sprint 2.5 (L-CONTROLLER-NS): targeted using-declarations.
using drogon::HttpClient;
using drogon::HttpMethod;
using drogon::HttpRequest;
using drogon::HttpRequestPtr;
using drogon::HttpResponsePtr;
using drogon::HttpResponse;
using drogon::k200OK;
using drogon::k400BadRequest;
using drogon::k502BadGateway;
using drogon::k503ServiceUnavailable;
using fos::api::errorResponse;
using fos::api::readAuthContext;
using fos::api::successResponse;

namespace err = fos::service::err;

namespace {

// AI service base URL — read once from environment, default to loopback.
const std::string& aiServiceUrl()
{
    static const std::string url = []() {
        const char* env = std::getenv("AI_SERVICE_URL");
        return env ? std::string(env) : std::string("http://127.0.0.1:8000");
    }();
    return url;
}

// Map upstream HTTP status to the appropriate AI error code.
std::string mapUpstreamStatus(int statusCode)
{
    if (statusCode == 422)  return err::kAiLlmRefused;
    if (statusCode == 400)  return err::kAiBadRequest;
    if (statusCode == 429)  return err::kAiUnavailable;
    if (statusCode == 503)  return err::kAiUnavailable;
    if (statusCode >= 500)  return err::kAiUpstreamError;
    if (statusCode >= 400)  return err::kAiBadRequest;
    return "";  // 2xx — no error
}

// Extract the "detail" field from an upstream JSON error body, or fall back
// to a generic message.
std::string extractDetail(const drogon::HttpResponsePtr& resp)
{
    auto bodyPtr = resp->getJsonObject();
    if (bodyPtr && bodyPtr->isMember("detail"))
    {
        return (*bodyPtr)["detail"].asString();
    }
    return "AI service returned status " + std::to_string(resp->statusCode());
}

// Wrap upstream JSON data in the standard envelope and forward to the client.
void forwardUpstreamResponse(
    const drogon::HttpResponsePtr& upstreamResp,
    const std::function<void(const HttpResponsePtr&)>& callback)
{
    auto bodyPtr = upstreamResp->getJsonObject();
    if (!bodyPtr)
    {
        callback(errorResponse(k502BadGateway, err::kAiUpstreamError,
                               "AI service returned non-JSON response"));
        return;
    }
    callback(successResponse(*bodyPtr, k200OK));
}

} // namespace

void AiController::parseOrder(
    const HttpRequestPtr& req,
    std::function<void(const HttpResponsePtr&)>&& callback)
{
    auto ctx = readAuthContext(req);

    // Validate JSON body
    auto bodyPtr = fos::api::requireJsonObject(req, callback);
    if (!bodyPtr) return;

    // Build upstream request
    auto upReq = HttpRequest::newHttpJsonRequest(*bodyPtr);
    upReq->setMethod(HttpMethod::Post);
    upReq->setPath("/ai/parse-order");
    upReq->addHeader("X-User-Id", std::to_string(ctx.userId));

    auto client = HttpClient::newHttpClient(aiServiceUrl());
    // Note: timeout is configured via Drogon's global idle connection timeout

    client->sendRequest(
        upReq,
        [cb = std::move(callback)](drogon::ReqResult result,
                                    const HttpResponsePtr& resp)
        {
            if (result != drogon::ReqResult::Ok)
            {
                cb(errorResponse(k503ServiceUnavailable, err::kAiUnavailable,
                                 "AI service is unreachable"));
                return;
            }

            const int status = static_cast<int>(resp->statusCode());
            const auto errCode = mapUpstreamStatus(status);
            if (!errCode.empty())
            {
                cb(errorResponse(fos::api::statusForError(errCode),
                                 errCode, extractDetail(resp)));
                return;
            }

            forwardUpstreamResponse(resp, cb);
        });
}

void AiController::searchMenu(
    const HttpRequestPtr& req,
    std::function<void(const HttpResponsePtr&)>&& callback)
{
    // Extract query params
    const auto& q = req->getParameter("q");
    if (q.empty())
    {
        callback(errorResponse(k400BadRequest, err::kAiBadRequest,
                               "Query parameter 'q' is required"));
        return;
    }

    std::string limit = req->getParameter("limit");
    if (limit.empty()) limit = "10";

    // Build upstream request
    auto upReq = HttpRequest::newHttpRequest();
    upReq->setMethod(HttpMethod::Get);
    upReq->setPath("/ai/search");
    upReq->setParameter("q", q);
    upReq->setParameter("limit", limit);

    auto client = HttpClient::newHttpClient(aiServiceUrl());
    // Note: timeout is configured via Drogon's global idle connection timeout

    client->sendRequest(
        upReq,
        [cb = std::move(callback)](drogon::ReqResult result,
                                    const HttpResponsePtr& resp)
        {
            if (result != drogon::ReqResult::Ok)
            {
                cb(errorResponse(k503ServiceUnavailable, err::kAiUnavailable,
                                 "AI service is unreachable"));
                return;
            }

            const int status = static_cast<int>(resp->statusCode());
            const auto errCode = mapUpstreamStatus(status);
            if (!errCode.empty())
            {
                cb(errorResponse(fos::api::statusForError(errCode),
                                 errCode, extractDetail(resp)));
                return;
            }

            forwardUpstreamResponse(resp, cb);
        });
}

void AiController::chat(
    const HttpRequestPtr& req,
    std::function<void(const HttpResponsePtr&)>&& callback)
{
    auto ctx = readAuthContext(req);

    auto bodyPtr = fos::api::requireJsonObject(req, callback);
    if (!bodyPtr) return;

    const bool wantStream = bodyPtr->get("stream", false).asBool();

    auto upReq = HttpRequest::newHttpJsonRequest(*bodyPtr);
    upReq->setMethod(HttpMethod::Post);
    upReq->setPath("/ai/chat");
    upReq->addHeader("X-User-Id", std::to_string(ctx.userId));

    auto client = HttpClient::newHttpClient(aiServiceUrl());

    client->sendRequest(
        upReq,
        [cb = std::move(callback), wantStream](drogon::ReqResult result,
                                                const HttpResponsePtr& resp)
        {
            if (result != drogon::ReqResult::Ok)
            {
                cb(errorResponse(k503ServiceUnavailable, err::kAiUnavailable,
                                 "AI service is unreachable"));
                return;
            }

            const int status = static_cast<int>(resp->statusCode());
            const auto errCode = mapUpstreamStatus(status);
            if (!errCode.empty())
            {
                cb(errorResponse(fos::api::statusForError(errCode),
                                 errCode, extractDetail(resp)));
                return;
            }

            if (wantStream)
            {
                // Pass-through SSE body. Drogon's HttpClient delivers the full
                // upstream response before invoking this callback, so this is
                // buffered pass-through (not true server-push streaming). The
                // SSE frame format is preserved so browser EventSource clients
                // still parse events correctly.
                auto out = HttpResponse::newHttpResponse();
                out->setStatusCode(k200OK);
                out->setContentTypeString("text/event-stream");
                out->addHeader("Cache-Control", "no-cache");
                out->addHeader("X-Accel-Buffering", "no");
                out->setBody(std::string(resp->getBody()));
                cb(out);
                return;
            }

            forwardUpstreamResponse(resp, cb);
        });
}

void AiController::recommend(
    const HttpRequestPtr& req,
    std::function<void(const HttpResponsePtr&)>&& callback)
{
    auto ctx = readAuthContext(req);

    std::string limit = req->getParameter("limit");
    if (limit.empty()) limit = "5";

    // Build upstream request
    auto upReq = HttpRequest::newHttpRequest();
    upReq->setMethod(HttpMethod::Get);
    upReq->setPath("/ai/recommend");
    upReq->setParameter("limit", limit);
    upReq->addHeader("X-User-Id", std::to_string(ctx.userId));

    auto client = HttpClient::newHttpClient(aiServiceUrl());
    // Note: timeout is configured via Drogon's global idle connection timeout

    client->sendRequest(
        upReq,
        [cb = std::move(callback)](drogon::ReqResult result,
                                    const HttpResponsePtr& resp)
        {
            if (result != drogon::ReqResult::Ok)
            {
                cb(errorResponse(k503ServiceUnavailable, err::kAiUnavailable,
                                 "AI service is unreachable"));
                return;
            }

            const int status = static_cast<int>(resp->statusCode());
            const auto errCode = mapUpstreamStatus(status);
            if (!errCode.empty())
            {
                cb(errorResponse(fos::api::statusForError(errCode),
                                 errCode, extractDetail(resp)));
                return;
            }

            forwardUpstreamResponse(resp, cb);
        });
}
