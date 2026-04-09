#ifndef HASHUTIL_H
#define HASHUTIL_H

#include <string>
#include <sstream>
#include <iomanip>
#include <cstdint>
#include <cstring>
#include <array>

namespace HashUtil {

// SHA-256 implementation (no external dependency)
std::string sha256(const std::string& input);

// Hash a password with a salt
std::string hashPassword(const std::string& password, const std::string& salt);

// Generate a simple random salt
std::string generateSalt(int length = 16);

} // namespace HashUtil

#endif // HASHUTIL_H
