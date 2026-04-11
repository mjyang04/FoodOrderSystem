#pragma once

// DefaultServices — free-function accessors returning process-wide
// AuthService / RestaurantService singletons wired to the real Database
// instance. HTTP controllers call these so they never need to know about
// repo construction; unit tests bypass these entirely and construct the
// service directly with a fake repo.
//
// Thread safety: the function-local static initializers are guaranteed
// thread-safe by C++11. The services themselves are stateless apart from
// holding a reference to the repo, so they are safe to share across
// Drogon worker threads — the underlying Database synchronises access via
// its recursive_mutex (see H-CONCURRENCY).

namespace fos::service {

class AuthService;
class RestaurantService;

AuthService& defaultAuthService();
RestaurantService& defaultRestaurantService();

} // namespace fos::service
