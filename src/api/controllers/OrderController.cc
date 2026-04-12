#include "OrderController.h"

#include "api/AuthContext.h"
#include "api/JsonBody.h"
#include "api/JsonEnvelope.h"
#include "service/DefaultServices.h"
#include "service/OrderDto.h"
#include "service/OrderService.h"

// Sprint 2.5 (L-CONTROLLER-NS): drop `using namespace drogon;` in favor of
// targeted declarations so this TU's drogon surface is explicit.
using drogon::HttpRequestPtr;
using drogon::HttpResponsePtr;
using drogon::k201Created;
using fos::api::errorResponse;
using fos::api::readAuthContext;
using fos::api::requireIntField;
using fos::api::requireJsonObject;
using fos::api::requireStringField;
using fos::api::statusForError;
using fos::api::successResponse;
using fos::service::defaultOrderService;
using fos::service::NewOrderDto;
using fos::service::NewOrderItemDto;
using fos::service::OrderDto;
using fos::service::OrderItemDto;

namespace {

Json::Value orderItemToJson(const OrderItemDto& item)
{
    Json::Value j;
    j["food_id"] = item.foodId;
    j["food_name"] = item.foodName;
    j["unit_price"] = item.unitPrice;
    j["quantity"] = item.quantity;
    return j;
}

Json::Value orderToJson(const OrderDto& order)
{
    Json::Value j;
    j["order_id"] = order.orderId;
    j["customer_id"] = order.customerId;
    j["restaurant_id"] = order.restaurantId;
    j["restaurant_name"] = order.restaurantName;
    j["total_price"] = order.totalPrice;
    j["delivery_option"] = order.deliveryOption;
    j["status"] = order.status;
    if (order.rating > 0.0) j["rating"] = order.rating;
    j["created_at"] = order.createdAt;

    Json::Value items(Json::arrayValue);
    for (const auto& item : order.items)
    {
        items.append(orderItemToJson(item));
    }
    j["items"] = items;
    return j;
}

// Parse the POST /api/orders JSON body into a NewOrderDto. Returns false on
// any validation failure, having already written an error response via the
// callback. The customerId is NOT populated here — the caller overwrites it
// from AuthContext so there is no path where a body field can masquerade as
// authenticated identity.
bool parseNewOrderBody(
    const HttpRequestPtr& req,
    const std::function<void(const HttpResponsePtr&)>& callback,
    NewOrderDto& out)
{
    auto bodyPtr = requireJsonObject(req, callback);
    if (!bodyPtr) return false;
    const Json::Value& body = *bodyPtr;

    if (!requireIntField(body, "restaurant_id", out.restaurantId, callback))
        return false;
    if (!requireStringField(body, "delivery_option", out.deliveryOption,
                            callback))
        return false;

    if (!body.isMember("items") || !body["items"].isArray())
    {
        callback(errorResponse(
            drogon::k400BadRequest,
            "VALIDATION_ERROR",
            "Field 'items' is required and must be a JSON array."));
        return false;
    }

    const Json::Value& itemsJson = body["items"];
    out.items.reserve(itemsJson.size());
    for (Json::ArrayIndex i = 0; i < itemsJson.size(); ++i)
    {
        const Json::Value& itemJson = itemsJson[i];
        if (!itemJson.isObject())
        {
            callback(errorResponse(
                drogon::k400BadRequest,
                "VALIDATION_ERROR",
                "Each element of 'items' must be a JSON object."));
            return false;
        }
        if (!itemJson.isMember("food_id") || !itemJson["food_id"].isInt() ||
            !itemJson.isMember("quantity") || !itemJson["quantity"].isInt())
        {
            callback(errorResponse(
                drogon::k400BadRequest,
                "VALIDATION_ERROR",
                "Each item must have integer 'food_id' and 'quantity'."));
            return false;
        }
        NewOrderItemDto item;
        item.foodId = itemJson["food_id"].asInt();
        item.quantity = itemJson["quantity"].asInt();
        out.items.push_back(item);
    }
    return true;
}

} // namespace

