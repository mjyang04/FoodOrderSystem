#pragma once

// Result<T> — lightweight success/error wrapper for service-layer APIs.
//
// Design goals:
//   1. No exceptions cross the HTTP boundary — controllers translate errors
//      into HTTP status codes by inspecting Result::error().code.
//   2. Error codes are machine-readable strings (e.g. "USER_EXISTS") so both
//      the REST envelope and the future LLM function-calling layer can act on
//      them programmatically.
//   3. Value-only success with an optional T payload. A dedicated Result<void>
//      specialisation is provided for operations that return no data.
//
// Inspired by std::expected (C++23), but C++17-compatible.

#include <optional>
#include <string>
#include <utility>

namespace fos::service {

struct ErrorInfo
{
    std::string code;     // Machine-readable code, e.g. "USER_EXISTS"
    std::string message;  // Human-readable message for clients
};

template <typename T>
class Result
{
public:
    static Result<T> success(T value)
    {
        Result r;
        r.ok_ = true;
        r.value_ = std::move(value);
        return r;
    }

    static Result<T> failure(std::string code, std::string message)
    {
        Result r;
        r.ok_ = false;
        r.error_ = ErrorInfo{std::move(code), std::move(message)};
        return r;
    }

    bool ok() const { return ok_; }
    explicit operator bool() const { return ok_; }

    const T& value() const { return *value_; }
    T& value() { return *value_; }

    const ErrorInfo& error() const { return error_; }

private:
    Result() = default;

    bool ok_ = false;
    std::optional<T> value_;
    ErrorInfo error_;
};

// Specialisation for operations returning no payload.
template <>
class Result<void>
{
public:
    static Result<void> success()
    {
        Result r;
        r.ok_ = true;
        return r;
    }

    static Result<void> failure(std::string code, std::string message)
    {
        Result r;
        r.ok_ = false;
        r.error_ = ErrorInfo{std::move(code), std::move(message)};
        return r;
    }

    bool ok() const { return ok_; }
    explicit operator bool() const { return ok_; }

    const ErrorInfo& error() const { return error_; }

private:
    Result() = default;

    bool ok_ = false;
    ErrorInfo error_;
};

} // namespace fos::service
