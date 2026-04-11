// test_order_service.cpp — Sprint 3 Step 1 (RED).
//
// These tests define the OrderService contract before the implementation
// exists. They are written against FakeOrderRepo + FakeRestaurantRepo so
// the service can be exercised without MySQL, matching the Sprint 2.5
// H-DI exit criterion for AuthService / RestaurantService.
//
// Coverage:
//   createOrder: happy path, empty items, bad quantity, unknown
//                restaurant, food_id not in restaurant, db unavailable,
//                bad delivery option, repo-level create failure.
//   getOrder:    owner happy path, wrong owner -> not_found,
//                admin sees any order, missing id -> not_found,
//                db unavailable.
//   listOrders:  customer sees only own, admin sees all, empty list,
//                db unavailable.

#include <memory>

#include <gtest/gtest.h>

#include "fakes/FakeOrderRepo.h"
#include "fakes/FakeRestaurantRepo.h"
#include "model/Food.h"
#include "service/ErrorCodes.h"
#include "service/OrderService.h"

using fos::service::NewOrderDto;
using fos::service::OrderDto;
using fos::service::OrderService;
using fos::tests::FakeOrderRepo;
using fos::tests::FakeRestaurantRepo;
namespace err = fos::service::err;

namespace {

// Helper: build a populated fake restaurant repo with 2 restaurants and
// a handful of foods whose ids match what the tests rely on.
//
// Restaurant 1 ("Sichuan Delight", Sichuan):
//   food id 10 — Kung Pao Chicken   @ 12.00
//   food id 11 — Mapo Tofu          @  8.00
// Restaurant 2 ("La Dolce Vita", Italian):
//   food id 20 — Pasta              @ 10.00
void seedRestaurants(FakeRestaurantRepo& repo)
{
    Restaurant r1(1, "Sichuan Delight", "Sichuan");
    Restaurant r2(2, "La Dolce Vita", "Italian");
    repo.addRestaurant(r1);
    repo.addRestaurant(r2);

    auto kungPao = std::make_shared<SichuanCuisine>(
        "Kung Pao Chicken", 12.00, "Spicy stir-fried chicken with peanuts");
    kungPao->setId(10);
    auto mapo = std::make_shared<SichuanCuisine>(
        "Mapo Tofu", 8.00, "Spicy tofu with minced meat");
    mapo->setId(11);
    auto pasta = std::make_shared<ItalianCuisine>(
        "Pasta", 10.00, "Italian pasta with tomato sauce");
    pasta->setId(20);

    repo.addFood(1, kungPao);
    repo.addFood(1, mapo);
    repo.addFood(2, pasta);
}

NewOrderDto makeValidRequest(int customerId = 42)
{
    NewOrderDto req;
    req.customerId = customerId;
    req.restaurantId = 1;
    req.items.push_back({10, 2}); // 2x Kung Pao
    req.items.push_back({11, 1}); // 1x Mapo Tofu
    req.deliveryOption = "Standard";
    return req;
}

} // namespace

// ---- createOrder ----------------------------------------------------------

TEST(OrderServiceTest, CreateOrderHappyPathComputesTotalAndPersists)
{
    FakeOrderRepo orderRepo;
    FakeRestaurantRepo restRepo;
    seedRestaurants(restRepo);
    OrderService svc(orderRepo, restRepo);

    auto result = svc.createOrder(makeValidRequest());

    ASSERT_TRUE(result.ok()) << "expected success, got " << result.error().code
                             << ": " << result.error().message;
    const OrderDto& dto = result.value();
    EXPECT_EQ(dto.orderId, 1);
    EXPECT_EQ(dto.customerId, 42);
    EXPECT_EQ(dto.restaurantId, 1);
    EXPECT_EQ(dto.restaurantName, "Sichuan Delight");
    ASSERT_EQ(dto.items.size(), 2u);
    EXPECT_EQ(dto.items[0].foodId, 10);
    EXPECT_EQ(dto.items[0].foodName, "Kung Pao Chicken");
    EXPECT_DOUBLE_EQ(dto.items[0].unitPrice, 12.00);
    EXPECT_EQ(dto.items[0].quantity, 2);
    EXPECT_EQ(dto.items[1].foodId, 11);
    EXPECT_DOUBLE_EQ(dto.items[1].unitPrice, 8.00);
    // Total = 2*12 + 1*8 = 32
    EXPECT_DOUBLE_EQ(dto.totalPrice, 32.00);
    EXPECT_EQ(dto.deliveryOption, "Standard");
    EXPECT_EQ(dto.status, "Pending");
    EXPECT_EQ(orderRepo.createOrderCalls(), 1);
    EXPECT_EQ(orderRepo.orderCount(), 1u);
}

TEST(OrderServiceTest, CreateOrderEmptyItemsReturnsEmptyOrder)
{
    FakeOrderRepo orderRepo;
    FakeRestaurantRepo restRepo;
    seedRestaurants(restRepo);
    OrderService svc(orderRepo, restRepo);

    NewOrderDto req = makeValidRequest();
    req.items.clear();
    auto result = svc.createOrder(req);

    ASSERT_FALSE(result.ok());
    EXPECT_STREQ(result.error().code.c_str(), err::kEmptyOrder);
    EXPECT_EQ(orderRepo.createOrderCalls(), 0);
}

