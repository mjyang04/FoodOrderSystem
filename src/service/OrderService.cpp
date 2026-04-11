#include "service/OrderService.h"

#include "service/ErrorCodes.h"

namespace fos::service {

// Sprint 3 Step 1 (RED): stub implementations so the test file compiles.
// Step 2 (GREEN) fills these in to pass every test case.

Result<OrderDto> OrderService::createOrder(const NewOrderDto& /*request*/)
{
    return Result<OrderDto>::failure(err::kDbError, "OrderService::createOrder not implemented");
}

Result<OrderDto> OrderService::getOrder(int /*orderId*/,
                                        int /*requestingUserId*/,
                                        bool /*isAdmin*/)
{
    return Result<OrderDto>::failure(err::kDbError, "OrderService::getOrder not implemented");
}

Result<std::vector<OrderDto>> OrderService::listOrders(int /*requestingUserId*/,
                                                       bool /*isAdmin*/)
{
    return Result<std::vector<OrderDto>>::failure(err::kDbError, "OrderService::listOrders not implemented");
}

} // namespace fos::service
