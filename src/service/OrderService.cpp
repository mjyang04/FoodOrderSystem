#include "service/OrderService.h"

#include <memory>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>

#include "model/Food.h"
#include "service/ErrorCodes.h"

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

} // namespace fos::service
