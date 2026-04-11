#include "service/DefaultServices.h"

#include "db/Database.h"
#include "service/AuthService.h"
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

} // namespace fos::service