TEST(OrderServiceTest, CreateOrderZeroQuantityReturnsInvalidQuantity)
{
    FakeOrderRepo orderRepo;
    FakeRestaurantRepo restRepo;
    seedRestaurants(restRepo);
    OrderService svc(orderRepo, restRepo);

    NewOrderDto req = makeValidRequest();
    req.items[0].quantity = 0;
    auto result = svc.createOrder(req);

    ASSERT_FALSE(result.ok());
    EXPECT_STREQ(result.error().code.c_str(), err::kInvalidQuantity);
}

TEST(OrderServiceTest, CreateOrderNegativeQuantityReturnsInvalidQuantity)
{
    FakeOrderRepo orderRepo;
    FakeRestaurantRepo restRepo;
    seedRestaurants(restRepo);
    OrderService svc(orderRepo, restRepo);

    NewOrderDto req = makeValidRequest();
    req.items[1].quantity = -3;
    auto result = svc.createOrder(req);

    ASSERT_FALSE(result.ok());
    EXPECT_STREQ(result.error().code.c_str(), err::kInvalidQuantity);
}

TEST(OrderServiceTest, CreateOrderUnknownRestaurantReturnsNotFound)
{
    FakeOrderRepo orderRepo;
    FakeRestaurantRepo restRepo;
    seedRestaurants(restRepo);
    OrderService svc(orderRepo, restRepo);

    NewOrderDto req = makeValidRequest();
    req.restaurantId = 999;
    auto result = svc.createOrder(req);

    ASSERT_FALSE(result.ok());
    EXPECT_STREQ(result.error().code.c_str(), err::kRestaurantNotFound);
    EXPECT_EQ(orderRepo.createOrderCalls(), 0);
}

TEST(OrderServiceTest, CreateOrderFoodNotOnMenuReturnsMismatch)
{
    FakeOrderRepo orderRepo;
    FakeRestaurantRepo restRepo;
    seedRestaurants(restRepo);
    OrderService svc(orderRepo, restRepo);

    NewOrderDto req = makeValidRequest();
    // Food id 20 belongs to restaurant 2, not restaurant 1.
    req.items.push_back({20, 1});
    auto result = svc.createOrder(req);

    ASSERT_FALSE(result.ok());
    EXPECT_STREQ(result.error().code.c_str(), err::kMenuItemMismatch);
    EXPECT_EQ(orderRepo.createOrderCalls(), 0);
}

TEST(OrderServiceTest, CreateOrderBadDeliveryOptionReturnsValidationError)
{
    FakeOrderRepo orderRepo;
    FakeRestaurantRepo restRepo;
    seedRestaurants(restRepo);
    OrderService svc(orderRepo, restRepo);

    NewOrderDto req = makeValidRequest();
    req.deliveryOption = "TeleportationDrone";
    auto result = svc.createOrder(req);

    ASSERT_FALSE(result.ok());
    EXPECT_STREQ(result.error().code.c_str(), err::kValidationError);
}

TEST(OrderServiceTest, CreateOrderDbUnavailableWhenRestaurantRepoDown)
{
    FakeOrderRepo orderRepo;
    FakeRestaurantRepo restRepo;
    seedRestaurants(restRepo);
    restRepo.setConnected(false);
    OrderService svc(orderRepo, restRepo);

    auto result = svc.createOrder(makeValidRequest());

    ASSERT_FALSE(result.ok());
    EXPECT_STREQ(result.error().code.c_str(), err::kDbUnavailable);
}

TEST(OrderServiceTest, CreateOrderDbUnavailableWhenOrderRepoDown)
{
    FakeOrderRepo orderRepo;
    FakeRestaurantRepo restRepo;
    seedRestaurants(restRepo);
    orderRepo.setConnected(false);
    OrderService svc(orderRepo, restRepo);

    auto result = svc.createOrder(makeValidRequest());

    ASSERT_FALSE(result.ok());
    EXPECT_STREQ(result.error().code.c_str(), err::kDbUnavailable);
}

TEST(OrderServiceTest, CreateOrderRepoPersistFailureReturnsDbError)
{
    FakeOrderRepo orderRepo;
    orderRepo.setFailCreate(true);
    FakeRestaurantRepo restRepo;
    seedRestaurants(restRepo);
    OrderService svc(orderRepo, restRepo);

    auto result = svc.createOrder(makeValidRequest());

    ASSERT_FALSE(result.ok());
    EXPECT_STREQ(result.error().code.c_str(), err::kDbError);
}

// ---- getOrder -------------------------------------------------------------

TEST(OrderServiceTest, GetOrderOwnerHappyPath)
{
    FakeOrderRepo orderRepo;
    FakeRestaurantRepo restRepo;
    seedRestaurants(restRepo);
    OrderService svc(orderRepo, restRepo);

    const int orderId =
        svc.createOrder(makeValidRequest(/*customerId=*/42)).value().orderId;

    auto result = svc.getOrder(orderId, /*requestingUserId=*/42, /*isAdmin=*/false);

    ASSERT_TRUE(result.ok());
    EXPECT_EQ(result.value().orderId, orderId);
    EXPECT_EQ(result.value().customerId, 42);
}

