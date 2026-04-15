// Unit tests for Sprint 5 order status transitions and rating.

#include <gtest/gtest.h>

#include "fakes/FakeOrderRepo.h"
#include "fakes/FakeRestaurantRepo.h"
#include "service/ErrorCodes.h"
#include "service/OrderService.h"
#include "service/OrderStatusMachine.h"

namespace err = fos::service::err;
using fos::service::OrderDto;
using fos::service::OrderService;
using fos::tests::FakeOrderRepo;
using fos::tests::FakeRestaurantRepo;

namespace {

// Helper: seed a fake order with the given status.
void seedOrder(FakeOrderRepo& repo, int orderId, int customerId,
               const std::string& status, double rating = 0.0)
{
    OrderDto dto;
    dto.orderId = orderId;
    dto.customerId = customerId;
    dto.restaurantId = 1;
    dto.status = status;
    dto.rating = rating;
    dto.createdAt = "2026-04-12 10:00:00";
    repo.createOrder(dto);
}

struct StatusFixture : ::testing::Test
{
    FakeOrderRepo orderRepo;
    FakeRestaurantRepo restaurantRepo;
    OrderService service{orderRepo, restaurantRepo};

    void SetUp() override
    {
        seedOrder(orderRepo, 1, 100, "Pending");
        seedOrder(orderRepo, 2, 100, "Confirmed");
        seedOrder(orderRepo, 3, 100, "Preparing");
        seedOrder(orderRepo, 4, 100, "Delivering");
        seedOrder(orderRepo, 5, 100, "Delivered");
        seedOrder(orderRepo, 6, 100, "Cancelled");
        seedOrder(orderRepo, 7, 100, "Delivered", 4.5);  // already rated
    }
};

} // namespace

// ---- Status machine validation ----

TEST(OrderStatusMachine, ValidTransitions)
{
    using fos::service::isValidTransition;
    EXPECT_TRUE(isValidTransition("Pending", "Confirmed"));
    EXPECT_TRUE(isValidTransition("Pending", "Cancelled"));
    EXPECT_TRUE(isValidTransition("Confirmed", "Preparing"));
    EXPECT_TRUE(isValidTransition("Confirmed", "Cancelled"));
    EXPECT_TRUE(isValidTransition("Preparing", "Delivering"));
    EXPECT_TRUE(isValidTransition("Delivering", "Delivered"));
}

TEST(OrderStatusMachine, InvalidTransitions)
{
    using fos::service::isValidTransition;
    EXPECT_FALSE(isValidTransition("Delivered", "Pending"));
    EXPECT_FALSE(isValidTransition("Cancelled", "Confirmed"));
    EXPECT_FALSE(isValidTransition("Preparing", "Pending"));
    EXPECT_FALSE(isValidTransition("Delivering", "Cancelled"));
    EXPECT_FALSE(isValidTransition("Pending", "Delivering"));
    EXPECT_FALSE(isValidTransition("Delivered", "Cancelled"));
}

TEST(OrderStatusMachine, TerminalStatesHaveNoTransitions)
{
    using fos::service::isValidTransition;
    EXPECT_FALSE(isValidTransition("Delivered", "Confirmed"));
    EXPECT_FALSE(isValidTransition("Cancelled", "Pending"));
}

// ---- Service: updateStatus ----

TEST_F(StatusFixture, UpdateStatus_PendingToConfirmed)
{
    auto result = service.updateStatus(1, "Confirmed", 999, true);
    ASSERT_TRUE(result.ok());
    EXPECT_EQ(result.value().status, "Confirmed");
}

TEST_F(StatusFixture, UpdateStatus_ConfirmedToPreparing)
{
    auto result = service.updateStatus(2, "Preparing", 999, true);
    ASSERT_TRUE(result.ok());
    EXPECT_EQ(result.value().status, "Preparing");
}

TEST_F(StatusFixture, UpdateStatus_InvalidTransition)
{
    auto result = service.updateStatus(1, "Delivering", 999, true);
    ASSERT_FALSE(result.ok());
    EXPECT_EQ(result.error().code, err::kInvalidStatusTransition);
}

TEST_F(StatusFixture, UpdateStatus_NonAdminForbidden)
{
    auto result = service.updateStatus(1, "Confirmed", 100, false);
    ASSERT_FALSE(result.ok());
    EXPECT_EQ(result.error().code, err::kForbidden);
}

TEST_F(StatusFixture, UpdateStatus_OrderNotFound)
{
    auto result = service.updateStatus(999, "Confirmed", 999, true);
    ASSERT_FALSE(result.ok());
    EXPECT_EQ(result.error().code, err::kOrderNotFound);
}

TEST_F(StatusFixture, UpdateStatus_CancelFromPending)
{
    auto result = service.updateStatus(1, "Cancelled", 999, true);
    ASSERT_TRUE(result.ok());
    EXPECT_EQ(result.value().status, "Cancelled");
}

TEST_F(StatusFixture, UpdateStatus_CancelFromConfirmed)
{
    auto result = service.updateStatus(2, "Cancelled", 999, true);
    ASSERT_TRUE(result.ok());
    EXPECT_EQ(result.value().status, "Cancelled");
}

TEST_F(StatusFixture, UpdateStatus_CannotCancelFromDelivering)
{
    auto result = service.updateStatus(4, "Cancelled", 999, true);
    ASSERT_FALSE(result.ok());
    EXPECT_EQ(result.error().code, err::kInvalidStatusTransition);
}

// ---- Service: rateOrder ----

TEST_F(StatusFixture, RateOrder_HappyPath)
{
    auto result = service.rateOrder(5, 4.0, 100, false);
    ASSERT_TRUE(result.ok());
    EXPECT_DOUBLE_EQ(result.value().rating, 4.0);
}

TEST_F(StatusFixture, RateOrder_NotDelivered)
{
    auto result = service.rateOrder(1, 4.0, 100, false);
    ASSERT_FALSE(result.ok());
    EXPECT_EQ(result.error().code, err::kInvalidStatusTransition);
}

TEST_F(StatusFixture, RateOrder_AlreadyRated)
{
    auto result = service.rateOrder(7, 3.0, 100, false);
    ASSERT_FALSE(result.ok());
    EXPECT_EQ(result.error().code, err::kOrderAlreadyRated);
}

TEST_F(StatusFixture, RateOrder_InvalidRatingLow)
{
    auto result = service.rateOrder(5, 0.5, 100, false);
    ASSERT_FALSE(result.ok());
    EXPECT_EQ(result.error().code, err::kValidationError);
}

TEST_F(StatusFixture, RateOrder_InvalidRatingHigh)
{
    auto result = service.rateOrder(5, 5.5, 100, false);
    ASSERT_FALSE(result.ok());
    EXPECT_EQ(result.error().code, err::kValidationError);
}

TEST_F(StatusFixture, RateOrder_NotOwner)
{
    auto result = service.rateOrder(5, 4.0, 999, false);
    ASSERT_FALSE(result.ok());
    EXPECT_EQ(result.error().code, err::kOrderNotFound);
}

TEST_F(StatusFixture, RateOrder_AdminCanRate)
{
    auto result = service.rateOrder(5, 4.5, 999, true);
    ASSERT_TRUE(result.ok());
    EXPECT_DOUBLE_EQ(result.value().rating, 4.5);
}
