#include "service/DefaultServices.h"

#include "db/Database.h"
#include "service/AuthService.h"
#include "service/OrderService.h"
#include "service/RestaurantService.h"

namespace fos::service {

AuthService& defaultAuthService()
{
    // Function-local static: C++11 guarantees thread-safe initialization.
    // The Database singleton is fully constructed the first time this is
    // called — which will be after main() has already called connect().
    static AuthService instance(Database::instance());
    return instance;
}

RestaurantService& defaultRestaurantService()
{
    static RestaurantService instance(Database::instance());
    return instance;
}

OrderService& defaultOrderService()
{
    // Database::instance() implements both IOrderRepo and IRestaurantRepo,
    // so we hand it to OrderService twice — the service only sees the two
    // interface references and never knows it's the same concrete object.
    static OrderService instance(Database::instance(), Database::instance());
    return instance;
}

} // namespace fos::service
