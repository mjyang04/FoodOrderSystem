#ifndef FOODFACTORY_H
#define FOODFACTORY_H

#include "Food.h"
#include <string>
#include <memory>
#include <functional>
#include <unordered_map>
#include <stdexcept>

// Factory + Registry pattern for Food creation
class FoodFactory
{
public:
    using Creator = std::function<std::unique_ptr<Food>(
        const std::string& name, double price, const std::string& desc)>;

    static FoodFactory& instance();

    // Register a cuisine type with its creator function
    void registerType(const std::string& type, Creator creator);

    // Create a Food object by cuisine type
    std::unique_ptr<Food> create(const std::string& type,
                                 const std::string& name,
                                 double price,
                                 const std::string& description) const;

    // Check if a type is registered
    bool hasType(const std::string& type) const;

private:
    FoodFactory();
    std::unordered_map<std::string, Creator> registry_;
    void registerDefaults();
};

#endif // FOODFACTORY_H
