#pragma once

// IUserRepo — pure virtual interface for the subset of Database operations
// that AuthService needs. Introduced in Sprint 2.5 (H-DI) to break the
// service layer's static coupling to Database::instance(), so that
// AuthService can be unit-tested against an in-memory fake without a live
// MySQL server.
//
// Stability note: this interface is an internal contract between the service
// layer and whatever repository backs it. Adding a method here is a minor
// change (update fakes); removing or renaming is a breaking change.

#include <string>

#include "auth/User.h"

class IUserRepo
{
public:
    virtual ~IUserRepo() = default;

    // Connection probe used by services to short-circuit into DB_UNAVAILABLE
    // before hitting the wire. Must be safe to call regardless of state.
    virtual bool isConnected() const = 0;

    // Returns true if a row with that username already exists.
    virtual bool userExists(const std::string& username) = 0;

    // Creates a new user. Returns true on success. Implementations may throw
    // UserExistsException if the username collides — callers must handle
    // both the false return and the exception path (the current Database
    // implementation does both depending on how it hits the collision).
    virtual bool createUser(const std::string& username,
                            const std::string& password,
                            UserRole role) = 0;

    // Looks up a user by username. Returns a default-constructed User with
    // id == 0 when no row is found. This matches the existing Database
    // contract that Sprint 2 services were built against.
    virtual User findUserByUsername(const std::string& username) = 0;
};
