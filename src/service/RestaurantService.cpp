#include "service/RestaurantService.h"

#include <string>

#include "db/Database.h"
#include "service/ErrorCodes.h"

namespace fos::service {

std::vector<Restaurant> RestaurantService::listAll()
{
    auto& db = Database::instance();
    if (!db.isConnected())
    {
        return {};
    }
    return db.getAllRestaurants();
}

Result<MenuView> RestaurantService::getMenu(int restaurantId)
{
    auto& db = Database::instance();
    if (!db.isConnected())
    {
        return Result<MenuView>::failure(
            err::kDbUnavailable,
            "Database is not connected.");
    }

    const auto restaurants = db.getAllRestaurants();
    const Restaurant* target = nullptr;
    for (const auto& r : restaurants)
    {
        if (r.getId() == restaurantId)
        {
            target = &r;
            break;
        }
    }
    if (target == nullptr)
    {
        return Result<MenuView>::failure(
            err::kRestaurantNotFound,
            "No restaurant with id " + std::to_string(restaurantId) + ".");
    }

    MenuView view;
    view.restaurantId = target->getId();
    view.restaurantName = target->getName();
    view.cuisineType = target->getType();
    view.foods = db.getFoodsByRestaurant(target->getId(), target->getType());
    return Result<MenuView>::success(std::move(view));
}

} // namespace fos::service
