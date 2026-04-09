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

// Convenience macros
#define LOG_DEBUG(msg) Logger::instance().debug(msg)
#define LOG_INFO(msg)  Logger::instance().info(msg)
#define LOG_WARN(msg)  Logger::instance().warn(msg)
#define LOG_ERROR(msg) Logger::instance().error(msg)

#endif // LOGGER_H
