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
//
// Sprint 2.5 (L-RESULT-ERGONOMICS, L-RESULT-ASSERT) added:
//   - from_error(const ErrorInfo&) to propagate an error across Result<T>
//     instances without re-naming the code/message fields.
//   - [[nodiscard]] on ok() / operator bool() so callers cannot accidentally
//     drop a failure check.
//   - assert(!ok_) in error() to catch buggy callers that try to read the
//     error field on a successful Result.

#include <cassert>
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

    // Propagate an existing error into a Result<T> of a different payload
    // type. Avoids the "failure(other.error().code, other.error().message)"
    // copy-and-paste pattern that showed up in AuthService::registerUser.
    static Result<T> from_error(const ErrorInfo& e)
    {
        return failure(e.code, e.message);
    }

    [[nodiscard]] bool ok() const { return ok_; }
    [[nodiscard]] explicit operator bool() const { return ok_; }

    const T& value() const { return *value_; }
    T& value() { return *value_; }

    const ErrorInfo& error() const
    {
        // Reading error() on a successful Result is a caller bug — it would
        // silently return a default-constructed ErrorInfo and hide the real
        // error protocol. Debug builds trip this assert; release builds fall
        // through to the same empty ErrorInfo for backward compatibility.
        assert(!ok_ && "Result::error() called on a successful Result");
        return error_;
    }

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

    static Result<void> from_error(const ErrorInfo& e)
    {
        return failure(e.code, e.message);
    }

    [[nodiscard]] bool ok() const { return ok_; }
    [[nodiscard]] explicit operator bool() const { return ok_; }

    const ErrorInfo& error() const
    {
        assert(!ok_ && "Result::error() called on a successful Result");
        return error_;
    }

private:
    Result() = default;

    bool ok_ = false;
    ErrorInfo error_;
};

} // namespace fos::service
