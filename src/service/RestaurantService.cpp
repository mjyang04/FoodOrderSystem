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

    // Sprint 2.5 (M-GETMENU): single indexed lookup instead of scanning the
    // whole restaurants table. Sprint 3 will wire orders to menus via this
    // same method, so the O(N) path must not survive into Sprint 3.
    auto target = repo_.findRestaurantById(restaurantId);
    if (!target)
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
