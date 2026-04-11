#ifndef LOGGER_H
#define LOGGER_H

#include <iostream>
#include <fstream>
#include <string>
#include <ctime>
#include <iomanip>
#include <sstream>
#include <mutex>

// Lightweight logger (no external dependency)
// Supports log levels: DEBUG, INFO, WARNING, ERROR
// Outputs to console (stderr) and optionally to file

enum class LogLevel { DEBUG, INFO, WARNING, ERROR };

class Logger
{
public:
    static Logger& instance()
    {
        static Logger logger;
        return logger;
    }

    void setLevel(LogLevel level) { level_ = level; }

    void setLogFile(const std::string& path)
    {
        std::lock_guard<std::mutex> lock(mutex_);
        if (file_.is_open()) file_.close();
        file_.open(path, std::ios::app);
    }

    void debug(const std::string& msg) { log(LogLevel::DEBUG, msg); }
    void info(const std::string& msg)  { log(LogLevel::INFO, msg); }
    void warn(const std::string& msg)  { log(LogLevel::WARNING, msg); }
    void error(const std::string& msg) { log(LogLevel::ERROR, msg); }

private:
    Logger() = default;
    ~Logger() { if (file_.is_open()) file_.close(); }
    Logger(const Logger&) = delete;
    Logger& operator=(const Logger&) = delete;

    LogLevel level_ = LogLevel::INFO;
    std::ofstream file_;
    std::mutex mutex_;

    void log(LogLevel level, const std::string& msg)
    {
        if (level < level_) return;

        std::lock_guard<std::mutex> lock(mutex_);
        std::string formatted = formatMessage(level, msg);

        std::cerr << formatted << std::endl;
        if (file_.is_open())
        {
            file_ << formatted << std::endl;
        }
    }

    std::string formatMessage(LogLevel level, const std::string& msg) const
    {
        auto now = std::time(nullptr);
        auto* tm = std::localtime(&now);
        std::ostringstream oss;
        oss << std::put_time(tm, "%Y-%m-%d %H:%M:%S")
            << " [" << levelToString(level) << "] " << msg;
        return oss.str();
    }

    static const char* levelToString(LogLevel level)
    {
        switch (level)
        {
            case LogLevel::DEBUG:   return "DEBUG";
            case LogLevel::INFO:    return "INFO ";
            case LogLevel::WARNING: return "WARN ";
            case LogLevel::ERROR:   return "ERROR";
        }
        return "?????";
    }
};

// Convenience macros.
//
// Support both plain-string and streaming usage:
//   LOG_INFO("hello");
//   LOG_INFO("port=" << port << " host=" << host);
//
// The do/while(0) wrapper makes the macro safe in unbraced if/else statements.
//
// Drogon's internal trantor logger also defines LOG_DEBUG/INFO/WARN/ERROR.
// We undef those first so that in translation units which include both
// drogon/drogon.h and this header, our project logger wins unambiguously.
#ifdef LOG_DEBUG
#undef LOG_DEBUG
#endif
#ifdef LOG_INFO
#undef LOG_INFO
#endif
#ifdef LOG_WARN
#undef LOG_WARN
#endif
#ifdef LOG_ERROR
#undef LOG_ERROR
#endif

#define LOG_STREAM_(level, expr)                                          \
    do {                                                                  \
        std::ostringstream _fos_log_oss_;                                 \
        _fos_log_oss_ << expr;                                            \
        Logger::instance().level(_fos_log_oss_.str());                    \
    } while (0)

#define LOG_DEBUG(expr) LOG_STREAM_(debug, expr)
#define LOG_INFO(expr)  LOG_STREAM_(info, expr)
#define LOG_WARN(expr)  LOG_STREAM_(warn, expr)
#define LOG_ERROR(expr) LOG_STREAM_(error, expr)

#endif // LOGGER_H
