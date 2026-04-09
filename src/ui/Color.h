#ifndef COLOR_H
#define COLOR_H

#include <string>

namespace Color {
    constexpr const char* RESET  = "\033[0m";
    constexpr const char* BOLD   = "\033[1m";
    constexpr const char* RED    = "\033[31m";
    constexpr const char* GREEN  = "\033[32m";
    constexpr const char* YELLOW = "\033[33m";
    constexpr const char* BLUE   = "\033[34m";
    constexpr const char* CYAN   = "\033[36m";
}

#endif // COLOR_H