void OrderController::createOrder(
    const HttpRequestPtr& req,
    std::function<void(const HttpResponsePtr&)>&& callback)
{
    NewOrderDto dto;
    if (!parseNewOrderBody(req, callback, dto))
    {
        return;
    }

    // CRITICAL: the customerId is authoritative from the JWT, NEVER from the
    // request body. JwtAuthFilter already validated the token before this
    // handler runs, so readAuthContext() is guaranteed to be populated.
    // Overwriting here means even if the client sends a customer_id field,
    // it is silently dropped instead of spoofing identity.
    const auto ctx = readAuthContext(req);
    dto.customerId = ctx.userId;

    auto result = defaultOrderService().createOrder(dto);
    if (!result)
    {
        callback(errorResponse(
            statusForError(result.error().code),
            result.error().code,
            result.error().message));
        return;
    }

    callback(successResponse(orderToJson(result.value()), k201Created));
}

void OrderController::listOrders(
    const HttpRequestPtr& req,
    std::function<void(const HttpResponsePtr&)>&& callback)
{
    const auto ctx = readAuthContext(req);

    auto result = defaultOrderService().listOrders(ctx.userId, ctx.isAdmin());
    if (!result)
    {
        callback(errorResponse(
            statusForError(result.error().code),
            result.error().code,
            result.error().message));
        return;
    }

    const auto& orders = result.value();
    Json::Value arr(Json::arrayValue);
    for (const auto& order : orders)
    {
        arr.append(orderToJson(order));
    }

    Json::Value data;
    data["orders"] = arr;
    data["count"] = static_cast<int>(orders.size());
    callback(successResponse(data));
}

void OrderController::getOrder(
    const HttpRequestPtr& req,
    std::function<void(const HttpResponsePtr&)>&& callback,
    int orderId)
{
    const auto ctx = readAuthContext(req);

    auto result =
        defaultOrderService().getOrder(orderId, ctx.userId, ctx.isAdmin());
    if (!result)
    {
        callback(errorResponse(
            statusForError(result.error().code),
            result.error().code,
            result.error().message));
        return;
    }

    callback(successResponse(orderToJson(result.value())));
}

void OrderController::updateStatus(
    const HttpRequestPtr& req,
    std::function<void(const HttpResponsePtr&)>&& callback,
    int orderId)
{
    auto bodyPtr = requireJsonObject(req, callback);
    if (!bodyPtr) return;

    std::string newStatus;
    if (!requireStringField(*bodyPtr, "status", newStatus, callback))
        return;

    const auto ctx = readAuthContext(req);

    auto result = defaultOrderService().updateStatus(
        orderId, newStatus, ctx.userId, ctx.isAdmin());
    if (!result)
    {
        callback(errorResponse(
            statusForError(result.error().code),
            result.error().code,
            result.error().message));
        return;
    }

    callback(successResponse(orderToJson(result.value())));
}

void OrderController::rateOrder(
    const HttpRequestPtr& req,
    std::function<void(const HttpResponsePtr&)>&& callback,
    int orderId)
{
    auto bodyPtr = requireJsonObject(req, callback);
    if (!bodyPtr) return;
    const Json::Value& body = *bodyPtr;

    if (!body.isMember("rating") || !body["rating"].isDouble())
    {
        callback(errorResponse(
            drogon::k400BadRequest,
            "VALIDATION_ERROR",
            "Field 'rating' is required and must be a number."));
        return;
    }
    double rating = body["rating"].asDouble();

    const auto ctx = readAuthContext(req);

    auto result = defaultOrderService().rateOrder(
        orderId, rating, ctx.userId, ctx.isAdmin());
    if (!result)
    {
        callback(errorResponse(
            statusForError(result.error().code),
            result.error().code,
            result.error().message));
        return;
    }

    callback(successResponse(orderToJson(result.value())));
}
