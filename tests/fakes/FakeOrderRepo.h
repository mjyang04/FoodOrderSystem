#pragma once

// FakeOrderRepo — in-memory implementation of IOrderRepo for OrderService
// unit tests. Mirrors FakeUserRepo / FakeRestaurantRepo (Sprint 2.5 H-DI
// pattern). The fake does NOT simulate transactions — Sprint 3 pushes
// atomicity down into the concrete Database impl, so in-process tests can
// treat createOrder as a simple vector push.
//
// The fake assigns orderId auto-increment style starting at 1, and stamps
// the status to "Pending" + a fixed createdAt string so tests asserting on
// the full OrderDto shape remain deterministic.

#include <optional>
#include <string>
#include <vector>

#include "db/IOrderRepo.h"
#include "service/OrderDto.h"

namespace fos::tests {

class FakeOrderRepo : public IOrderRepo
{
public:
    bool isConnected() const override { return connected_; }

    std::optional<int> createOrder(
        const fos::service::OrderDto& order) override
    {
        ++createOrderCalls_;
        if (failCreate_) return std::nullopt;

        fos::service::OrderDto stored = order;
        stored.orderId = nextOrderId_++;
        if (stored.status.empty()) stored.status = "Pending";
        if (stored.createdAt.empty()) stored.createdAt = fixedCreatedAt_;
        orders_.push_back(stored);
        return stored.orderId;
    }

    std::optional<fos::service::OrderDto> findOrderById(int orderId) override
    {
        ++findOrderCalls_;
        for (const auto& o : orders_)
        {
            if (o.orderId == orderId) return o;
        }
        return std::nullopt;
    }

    std::vector<fos::service::OrderDto> listOrdersByCustomer(
        int customerId) override
    {
        ++listByCustomerCalls_;
        std::vector<fos::service::OrderDto> out;
        for (const auto& o : orders_)
        {
            if (o.customerId == customerId) out.push_back(o);
        }
        return out;
    }

    std::vector<fos::service::OrderDto> listAllOrders() override
    {
        ++listAllCalls_;
        return orders_;
    }

    bool updateOrderStatus(int orderId, const std::string& newStatus) override
    {
        for (auto& o : orders_)
        {
            if (o.orderId == orderId)
            {
                o.status = newStatus;
                return true;
            }
        }
        return false;
    }

    bool updateOrderRating(int orderId, double rating) override
    {
        for (auto& o : orders_)
        {
            if (o.orderId == orderId)
            {
                o.rating = rating;
                return true;
            }
        }
        return false;
    }

    // ---- Test knobs ----
    void setConnected(bool v) { connected_ = v; }
    void setFailCreate(bool v) { failCreate_ = v; }
    void setFixedCreatedAt(const std::string& s) { fixedCreatedAt_ = s; }

    // ---- Call counters ----
    int createOrderCalls() const { return createOrderCalls_; }
    int findOrderCalls() const { return findOrderCalls_; }
    int listByCustomerCalls() const { return listByCustomerCalls_; }
    int listAllCalls() const { return listAllCalls_; }
    std::size_t orderCount() const { return orders_.size(); }

private:
    bool connected_ = true;
    bool failCreate_ = false;
    int nextOrderId_ = 1;
    std::string fixedCreatedAt_ = "2026-04-12 10:00:00";
    std::vector<fos::service::OrderDto> orders_;

    int createOrderCalls_ = 0;
    int findOrderCalls_ = 0;
    int listByCustomerCalls_ = 0;
    int listAllCalls_ = 0;
};

} // namespace fos::tests
