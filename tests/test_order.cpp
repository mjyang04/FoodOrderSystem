#include <gtest/gtest.h>
#include "../src/core/Order.h"
#include "../src/model/Food.h"

// ---- OrderStatus conversion tests ----
TEST(OrderStatusTest, ToString)
{
    EXPECT_EQ(orderStatusToString(OrderStatus::PENDING), "Pending");
    EXPECT_EQ(orderStatusToString(OrderStatus::CONFIRMED), "Confirmed");
    EXPECT_EQ(orderStatusToString(OrderStatus::PREPARING), "Preparing");
    EXPECT_EQ(orderStatusToString(OrderStatus::DELIVERING), "Delivering");
    EXPECT_EQ(orderStatusToString(OrderStatus::DELIVERED), "Delivered");
    EXPECT_EQ(orderStatusToString(OrderStatus::CANCELLED), "Cancelled");
}

TEST(OrderStatusTest, FromString)
{
    EXPECT_EQ(stringToOrderStatus("Pending"), OrderStatus::PENDING);
    EXPECT_EQ(stringToOrderStatus("Confirmed"), OrderStatus::CONFIRMED);
    EXPECT_EQ(stringToOrderStatus("Preparing"), OrderStatus::PREPARING);
    EXPECT_EQ(stringToOrderStatus("Delivering"), OrderStatus::DELIVERING);
    EXPECT_EQ(stringToOrderStatus("Delivered"), OrderStatus::DELIVERED);
    EXPECT_EQ(stringToOrderStatus("Cancelled"), OrderStatus::CANCELLED);
}

TEST(OrderStatusTest, FromString_Unknown_DefaultsPending)
{
    EXPECT_EQ(stringToOrderStatus("InvalidStatus"), OrderStatus::PENDING);
    EXPECT_EQ(stringToOrderStatus(""), OrderStatus::PENDING);
}

TEST(OrderStatusTest, Roundtrip)
{
    for (auto status : {OrderStatus::PENDING, OrderStatus::CONFIRMED, OrderStatus::PREPARING,
                        OrderStatus::DELIVERING, OrderStatus::DELIVERED, OrderStatus::CANCELLED})
    {
        EXPECT_EQ(stringToOrderStatus(orderStatusToString(status)), status);
    }
}

// ---- Order tests ----
TEST(OrderTest, DefaultState)
{
    Order order;
    EXPECT_EQ(order.getOrderId(), 0);
    EXPECT_EQ(order.getUserId(), 0);
    EXPECT_EQ(order.getStatus(), OrderStatus::PENDING);
    EXPECT_DOUBLE_EQ(order.getTotalPrice(), 0.0);
    EXPECT_DOUBLE_EQ(order.getRating(), 0.0);
    EXPECT_TRUE(order.getItems().empty());
    EXPECT_EQ(order.getDelivery(), nullptr);
}

TEST(OrderTest, Setters)
{
    Order order;
    order.setOrderId(42);
    order.setUserId(7);
    order.setUsername("testuser");
    order.setRestaurantName("Sichuan Palace");
    order.setStatus(OrderStatus::CONFIRMED);
    order.setPaymentMethod("Credit Card");
    order.setRider("John", "1234567890");
    order.setRating(4.5);
    order.setCreatedAt("2024-01-01 12:00:00");

    EXPECT_EQ(order.getOrderId(), 42);
    EXPECT_EQ(order.getUserId(), 7);
    EXPECT_EQ(order.getUsername(), "testuser");
    EXPECT_EQ(order.getRestaurantName(), "Sichuan Palace");
    EXPECT_EQ(order.getStatus(), OrderStatus::CONFIRMED);
    EXPECT_EQ(order.getPaymentMethod(), "Credit Card");
    EXPECT_EQ(order.getRiderName(), "John");
    EXPECT_EQ(order.getRiderPhone(), "1234567890");
    EXPECT_DOUBLE_EQ(order.getRating(), 4.5);
    EXPECT_EQ(order.getCreatedAt(), "2024-01-01 12:00:00");
}

TEST(OrderTest, AddItemAndRecalculate)
{
    Order order;
    auto food = std::make_shared<SichuanCuisine>("Mapo Tofu", 28.0, "Spicy");
    order.addItem(food, 2, "", "");

    EXPECT_EQ(order.getItems().size(), 1u);
    EXPECT_DOUBLE_EQ(order.getTotalPrice(), 56.0);  // 28 * 2
}

TEST(OrderTest, MultipleItems)
{
    Order order;
    auto food1 = std::make_shared<SichuanCuisine>("Mapo Tofu", 28.0, "");
    auto food2 = std::make_shared<ItalianCuisine>("Pizza", 15.0, "");
    order.addItem(food1, 1, "", "");
    order.addItem(food2, 2, "", "");

    EXPECT_EQ(order.getItems().size(), 2u);
    EXPECT_DOUBLE_EQ(order.getTotalPrice(), 58.0);  // 28 + 15*2
}

TEST(OrderTest, DeleteItem)
{
    Order order;
    auto food1 = std::make_shared<SichuanCuisine>("A", 10.0, "");
    auto food2 = std::make_shared<SichuanCuisine>("B", 20.0, "");
    order.addItem(food1, 1, "", "");
    order.addItem(food2, 1, "", "");

    order.deleteItem(0);
    EXPECT_EQ(order.getItems().size(), 1u);
    EXPECT_DOUBLE_EQ(order.getTotalPrice(), 20.0);
}

TEST(OrderTest, DeleteItem_InvalidIndex)
{
    Order order;
    EXPECT_THROW(order.deleteItem(0), std::out_of_range);
    EXPECT_THROW(order.deleteItem(-1), std::out_of_range);
}

TEST(OrderTest, ModifyItem)
{
    Order order;
    auto food = std::make_shared<SichuanCuisine>("Mapo Tofu", 28.0, "");
    order.addItem(food, 1, "", "");

    order.modifyItem(0, 3, "extra spicy", "hot");
    EXPECT_EQ(order.getItems()[0].quantity, 3);
    EXPECT_EQ(order.getItems()[0].specialInstruction, "extra spicy");
    EXPECT_DOUBLE_EQ(order.getTotalPrice(), 84.0);  // 28 * 3
}

TEST(OrderTest, ApplyDiscount)
{
    Order order;
    auto food = std::make_shared<SichuanCuisine>("Test", 100.0, "");
    order.addItem(food, 1, "", "");

    order.applyDiscount(10.0);  // 10% off
    EXPECT_DOUBLE_EQ(order.getTotalPrice(), 90.0);
    EXPECT_DOUBLE_EQ(order.getDiscountPercentage(), 10.0);
}

TEST(OrderTest, ApplyDiscount_Invalid)
{
    Order order;
    EXPECT_THROW(order.applyDiscount(-1), std::invalid_argument);
    EXPECT_THROW(order.applyDiscount(101), std::invalid_argument);
}

TEST(OrderTest, GrandTotal_WithDelivery)
{
    Order order;
    auto food = std::make_shared<SichuanCuisine>("Test", 50.0, "");
    order.addItem(food, 1, "", "");
    order.setDelivery(std::make_unique<DirectDelivery>());

    EXPECT_DOUBLE_EQ(order.getGrandTotal(), 55.0);  // 50 + 5 (Direct fee)
}

TEST(OrderTest, GrandTotal_WithoutDelivery)
{
    Order order;
    auto food = std::make_shared<SichuanCuisine>("Test", 50.0, "");
    order.addItem(food, 1, "", "");

    EXPECT_DOUBLE_EQ(order.getGrandTotal(), 50.0);
}
