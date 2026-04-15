#include "HealthController.h"

#include "api/JsonEnvelope.h"
#include "db/Database.h"

using drogon::HttpRequestPtr;
using drogon::HttpResponse;
using drogon::HttpResponsePtr;
using drogon::k200OK;
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
    data["version"] = "3.2.0";
    data["service"] = "fos_api";

    auto resp = HttpResponse::newHttpJsonResponse(
        makeEnvelope(dbOk, data, Json::nullValue));
    resp->setStatusCode(dbOk ? k200OK : k503ServiceUnavailable);
    callback(resp);
}
