#pragma once

// IRestaurantRepo — pure virtual interface for the subset of Database
// operations that RestaurantService needs. See IUserRepo.h for the broader
// rationale (Sprint 2.5 H-DI: break static coupling so services can be
// unit-tested without a live MySQL).

#include <memory>
#include <string>
#include <vector>

#include "core/Restaurant.h"
#include "model/Food.h"

class IRestaurantRepo
{
public:
    virtual ~IRestaurantRepo() = default;

    virtual bool isConnected() const = 0;

    virtual std::vector<Restaurant> getAllRestaurants() = 0;

    virtual std::vector<std::shared_ptr<Food>> getFoodsByRestaurant(
        int restaurantId, const std::string& cuisineType) = 0;
};
