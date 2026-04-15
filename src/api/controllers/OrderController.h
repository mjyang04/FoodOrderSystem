#pragma once

#include <drogon/HttpController.h>

// OrderController — Sprint 3 authenticated order endpoints.
//
// Routes (all gated on JwtAuthFilter):
//   POST /api/orders        -> create a new order for the authenticated user
//   GET  /api/orders        -> list orders visible to the caller
//                              (customers see their own; admins see all)
//   GET  /api/orders/{id}   -> fetch a single order (owner-or-admin,
//                              non-owners get ORDER_NOT_FOUND per plan Q1)
//
// The controller is a thin adapter: it unwraps the JSON body / path param,
// overwrites the customerId from AuthContext (NEVER from the request body —
// see plan/sprint_3_orders.md §4 "customerId trust boundary"), and hands off
// to fos::service::defaultOrderService(). All error mapping goes through
// JsonEnvelope::statusForError, so adding a new service error code only
// touches the envelope and not this file.
class OrderController : public drogon::HttpController<OrderController>
{
public:
    METHOD_LIST_BEGIN
    ADD_METHOD_TO(OrderController::createOrder,
                  "/api/orders", drogon::Post, "JwtAuthFilter");
    ADD_METHOD_TO(OrderController::listOrders,
                  "/api/orders", drogon::Get,  "JwtAuthFilter");
    ADD_METHOD_TO(OrderController::getOrder,
                  "/api/orders/{1}", drogon::Get, "JwtAuthFilter");
    ADD_METHOD_TO(OrderController::updateStatus,
                  "/api/orders/{1}/status", drogon::Patch, "JwtAuthFilter");
    ADD_METHOD_TO(OrderController::rateOrder,
                  "/api/orders/{1}/rating", drogon::Patch, "JwtAuthFilter");
    METHOD_LIST_END

    void createOrder(
        const drogon::HttpRequestPtr& req,
        std::function<void(const drogon::HttpResponsePtr&)>&& callback);

    void listOrders(
        const drogon::HttpRequestPtr& req,
        std::function<void(const drogon::HttpResponsePtr&)>&& callback);

    void getOrder(
        const drogon::HttpRequestPtr& req,
        std::function<void(const drogon::HttpResponsePtr&)>&& callback,
        int orderId);

    void updateStatus(
        const drogon::HttpRequestPtr& req,
        std::function<void(const drogon::HttpResponsePtr&)>&& callback,
        int orderId);

    void rateOrder(
        const drogon::HttpRequestPtr& req,
        std::function<void(const drogon::HttpResponsePtr&)>&& callback,
        int orderId);
};
