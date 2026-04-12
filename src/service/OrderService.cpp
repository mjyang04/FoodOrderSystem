#include "service/OrderService.h"

#include <memory>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>

#include "model/Food.h"
#include "service/ErrorCodes.h"
#include "service/OrderStatusMachine.h"

namespace fos::service {

namespace {

// Whitelist of delivery options the HTTP path will accept. The CLI still
// supports more exotic options through the legacy Order class, but the
// Sprint 3 REST surface intentionally restricts itself to this trio so the
// JSON contract is small and unambiguous.
const std::unordered_set<std::string>& deliveryWhitelist()
{
    static const std::unordered_set<std::string> kAllowed{
        "Standard", "Express", "Scheduled"};
    return kAllowed;
}

} // namespace

Result<OrderDto> OrderService::createOrder(const NewOrderDto& request)
{
    if (!orderRepo_.isConnected() || !restaurantRepo_.isConnected())
    {
        return Result<OrderDto>::failure(
            err::kDbUnavailable, "Database is not available");
    }

    // Validation order matters: delivery + shape checks before any repo
    // call so a malformed request is cheap to reject.
    if (deliveryWhitelist().count(request.deliveryOption) == 0)
    {
        return Result<OrderDto>::failure(
            err::kValidationError,
            "Unsupported delivery option: " + request.deliveryOption);
    }

    if (request.items.empty())
    {
        return Result<OrderDto>::failure(
            err::kEmptyOrder, "Order must contain at least one item");
    }

    for (const auto& item : request.items)
    {
        if (item.quantity <= 0)
        {
            return Result<OrderDto>::failure(
                err::kInvalidQuantity,
                "Item quantity must be positive");
        }
    }

    auto restaurantOpt =
        restaurantRepo_.findRestaurantById(request.restaurantId);
    if (!restaurantOpt.has_value())
    {
        return Result<OrderDto>::failure(
            err::kRestaurantNotFound,
            "Restaurant not found: " + std::to_string(request.restaurantId));
    }
    const Restaurant& restaurant = *restaurantOpt;

    // Load the authoritative menu once, then index by food_id so the per-item
    // validation below is O(1). Prices come from the freshly loaded menu —
    // clients never send prices, so we cannot be tricked into under-charging.
    auto foods = restaurantRepo_.getFoodsByRestaurant(
        restaurant.getId(), restaurant.getType());
    std::unordered_map<int, std::shared_ptr<Food>> menu;
    menu.reserve(foods.size());
    for (auto& food : foods)
    {
        if (food) menu.emplace(food->getId(), food);
    }

    OrderDto dto;
    dto.customerId = request.customerId;
    dto.restaurantId = restaurant.getId();
    dto.restaurantName = restaurant.getName();
    dto.deliveryOption = request.deliveryOption;
    dto.status = "Pending";
    dto.totalPrice = 0.0;
    dto.items.reserve(request.items.size());

    for (const auto& item : request.items)
    {
        auto it = menu.find(item.foodId);
        if (it == menu.end())
        {
            return Result<OrderDto>::failure(
                err::kMenuItemMismatch,
                "Food is not on the restaurant's menu: " +
                    std::to_string(item.foodId));
        }
        const auto& food = it->second;

        OrderItemDto line;
        line.foodId = food->getId();
        line.foodName = food->getName();
        line.unitPrice = food->getPrice();
        line.quantity = item.quantity;
        dto.totalPrice += line.unitPrice * static_cast<double>(line.quantity);
        dto.items.push_back(std::move(line));
    }

    auto newId = orderRepo_.createOrder(dto);
    if (!newId.has_value())
    {
        return Result<OrderDto>::failure(
            err::kDbError, "Failed to persist order");
    }

    // Sprint 3 smoke-test finding: the locally-constructed dto has no
    // created_at because only the database can stamp it. Rehydrate from
    // findOrderById so the POST response carries the same shape GET does —
    // otherwise the client has to do a follow-up read just to learn when
    // its own order was created. The extra SELECT is negligible at Sprint 3
    // scale and keeps the response contract consistent.
    //
    // Fallback: if the rehydrate itself fails right after a successful
    // insert (rare — implies a concurrent delete or a broken connection),
    // we still report success with the in-memory DTO. The client loses the
    // timestamp but keeps the order_id and can do a follow-up GET.
    auto persisted = orderRepo_.findOrderById(*newId);
    if (persisted.has_value())
    {
        return Result<OrderDto>::success(std::move(*persisted));
    }
    dto.orderId = *newId;
    return Result<OrderDto>::success(std::move(dto));
}

Result<OrderDto> OrderService::getOrder(int orderId,
                                        int requestingUserId,
                                        bool isAdmin)
{
    if (!orderRepo_.isConnected())
    {
        return Result<OrderDto>::failure(
            err::kDbUnavailable, "Database is not available");
    }

    auto orderOpt = orderRepo_.findOrderById(orderId);
    if (!orderOpt.has_value())
    {
        return Result<OrderDto>::failure(
            err::kOrderNotFound,
            "Order not found: " + std::to_string(orderId));
    }

    // Sprint 3 plan Q1: non-owner non-admin reads collapse into ORDER_NOT_FOUND
    // so the API never leaks the existence of someone else's order. The
    // kForbidden code stays reserved in ErrorCodes.h for future admin-only
    // endpoints where existence leakage is not a concern.
    const OrderDto& order = *orderOpt;
    if (!isAdmin && order.customerId != requestingUserId)
    {
        return Result<OrderDto>::failure(
            err::kOrderNotFound,
            "Order not found: " + std::to_string(orderId));
    }

    return Result<OrderDto>::success(*orderOpt);
}

Result<std::vector<OrderDto>> OrderService::listOrders(int requestingUserId,
                                                       bool isAdmin)
{
    if (!orderRepo_.isConnected())
    {
        return Result<std::vector<OrderDto>>::failure(
            err::kDbUnavailable, "Database is not available");
    }

    if (isAdmin)
    {
        return Result<std::vector<OrderDto>>::success(
            orderRepo_.listAllOrders());
    }
    return Result<std::vector<OrderDto>>::success(
        orderRepo_.listOrdersByCustomer(requestingUserId));
}

Result<OrderDto> OrderService::updateStatus(int orderId,
                                             const std::string& newStatus,
                                             int /*requestingUserId*/,
                                             bool isAdmin)
{
    if (!orderRepo_.isConnected())
    {
        return Result<OrderDto>::failure(
            err::kDbUnavailable, "Database is not available");
    }

    if (!isAdmin)
    {
        return Result<OrderDto>::failure(
            err::kForbidden, "Only admins can change order status");
    }

    auto orderOpt = orderRepo_.findOrderById(orderId);
    if (!orderOpt.has_value())
    {
        return Result<OrderDto>::failure(
            err::kOrderNotFound,
            "Order not found: " + std::to_string(orderId));
    }

    const auto& current = orderOpt->status;
    if (!isValidTransition(current, newStatus))
    {
        return Result<OrderDto>::failure(
            err::kInvalidStatusTransition,
            "Cannot transition from " + current + " to " + newStatus);
    }

    if (!orderRepo_.updateOrderStatus(orderId, newStatus))
    {
        return Result<OrderDto>::failure(err::kDbError, "Failed to update status");
    }

    // Return the updated order.
    auto updated = orderRepo_.findOrderById(orderId);
    if (updated.has_value())
    {
        return Result<OrderDto>::success(std::move(*updated));
    }
    orderOpt->status = newStatus;
    return Result<OrderDto>::success(std::move(*orderOpt));
}

Result<OrderDto> OrderService::rateOrder(int orderId,
                                          double rating,
                                          int requestingUserId,
                                          bool isAdmin)
{
    if (!orderRepo_.isConnected())
    {
        return Result<OrderDto>::failure(
            err::kDbUnavailable, "Database is not available");
    }

    auto orderOpt = orderRepo_.findOrderById(orderId);
    if (!orderOpt.has_value())
    {
        return Result<OrderDto>::failure(
            err::kOrderNotFound,
            "Order not found: " + std::to_string(orderId));
    }

    // Owner check: only the customer who placed the order can rate it.
    if (!isAdmin && orderOpt->customerId != requestingUserId)
    {
        return Result<OrderDto>::failure(
            err::kOrderNotFound,
            "Order not found: " + std::to_string(orderId));
    }

    if (!canRate(orderOpt->status))
    {
        return Result<OrderDto>::failure(
            err::kInvalidStatusTransition,
            "Order must be in Delivered status to rate");
    }

    if (orderOpt->rating > 0.0)
    {
        return Result<OrderDto>::failure(
            err::kOrderAlreadyRated, "Order has already been rated");
    }

    if (!isValidRating(rating))
    {
        return Result<OrderDto>::failure(
            err::kValidationError,
            "Rating must be between 1.0 and 5.0");
    }

    if (!orderRepo_.updateOrderRating(orderId, rating))
    {
        return Result<OrderDto>::failure(err::kDbError, "Failed to save rating");
    }

    auto updated = orderRepo_.findOrderById(orderId);
    if (updated.has_value())
    {
        return Result<OrderDto>::success(std::move(*updated));
    }
    orderOpt->rating = rating;
    return Result<OrderDto>::success(std::move(*orderOpt));
}

} // namespace fos::service
