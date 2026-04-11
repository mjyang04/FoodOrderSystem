#include "RestaurantController.h"

#include "api/JsonEnvelope.h"
#include "core/Restaurant.h"
#include "model/Food.h"
#include "service/DefaultServices.h"
#include "service/RestaurantService.h"

using namespace drogon;
using fos::api::errorResponse;
using fos::api::statusForError;
using fos::api::successResponse;
using fos::service::defaultRestaurantService;

namespace {

Json::Value restaurantToJson(const Restaurant& r)
{
    Json::Value j;
    j["id"] = r.getId();
    j["name"] = r.getName();
    j["cuisine_type"] = r.getType();
    return j;
}

Json::Value foodToJson(const Food& f)
{
    Json::Value j;
    j["id"] = f.getId();
    j["name"] = f.getName();
    j["price"] = f.getPrice();
    j["description"] = f.getDescription();
    j["type"] = f.getTypeName();

    Json::Value prefs(Json::arrayValue);
    for (const auto& p : f.getPreferences())
    {
        prefs.append(p);
    }
    j["preferences"] = prefs;
    return j;
}

} // namespace

void RestaurantController::listAll(
    const HttpRequestPtr& req,
    std::function<void(const HttpResponsePtr&)>&& callback)
{
    (void)req;

    const auto restaurants = defaultRestaurantService().listAll();

    Json::Value arr(Json::arrayValue);
    for (const auto& r : restaurants)
    {
        arr.append(restaurantToJson(r));
    }

    Json::Value data;
    data["restaurants"] = arr;
    data["count"] = static_cast<int>(restaurants.size());
    callback(successResponse(data));
}

void RestaurantController::getMenu(
    const HttpRequestPtr& req,
    std::function<void(const HttpResponsePtr&)>&& callback,
    int restaurantId)
{
    (void)req;

    auto result = defaultRestaurantService().getMenu(restaurantId);
    if (!result)
    {
        callback(errorResponse(
            statusForError(result.error().code),
            result.error().code,
            result.error().message));
        return;
    }

    const auto& menu = result.value();
    Json::Value foods(Json::arrayValue);
    for (const auto& food : menu.foods)
    {
        if (food)
        {
            foods.append(foodToJson(*food));
        }
    }

    Json::Value data;
    data["restaurant_id"] = menu.restaurantId;
    data["restaurant_name"] = menu.restaurantName;
    data["cuisine_type"] = menu.cuisineType;
    data["foods"] = foods;
    data["count"] = static_cast<int>(menu.foods.size());
    callback(successResponse(data));
}
