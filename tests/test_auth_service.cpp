// test_auth_service.cpp — first service-layer unit tests.
//
// These are the Sprint 2.5 H-DI exit criterion: AuthService must be
// testable WITHOUT a live MySQL server. Built on FakeUserRepo, not
// Database::instance().

#include <gtest/gtest.h>

#include "fakes/FakeUserRepo.h"
#include "service/AuthService.h"
#include "service/ErrorCodes.h"

using fos::service::AuthService;
using fos::tests::FakeUserRepo;
namespace err = fos::service::err;

TEST(AuthServiceTest, RegisterUserHappyPath)
{
    FakeUserRepo repo;
    AuthService svc(repo);

    auto result = svc.registerUser("alice", "secret1", UserRole::CUSTOMER);

    ASSERT_TRUE(result.ok()) << "expected success, got " << result.error().code
                             << ": " << result.error().message;
    EXPECT_EQ(result.value(), 1);
    EXPECT_EQ(repo.userCount(), 1u);
    EXPECT_GE(repo.userExistsCalls(), 1);
    EXPECT_GE(repo.createUserCalls(), 1);
}

TEST(AuthServiceTest, AuthenticateWrongPasswordReturnsInvalidCredentials)
{
    FakeUserRepo repo;
    AuthService svc(repo);

    ASSERT_TRUE(svc.registerUser("bob", "correct-password").ok());

    auto result = svc.authenticate("bob", "wrong-password");

    ASSERT_FALSE(result.ok());
    EXPECT_EQ(result.error().code, err::kInvalidCredentials);
}

TEST(AuthServiceTest, RegisterOnDisconnectedRepoReturnsDbUnavailable)
{
    FakeUserRepo repo;
    repo.setConnected(false);
    AuthService svc(repo);

    auto result = svc.registerUser("carol", "secret1");

    ASSERT_FALSE(result.ok());
    EXPECT_EQ(result.error().code, err::kDbUnavailable);
    EXPECT_EQ(repo.userCount(), 0u)
        << "must not touch the repo after connection probe fails";
    EXPECT_EQ(repo.createUserCalls(), 0);
}
