#pragma once

// FakeUserRepo — in-memory implementation of IUserRepo for service-layer
// unit tests. Records calls and stores users in a vector so tests can both
// drive behavior (setConnected) and assert on side effects.
//
// Deliberately simple: no threading, no ordering contract, O(N) lookups.
// This is for unit tests that exercise AuthService logic, not for
// performance benchmarking.

#include <string>
#include <vector>

#include "auth/HashUtil.h"
#include "auth/User.h"
#include "db/IUserRepo.h"

namespace fos::tests {

class FakeUserRepo : public IUserRepo
{
public:
    bool isConnected() const override { return connected_; }

    bool userExists(const std::string& username) override
    {
        ++userExistsCalls_;
        for (const auto& u : users_)
        {
            if (u.getUsername() == username) return true;
        }
        return false;
    }

    bool createUser(const std::string& username,
                    const std::string& password,
                    UserRole role) override
    {
        ++createUserCalls_;
        if (failCreate_) return false;
        // Use the real HashUtil so verifyPassword() will succeed in tests
        // that authenticate a user after registering them.
        const std::string salt = HashUtil::generateSalt();
        const std::string hash = HashUtil::hashPassword(password, salt);
        const int newId = static_cast<int>(users_.size()) + 1;
        users_.emplace_back(newId, username, hash, salt, role);
        return true;
    }

    User findUserByUsername(const std::string& username) override
    {
        ++findUserCalls_;
        for (const auto& u : users_)
        {
            if (u.getUsername() == username) return u;
        }
        return {};
    }

    // ---- Test knobs ----
    void setConnected(bool v) { connected_ = v; }
    void setFailCreate(bool v) { failCreate_ = v; }

    // ---- Call counters (for assertions) ----
    int userExistsCalls() const { return userExistsCalls_; }
    int createUserCalls() const { return createUserCalls_; }
    int findUserCalls() const { return findUserCalls_; }
    std::size_t userCount() const { return users_.size(); }

private:
    bool connected_ = true;
    bool failCreate_ = false;
    std::vector<User> users_;

    int userExistsCalls_ = 0;
    int createUserCalls_ = 0;
    int findUserCalls_ = 0;
};

} // namespace fos::tests
