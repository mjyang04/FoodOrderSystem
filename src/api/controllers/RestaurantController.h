#pragma once

#include <drogon/HttpController.h>

// RestaurantController — public read endpoints for the catalogue.
//
// Routes:
//   GET /api/restaurants              -> { restaurants: [...], count }
//   GET /api/restaurants/{id}/menu    -> { restaurant_id, restaurant_name,
//                                          cuisine_type, foods: [...], count }
//
// These endpoints are intentionally unauthenticated in Sprint 2 — the menu is
// public information. Write endpoints will be added in Sprint 3 behind the
// JwtAuthFilter + admin-role check.
class RestaurantController : public drogon::HttpController<RestaurantController>
{
public:
    METHOD_LIST_BEGIN
    ADD_METHOD_TO(RestaurantController::listAll,
                  "/api/restaurants", drogon::Get);
    ADD_METHOD_TO(RestaurantController::getMenu,
                  "/api/restaurants/{1}/menu", drogon::Get);
    METHOD_LIST_END

    void listAll(
        const drogon::HttpRequestPtr& req,
        std::function<void(const drogon::HttpResponsePtr&)>&& callback);

    void getMenu(
        const drogon::HttpRequestPtr& req,
        std::function<void(const drogon::HttpResponsePtr&)>&& callback,
        int restaurantId);
};
