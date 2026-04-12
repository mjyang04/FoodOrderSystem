#pragma once

// IOrderRepo — pure virtual interface for the persistence operations that
// OrderService needs. Mirrors IUserRepo / IRestaurantRepo (Sprint 2.5 H-DI
// pattern): the service layer takes the interface by reference so unit
// tests can swap in an in-memory fake without touching MySQL.
//
// Sprint 3 (D2 in plan/sprint_3_orders.md): createOrder is a single atomic
// operation. The concrete Database implementation wraps the orders +
// order_items inserts in a MySQL transaction so the service never has to
// think about partial commits. FakeOrderRepo can ignore atomicity because
// it stores everything in-process anyway.

#include <optional>
#include <vector>

#include "service/OrderDto.h"

class IOrderRepo
{
public:
    virtual ~IOrderRepo() = default;

    virtual bool isConnected() const = 0;

    // Persist an order atomically. The input DTO carries pre-validated
    // items with unit prices already resolved by the service layer; the
    // repo only needs to write rows. On success, returns the new order id.
    // On failure, returns std::nullopt — the service maps that to DB_ERROR.
    virtual std::optional<int> createOrder(
        const fos::service::OrderDto& order) = 0;

    // Look up a single order by primary key. Returns std::nullopt when no
    // row matches. The service layer is responsible for authorization
    // (owner-vs-admin): the repo has no idea who is asking.
    virtual std::optional<fos::service::OrderDto> findOrderById(int orderId) = 0;

    // Return every order for a given customer, ordered newest-first.
    // Capped server-side (L-PAGINATION pattern) so the transport never
    // walks an unbounded result set.
    virtual std::vector<fos::service::OrderDto> listOrdersByCustomer(
        int customerId) = 0;

    // Admin path: return every order in the system, ordered newest-first,
    // capped. The service decides who may call this.
    virtual std::vector<fos::service::OrderDto> listAllOrders() = 0;

    // Sprint 5: update order status. Returns true on success.
    virtual bool updateOrderStatus(int orderId, const std::string& newStatus) = 0;

    // Sprint 5: set order rating. Returns true on success.
    virtual bool updateOrderRating(int orderId, double rating) = 0;
};
