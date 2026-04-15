#pragma once

// OrderDto — plain-data shapes for the HTTP order path.
//
// Sprint 3 introduces these structs so OrderService can speak the same
// language as the Drogon controllers and the IOrderRepo without dragging
// along the legacy CLI Order class (which carries unique_ptr<Delivery>,
// shared_ptr<Food> menu references, and interactive display methods).
//
// Sprint 3 (D1 in plan/sprint_3_orders.md): the DTOs live in the service
// layer on purpose — they are the stable contract for both HTTP handlers
// and unit-test fakes. The legacy core/Order class stays untouched and
// remains the CLI's domain model.
//
// All fields are defaulted so "empty DTO" is a valid constructable value,
// which keeps the Result<OrderDto> fallback behavior safe (the [[nodiscard]]
// + assert guard on Result<T>::error() is the real misuse trap).

#include <string>
#include <vector>

namespace fos::service {

// Request shape for POST /api/orders.
struct NewOrderItemDto
{
    int foodId = 0;
    int quantity = 0;
};

struct NewOrderDto
{
    int customerId = 0;                    // Filled from AuthContext in the controller.
    int restaurantId = 0;
    std::vector<NewOrderItemDto> items;
    std::string deliveryOption;            // "Standard" | "Express" | "Scheduled"
};

// Response shape for GET /api/orders[/:id] and the success payload of
// POST /api/orders. Prices are captured at creation time — the Dto carries
// the snapshot that was committed to the database, not the live menu price.
struct OrderItemDto
{
    int foodId = 0;
    std::string foodName;
    double unitPrice = 0.0;
    int quantity = 0;
};

struct OrderDto
{
    int orderId = 0;
    int customerId = 0;
    int restaurantId = 0;
    std::string restaurantName;
    std::vector<OrderItemDto> items;
    double totalPrice = 0.0;
    std::string deliveryOption;
    std::string status;                    // OrderStatus as lowercase string.
    double rating = 0.0;                   // 0.0 means unrated; valid range [1.0, 5.0].
    std::string createdAt;                 // ISO timestamp (MySQL format is fine for Sprint 3).
};

} // namespace fos::service
