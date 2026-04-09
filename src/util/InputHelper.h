#ifndef INPUTHELPER_H
#define INPUTHELPER_H

#include <iostream>
#include <string>
#include <limits>
#include <functional>

namespace InputHelper {

// Read an integer with validation and retry
int readInt(const std::string& prompt, int min = std::numeric_limits<int>::min(),
            int max = std::numeric_limits<int>::max());

// Read a double with validation and retry
double readDouble(const std::string& prompt, double min = 0.0,
                  double max = std::numeric_limits<double>::max());

// Read a non-empty string
std::string readString(const std::string& prompt);

// Read a line (can be empty)
std::string readLine(const std::string& prompt);

// Cross-platform clear screen
void clearScreen();

// Pause and wait for user input
void pauseScreen();

} // namespace InputHelper

#endif // INPUTHELPER_H
