#include "FoodFactory.h"

FoodFactory& FoodFactory::instance()
{
    static FoodFactory factory;
    return factory;
}

FoodFactory::FoodFactory()
{
    registerDefaults();
}

void FoodFactory::registerType(const std::string& type, Creator creator)
{
    registry_[type] = std::move(creator);
}

std::unique_ptr<Food> FoodFactory::create(const std::string& type,
                                          const std::string& name,
                                          double price,
                                          const std::string& description) const
{
    auto it = registry_.find(type);
    if (it == registry_.end())
    {
        throw std::runtime_error("Unknown cuisine type: " + type);
    }
    return it->second(name, price, description);
}

bool FoodFactory::hasType(const std::string& type) const
{
    return registry_.count(type) > 0;
}

void FoodFactory::registerDefaults()
{
    registerType("Sichuan", [](const std::string& n, double p, const std::string& d) {
        return std::make_unique<SichuanCuisine>(n, p, d);
    });
    registerType("Cantonese", [](const std::string& n, double p, const std::string& d) {
        return std::make_unique<CantoneseCuisine>(n, p, d);
    });
    registerType("Italian", [](const std::string& n, double p, const std::string& d) {
        return std::make_unique<ItalianCuisine>(n, p, d);
    });
    registerType("French", [](const std::string& n, double p, const std::string& d) {
        return std::make_unique<FrenchCuisine>(n, p, d);
    });
    registerType("Lebanese", [](const std::string& n, double p, const std::string& d) {
        return std::make_unique<LebaneseCuisine>(n, p, d);
    });
    registerType("Moroccan", [](const std::string& n, double p, const std::string& d) {
        return std::make_unique<MoroccanCuisine>(n, p, d);
    });
    registerType("TexMex", [](const std::string& n, double p, const std::string& d) {
        return std::make_unique<TexMexCuisine>(n, p, d);
    });
    registerType("TraditionalMexican", [](const std::string& n, double p, const std::string& d) {
        return std::make_unique<TraditionalMexicanCuisine>(n, p, d);
    });
    registerType("Sushi", [](const std::string& n, double p, const std::string& d) {
        return std::make_unique<SushiCuisine>(n, p, d);
    });
    registerType("Ramen", [](const std::string& n, double p, const std::string& d) {
        return std::make_unique<RamenCuisine>(n, p, d);
    });
}
