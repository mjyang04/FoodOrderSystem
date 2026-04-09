#include <gtest/gtest.h>
#include "../src/model/Delivery.h"

// ---- Delivery property tests ----
TEST(DeliveryTest, DirectDelivery_Properties)
{
    DirectDelivery d;
    EXPECT_EQ(d.getName(), "Direct Delivery");
    EXPECT_EQ(d.getDeliveryTime(), 30);
    EXPECT_DOUBLE_EQ(d.getFee(), 5.0);
}

TEST(DeliveryTest, StandardDelivery_Properties)
{
    StandardDelivery d;
    EXPECT_EQ(d.getName(), "Standard Delivery");
    EXPECT_EQ(d.getDeliveryTime(), 45);
    EXPECT_DOUBLE_EQ(d.getFee(), 3.0);
}

TEST(DeliveryTest, SaverDelivery_Properties)
{
    SaverDelivery d;
    EXPECT_EQ(d.getName(), "Saver Delivery");
    EXPECT_EQ(d.getDeliveryTime(), 60);
    EXPECT_DOUBLE_EQ(d.getFee(), 2.0);
}

// ---- Fee ordering: Direct > Standard > Saver ----
TEST(DeliveryTest, FeeOrdering)
{
    DirectDelivery direct;
    StandardDelivery standard;
    SaverDelivery saver;

    EXPECT_GT(direct.getFee(), standard.getFee());
    EXPECT_GT(standard.getFee(), saver.getFee());
}

// ---- Time ordering: Direct < Standard < Saver ----
TEST(DeliveryTest, TimeOrdering)
{
    DirectDelivery direct;
    StandardDelivery standard;
    SaverDelivery saver;

    EXPECT_LT(direct.getDeliveryTime(), standard.getDeliveryTime());
    EXPECT_LT(standard.getDeliveryTime(), saver.getDeliveryTime());
}

// ---- Clone tests ----
TEST(DeliveryTest, Clone_Direct)
{
    DirectDelivery original;
    auto cloned = original.clone();
    EXPECT_NE(cloned.get(), &original);
    EXPECT_EQ(cloned->getName(), original.getName());
    EXPECT_DOUBLE_EQ(cloned->getFee(), original.getFee());
}

TEST(DeliveryTest, Clone_Standard)
{
    StandardDelivery original;
    auto cloned = original.clone();
    EXPECT_EQ(cloned->getName(), "Standard Delivery");
}

// ---- Factory function ----
TEST(DeliveryTest, CreateDelivery_Valid)
{
    auto d1 = createDelivery("Direct Delivery");
    EXPECT_NE(d1, nullptr);
    EXPECT_EQ(d1->getName(), "Direct Delivery");

    auto d2 = createDelivery("Standard Delivery");
    EXPECT_EQ(d2->getName(), "Standard Delivery");

    auto d3 = createDelivery("Saver Delivery");
    EXPECT_EQ(d3->getName(), "Saver Delivery");
}

TEST(DeliveryTest, CreateDelivery_InvalidThrows)
{
    EXPECT_THROW(createDelivery("Teleport"), std::runtime_error);
}
