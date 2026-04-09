#ifndef CONFIG_H
#define CONFIG_H

#include <string>
#include <fstream>
#include <unordered_map>
#include <cstdlib>

// Simple key=value config file parser
// Priority: environment variable > config file > default value
class Config
{
public:
    static Config& instance()
    {
        static Config cfg;
        return cfg;
    }

    // Load config from a file (key=value format, # for comments)
    bool loadFromFile(const std::string& path)
    {
        std::ifstream file(path);
        if (!file.is_open()) return false;

        std::string line;
        while (std::getline(file, line))
        {
            // Skip comments and empty lines
            if (line.empty() || line[0] == '#') continue;

            auto pos = line.find('=');
            if (pos == std::string::npos) continue;

            std::string key = trim(line.substr(0, pos));
            std::string value = trim(line.substr(pos + 1));

            // Remove surrounding quotes
            if (value.size() >= 2 &&
                ((value.front() == '"' && value.back() == '"') ||
                 (value.front() == '\'' && value.back() == '\'')))
            {
                value = value.substr(1, value.size() - 2);
            }

            values_[key] = value;
        }
        return true;
    }

    // Get string value (env var takes priority)
    std::string getString(const std::string& key, const std::string& defaultVal = "") const
    {
        // 1. Check environment variable
        const char* envVal = std::getenv(key.c_str());
        if (envVal) return envVal;

        // 2. Check config file values
        auto it = values_.find(key);
        if (it != values_.end()) return it->second;

        // 3. Return default
        return defaultVal;
    }

    int getInt(const std::string& key, int defaultVal = 0) const
    {
        std::string val = getString(key, "");
        if (val.empty()) return defaultVal;
        try { return std::stoi(val); }
        catch (...) { return defaultVal; }
    }

    double getDouble(const std::string& key, double defaultVal = 0.0) const
    {
        std::string val = getString(key, "");
        if (val.empty()) return defaultVal;
        try { return std::stod(val); }
        catch (...) { return defaultVal; }
    }

    bool getBool(const std::string& key, bool defaultVal = false) const
    {
        std::string val = getString(key, "");
        if (val.empty()) return defaultVal;
        return val == "true" || val == "1" || val == "yes";
    }

    Config() = default;

private:
    std::unordered_map<std::string, std::string> values_;

    static std::string trim(const std::string& str)
    {
        size_t start = str.find_first_not_of(" \t\r\n");
        if (start == std::string::npos) return "";
        size_t end = str.find_last_not_of(" \t\r\n");
        return str.substr(start, end - start + 1);
    }
};

#endif // CONFIG_H
