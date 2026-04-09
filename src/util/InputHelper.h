#ifndef INPUTHELPER_H
#define INPUTHELPER_H

#include <string>
#include <limits>

namespace InputHelper {

// Read an integer with validation and retry
int readInt(const std::string& prompt, int min = std::numeric_limits<int>::min(),
            int max = std::numeric_limits<int>::max());

// Read a double with validation and retry
double readDouble(const std::string& prompt, double min = 0.0,
                  double max = std::numeric_limits<double>::max());

// Read a non-empty string
std::string readString(const std::string& prompt);

// Cross-platform clear screen
void clearScreen();

} // namespace InputHelper

#endif // INPUTHELPER_H
