// HTTP API entry point for FoodOrderSystem.
//
// This binary (fos_api) launches a Drogon HTTP server that exposes the
// food-ordering business logic over REST. The legacy interactive CLI remains
// available as the separate fos_cli binary.
//
// Configuration (from config file or environment variables):
//   HTTP_HOST       Bind address (default 0.0.0.0)
//   HTTP_PORT       Listen port  (default 8080)
//   HTTP_THREADS    Worker threads (default 4)
//   DB_HOST/USER/PASS/NAME/PORT   MySQL connection (shared with CLI)
//   LOG_LEVEL / LOG_FILE          Logger configuration

#include <drogon/drogon.h>

#include <cstdlib>
#include <iostream>
#include <string>

#include "db/Database.h"
#include "service/JwtService.h"
#include "util/Config.h"
#include "util/Logger.h"

namespace {

void configureLogger(Config& config)
{
    auto& logger = Logger::instance();
    const std::string level = config.getString("LOG_LEVEL", "INFO");
    if (level == "DEBUG")        logger.setLevel(LogLevel::DEBUG);
    else if (level == "WARNING") logger.setLevel(LogLevel::WARNING);
    else if (level == "ERROR")   logger.setLevel(LogLevel::ERROR);
    else                         logger.setLevel(LogLevel::INFO);

    const std::string logFile = config.getString("LOG_FILE", "");
    if (!logFile.empty()) logger.setLogFile(logFile);
}

bool connectDatabase(Config& config)
{
    const std::string dbHost = config.getString("DB_HOST", "127.0.0.1");
    const std::string dbUser = config.getString("DB_USER", "root");
    const std::string dbPass = config.getString("DB_PASS", "");
    const std::string dbName = config.getString("DB_NAME", "food_order_system");
    const auto dbPort = static_cast<unsigned int>(config.getInt("DB_PORT", 3306));

    auto& db = Database::instance();
    if (!db.connect(dbHost, dbUser, dbPass, dbName, dbPort))
    {
        LOG_ERROR("Failed to connect to MySQL database at " << dbHost << ":" << dbPort);
        return false;
    }

    // Intentionally omit dbUser from the INFO line so log aggregation
    // pipelines never persist the DB account name alongside app traces
    // (Sprint 2 security review finding S-H4).
    LOG_INFO("Database connected: " << dbHost << ":" << dbPort
             << "/" << dbName);
    db.initializeSchema();
    return true;
}

} // namespace

int main()
{
    // ---- Load configuration ----
    auto& config = Config::instance();
    config.loadFromFile("config");

    configureLogger(config);

    // ---- Connect to MySQL (shared singleton for Sprint 1) ----
    //
    // NOTE: The current Database singleton holds a single MYSQL* connection and
    // is NOT thread-safe under concurrent HTTP load. For Sprint 1 we pin the
    // Drogon thread pool to 1 worker so we can smoke-test /health end to end.
    // Sprint 2+ will migrate repository code to Drogon's DbClient connection
    // pool (or a mutex-guarded wrapper).
    //
    // We do NOT exit on DB failure: a well-behaved HTTP service should still
    // come up and report its degraded state via /health. This also lets ops
    // tools (Kubernetes readiness probes, docker healthcheck) observe the
    // failure instead of silently restart-looping.
    if (!connectDatabase(config))
    {
        LOG_WARN("Starting in DEGRADED mode: database is unreachable. "
                 "/health will return 503 until the database recovers.");
    }

    // ---- Configure JWT signing ----
    //
    // JWT_SECRET is required for /api/auth/login to issue tokens and for
    // JwtAuthFilter to verify them. We do NOT exit if it's missing — the
    // public read paths (/health, /api/restaurants) still work, and login
    // will return JWT_NOT_CONFIGURED with a clear error message.
    const std::string jwtSecret = config.getString("JWT_SECRET", "");
    const int jwtTtlHours = config.getInt("JWT_TTL_HOURS", 24);
    if (jwtSecret.empty())
    {
        LOG_WARN("JWT_SECRET is empty — /api/auth/login will fail until "
                 "you set JWT_SECRET in config or environment.");
    }
    else
    {
        LOG_INFO("JWT signing configured (HS256, ttl=" << jwtTtlHours << "h)");
    }
    // Sprint 2.5 (L-TTL-WARN): one week is the maximum reasonable operational
    // TTL for a course-project API. Anything longer is almost certainly a
    // misconfiguration (typo in hours vs days) and should at least trip a
    // startup warning. We do NOT refuse to start — deployments that really
    // want a long TTL can ignore the warning.
    constexpr int kJwtTtlWarnHours = 168;
    if (jwtTtlHours > kJwtTtlWarnHours)
    {
        LOG_WARN("JWT_TTL_HOURS=" << jwtTtlHours
                 << " exceeds the " << kJwtTtlWarnHours
                 << "h (1 week) operational cap. Double-check that the unit "
                    "is hours and not days/minutes.");
    }
    fos::service::JwtService::configure(jwtSecret, jwtTtlHours);

    // ---- Configure Drogon listener ----
    const std::string host   = config.getString("HTTP_HOST", "0.0.0.0");
    const int         port   = config.getInt("HTTP_PORT", 8080);
    const int         reqThr = config.getInt("HTTP_THREADS", 1);

    LOG_INFO("Starting fos_api on " << host << ":" << port
             << " with " << reqThr << " worker thread(s)");

    drogon::app()
        .addListener(host, static_cast<uint16_t>(port))
        .setThreadNum(static_cast<size_t>(reqThr))
        .setLogLevel(trantor::Logger::kInfo)
        .setIdleConnectionTimeout(60)
        .registerBeginningAdvice([host, port]() {
            LOG_INFO("fos_api listening on http://" << host << ":" << port);
            LOG_INFO("Try: curl http://localhost:" << port << "/health");
        });

    // Blocks until SIGINT/SIGTERM
    drogon::app().run();

    LOG_INFO("fos_api shutting down");
    Database::instance().disconnect();
    return 0;
}