TEST(OrderServiceTest, GetOrderWrongOwnerReturnsNotFound)
{
    FakeOrderRepo orderRepo;
    FakeRestaurantRepo restRepo;
    seedRestaurants(restRepo);
    OrderService svc(orderRepo, restRepo);

    const int orderId =
        svc.createOrder(makeValidRequest(/*customerId=*/42)).value().orderId;

    auto result = svc.getOrder(orderId, /*requestingUserId=*/7, /*isAdmin=*/false);

    ASSERT_FALSE(result.ok());
    EXPECT_STREQ(result.error().code.c_str(), err::kOrderNotFound);
}

TEST(OrderServiceTest, GetOrderAdminCanReadAnyOrder)
{
    FakeOrderRepo orderRepo;
    FakeRestaurantRepo restRepo;
    seedRestaurants(restRepo);
    OrderService svc(orderRepo, restRepo);

    const int orderId =
        svc.createOrder(makeValidRequest(/*customerId=*/42)).value().orderId;

    auto result = svc.getOrder(orderId, /*requestingUserId=*/1, /*isAdmin=*/true);

    ASSERT_TRUE(result.ok());
    EXPECT_EQ(result.value().customerId, 42);
}

TEST(OrderServiceTest, GetOrderMissingIdReturnsNotFound)
{
    FakeOrderRepo orderRepo;
    FakeRestaurantRepo restRepo;
    seedRestaurants(restRepo);
    OrderService svc(orderRepo, restRepo);

    auto result = svc.getOrder(/*orderId=*/999, /*requestingUserId=*/42, /*isAdmin=*/false);

    ASSERT_FALSE(result.ok());
    EXPECT_STREQ(result.error().code.c_str(), err::kOrderNotFound);
}

TEST(OrderServiceTest, GetOrderDbUnavailable)
{
    FakeOrderRepo orderRepo;
    orderRepo.setConnected(false);
    FakeRestaurantRepo restRepo;
    OrderService svc(orderRepo, restRepo);

    auto result = svc.getOrder(1, 42, false);

    ASSERT_FALSE(result.ok());
    EXPECT_STREQ(result.error().code.c_str(), err::kDbUnavailable);
}

// ---- listOrders -----------------------------------------------------------

TEST(OrderServiceTest, ListOrdersCustomerSeesOnlyOwn)
{
    FakeOrderRepo orderRepo;
    FakeRestaurantRepo restRepo;
    seedRestaurants(restRepo);
    OrderService svc(orderRepo, restRepo);

    ASSERT_TRUE(svc.createOrder(makeValidRequest(/*customerId=*/42)).ok());
    ASSERT_TRUE(svc.createOrder(makeValidRequest(/*customerId=*/7)).ok());
    ASSERT_TRUE(svc.createOrder(makeValidRequest(/*customerId=*/42)).ok());

    auto result = svc.listOrders(/*requestingUserId=*/42, /*isAdmin=*/false);

    ASSERT_TRUE(result.ok());
    ASSERT_EQ(result.value().size(), 2u);
    for (const auto& o : result.value())
    {
        EXPECT_EQ(o.customerId, 42);
    }
}

TEST(OrderServiceTest, ListOrdersAdminSeesAll)
{
    FakeOrderRepo orderRepo;
    FakeRestaurantRepo restRepo;
    seedRestaurants(restRepo);
    OrderService svc(orderRepo, restRepo);

    ASSERT_TRUE(svc.createOrder(makeValidRequest(/*customerId=*/42)).ok());
    ASSERT_TRUE(svc.createOrder(makeValidRequest(/*customerId=*/7)).ok());
    ASSERT_TRUE(svc.createOrder(makeValidRequest(/*customerId=*/42)).ok());

    auto result = svc.listOrders(/*requestingUserId=*/1, /*isAdmin=*/true);

    ASSERT_TRUE(result.ok());
    EXPECT_EQ(result.value().size(), 3u);
}

TEST(OrderServiceTest, ListOrdersEmptyListForNewCustomer)
{
    FakeOrderRepo orderRepo;
    FakeRestaurantRepo restRepo;
    seedRestaurants(restRepo);
    OrderService svc(orderRepo, restRepo);

    auto result = svc.listOrders(/*requestingUserId=*/42, /*isAdmin=*/false);

    ASSERT_TRUE(result.ok());
    EXPECT_TRUE(result.value().empty());
}

TEST(OrderServiceTest, ListOrdersDbUnavailable)
{
    FakeOrderRepo orderRepo;
    orderRepo.setConnected(false);
    FakeRestaurantRepo restRepo;
    OrderService svc(orderRepo, restRepo);

    auto result = svc.listOrders(42, false);

    ASSERT_FALSE(result.ok());
    EXPECT_STREQ(result.error().code.c_str(), err::kDbUnavailable);
}
