#pragma once

// OrderService — Sprint 3 write path for customer orders.
//
// The service takes IOrderRepo& + IRestaurantRepo& in its constructor
// (Sprint 2.5 H-DI pattern), so unit tests can swap the real MySQL for a
// FakeOrderRepo + FakeRestaurantRepo without touching the implementation.
//
// Responsibilities:
//   - Validate the incoming NewOrderDto (non-empty items, positive
//     quantities, known delivery option).
//   - Look up the restaurant (RESTAURANT_NOT_FOUND on miss).
//   - Cross-check every food_id against the restaurant's menu
//     (MENU_ITEM_MISMATCH on miss).
//   - Compute the total from the freshly loaded menu prices (NOT the
//     client-supplied prices — clients never send prices).
//   - Ask the repo to persist atomically.
//
//   - Enforce owner-or-admin authorization for read operations. The
//     caller identity is passed explicitly as (requestingUserId,
//     isAdmin) so the service stays HTTP-layer-agnostic.
//
// Error codes (see service/ErrorCodes.h):
//   DB_UNAVAILABLE         - Either repo reports disconnected
//   VALIDATION_ERROR       - Delivery option not in the whitelist
//   EMPTY_ORDER            - items vector was empty
//   INVALID_QUANTITY       - Some item had quantity <= 0
//   RESTAURANT_NOT_FOUND   - restaurantId does not exist
//   MENU_ITEM_MISMATCH     - A food_id is not on the requested restaurant's menu
//   ORDER_NOT_FOUND        - No such order (OR caller is not the owner — we
//                            deliberately collapse both cases per D1/Q1)
//   DB_ERROR               - Repo accepted the request but failed to persist

#include "db/IOrderRepo.h"
#include "db/IRestaurantRepo.h"
#include "service/OrderDto.h"
#include "service/Result.h"

namespace fos::service {

class OrderService
{
public:
    OrderService(IOrderRepo& orderRepo, IRestaurantRepo& restaurantRepo)
        : orderRepo_(orderRepo), restaurantRepo_(restaurantRepo)
    {}

    // Create a new order on behalf of the authenticated customer.
    // The customerId inside the DTO is trusted — the controller must
    // populate it from AuthContext, not from the request body.
    Result<OrderDto> createOrder(const NewOrderDto& request);

    // Read one order. Customers may read only their own orders; admins
    // may read any order. Policy violations return ORDER_NOT_FOUND (we
    // do not distinguish "missing" from "not yours" — see plan Q1).
    Result<OrderDto> getOrder(int orderId, int requestingUserId, bool isAdmin);

    // List orders visible to the caller. Customers see their own;
    // admins see everything.
    Result<std::vector<OrderDto>> listOrders(int requestingUserId, bool isAdmin);

private:
    IOrderRepo& orderRepo_;
    IRestaurantRepo& restaurantRepo_;
};

} // namespace fos::service
