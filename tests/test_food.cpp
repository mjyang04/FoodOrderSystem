#include <gtest/gtest.h>
#include "../src/model/Food.h"
#include "../src/model/FoodFactory.h"

// ---- Food base class tests ----
TEST(FoodTest, SichuanCuisine_Properties)
{
    SichuanCuisine food("Mapo Tofu", 28.0, "Spicy tofu dish");
    EXPECT_EQ(food.getName(), "Mapo Tofu");
    EXPECT_DOUBLE_EQ(food.getPrice(), 28.0);
    EXPECT_EQ(food.getDescription(), "Spicy tofu dish");
    EXPECT_EQ(food.getTypeName(), "Sichuan");
}

TEST(FoodTest, ItalianCuisine_Properties)
{
    ItalianCuisine food("Margherita Pizza", 15.0, "Classic pizza");
    EXPECT_EQ(food.getTypeName(), "Italian");
}

TEST(FoodTest, Clone_CreatesCopy)
{
    SichuanCuisine original("Kung Pao Chicken", 32.0, "Classic dish");
    auto cloned = original.clone();

    EXPECT_NE(cloned.get(), &original);
    EXPECT_EQ(cloned->getName(), original.getName());
    EXPECT_DOUBLE_EQ(cloned->getPrice(), original.getPrice());
    EXPECT_EQ(cloned->getDescription(), original.getDescription());
    EXPECT_EQ(cloned->getTypeName(), original.getTypeName());
}

TEST(FoodTest, SetId)
{
    SichuanCuisine food("Test", 10.0, "");
    EXPECT_EQ(food.getId(), 0);
    food.setId(42);
    EXPECT_EQ(food.getId(), 42);
}

TEST(FoodTest, SetPreferences)
{
    CantoneseCuisine food("Dim Sum", 18.0, "");
    std::vector<std::string> prefs = {"Steamed", "Fried", "Baked"};
    food.setPreferences(prefs);
    EXPECT_EQ(food.getPreferences().size(), 3u);
    EXPECT_EQ(food.getPreferences()[0], "Steamed");
}

// ---- All cuisine types exist ----
TEST(FoodTest, AllCuisineTypes)
{
    ChineseFood chinese("A", 1.0, "");
    EXPECT_EQ(chinese.getTypeName(), "Chinese");

    WesternFood western("B", 2.0, "");
    EXPECT_EQ(western.getTypeName(), "Western");

    ArabicFood arabic("C", 3.0, "");
    EXPECT_EQ(arabic.getTypeName(), "Arabic");

    MexicanFood mexican("D", 4.0, "");
    EXPECT_EQ(mexican.getTypeName(), "Mexican");

    JapaneseFood japanese("E", 5.0, "");
    EXPECT_EQ(japanese.getTypeName(), "Japanese");
}

// ---- FoodFactory tests ----
TEST(FoodFactoryTest, CreateAllRegisteredTypes)
{
    auto& factory = FoodFactory::instance();

    // Factory uses short names matching getTypeName()
    std::vector<std::string> types = {
        "Sichuan", "Cantonese",
        "Italian", "French",
        "Lebanese", "Moroccan",
        "TexMex", "TraditionalMexican",
        "Sushi", "Ramen"
    };

    for (const auto& type : types)
    {
        auto food = factory.create(type, "Test Food", 10.0, "desc");
        EXPECT_NE(food, nullptr) << "Factory failed for type: " << type;
        EXPECT_EQ(food->getTypeName(), type);
    }
}

TEST(FoodFactoryTest, HasType)
{
    auto& factory = FoodFactory::instance();
    EXPECT_TRUE(factory.hasType("Sichuan"));
    EXPECT_TRUE(factory.hasType("Italian"));
    EXPECT_FALSE(factory.hasType("NonExistentCuisine"));
}

TEST(FoodFactoryTest, CreateUnknownTypeThrows)
{
    auto& factory = FoodFactory::instance();
    EXPECT_THROW(factory.create("FakeCuisine", "Test", 10.0, ""),
                 std::runtime_error);
}

TEST(FoodFactoryTest, Singleton)
{
    auto& f1 = FoodFactory::instance();
    auto& f2 = FoodFactory::instance();
    EXPECT_EQ(&f1, &f2);
}
