#pragma once

// RestaurantService — read-only catalogue for restaurants and their menus.
//
// This is the read path shared by the HTTP API, the legacy CLI, and the
// future LLM recommendation layer. Mutations (add/delete restaurant, edit
// menu) remain on the legacy admin flows in Sprint 2 — they land in
// Sprint 3 alongside the order endpoints.
//
// Sprint 2.5 (H-DI) turned this into an instance class that takes an
// IRestaurantRepo& in its constructor so it can be unit-tested against an
// in-memory fake. For the production HTTP path, call
// DefaultServices::defaultRestaurantService().
//
// Error codes:
//   DB_UNAVAILABLE         - Underlying repo is not connected
//   RESTAURANT_NOT_FOUND   - No row matches the requested id

#include <memory>
#include <string>
#include <vector>

#include "core/Restaurant.h"
#include "db/IRestaurantRepo.h"
#include "model/Food.h"
#include "service/Result.h"

namespace fos::service {

struct MenuView
{
    int restaurantId = 0;
    std::string restaurantName;
    std::string cuisineType;
    std::vector<std::shared_ptr<Food>> foods;
};

class RestaurantService
{
public:
    explicit RestaurantService(IRestaurantRepo& repo) : repo_(repo) {}

    // Returns every restaurant row. An empty vector is a valid result
    // (no restaurants yet); callers should not treat it as an error.
    std::vector<Restaurant> listAll();

    // Returns the full menu (restaurant metadata + foods) for a single id.
    Result<MenuView> getMenu(int restaurantId);

private:
    IRestaurantRepo& repo_;
};

} // namespace fos::service
