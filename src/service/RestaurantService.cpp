#include "service/RestaurantService.h"

#include <string>

#include "service/ErrorCodes.h"

namespace fos::service {

std::vector<Restaurant> RestaurantService::listAll()
{
    if (!repo_.isConnected())
    {
        return {};
    }
    return repo_.getAllRestaurants();
}

Result<MenuView> RestaurantService::getMenu(int restaurantId)
{
    if (!repo_.isConnected())
    {
        return Result<MenuView>::failure(
            err::kDbUnavailable,
            "Database is not connected.");
    }

    const auto restaurants = repo_.getAllRestaurants();
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
    view.foods = repo_.getFoodsByRestaurant(target->getId(), target->getType());
    return Result<MenuView>::success(std::move(view));
}

} // namespace fos::service
