#pragma once

// FakeRestaurantRepo — in-memory implementation of IRestaurantRepo for
// OrderService unit tests. Mirrors FakeUserRepo (Sprint 2.5 H-DI): tests
// seed restaurants + menus directly, then assert on service-layer
// behavior without needing a real MySQL.
//
// OrderService asks this fake two questions: "does restaurant N exist"
// (findRestaurantById) and "what foods belong to restaurant N"
// (getFoodsByRestaurant). That is exactly the Sprint 2.5 M-GETMENU
// contract, so the fake stays deliberately thin.

#include <memory>
#include <optional>
#include <string>
#include <unordered_map>
#include <vector>

#include "core/Restaurant.h"
#include "db/IRestaurantRepo.h"
#include "model/Food.h"

namespace fos::tests {

class FakeRestaurantRepo : public IRestaurantRepo
{
public:
    bool isConnected() const override { return connected_; }

    std::vector<Restaurant> getAllRestaurants() override
    {
        ++getAllCalls_;
        std::vector<Restaurant> out;
        out.reserve(restaurants_.size());
        for (const auto& [id, r] : restaurants_) out.push_back(r);
        return out;
    }

    std::optional<Restaurant> findRestaurantById(int id) override
    {
        ++findByIdCalls_;
        auto it = restaurants_.find(id);
        if (it == restaurants_.end()) return std::nullopt;
        return it->second;
    }

    std::vector<std::shared_ptr<Food>> getFoodsByRestaurant(
        int restaurantId, const std::string& /*cuisineType*/) override
    {
        ++getFoodsCalls_;
        auto it = menus_.find(restaurantId);
        if (it == menus_.end()) return {};
        return it->second;
    }

    // ---- Seeding helpers ----
    void addRestaurant(const Restaurant& r)
    {
        restaurants_[r.getId()] = r;
    }

    void addFood(int restaurantId, std::shared_ptr<Food> food)
    {
        menus_[restaurantId].push_back(std::move(food));
    }

    void setConnected(bool v) { connected_ = v; }

    // ---- Call counters ----
    int getAllCalls() const { return getAllCalls_; }
    int findByIdCalls() const { return findByIdCalls_; }
    int getFoodsCalls() const { return getFoodsCalls_; }

private:
    bool connected_ = true;
    std::unordered_map<int, Restaurant> restaurants_;
    std::unordered_map<int, std::vector<std::shared_ptr<Food>>> menus_;

    int getAllCalls_ = 0;
    int findByIdCalls_ = 0;
    int getFoodsCalls_ = 0;
};

} // namespace fos::tests
