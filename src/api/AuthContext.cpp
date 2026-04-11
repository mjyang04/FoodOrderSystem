#include "AuthContext.h"

namespace fos::api {

AuthContext readAuthContext(const drogon::HttpRequestPtr& req)
{
    auto attrs = req->getAttributes();
    AuthContext ctx;
    ctx.userId = attrs->get<int>("user_id");
    ctx.username = attrs->get<std::string>("username");
    // The filter writes an int representation so that the on-the-wire
    // attribute shape is stable regardless of whether the enum moves.
    // Convert back here so downstream handlers see a strongly-typed
    // UserRole and can call ctx.isAdmin() instead of comparing to a
    // magic number.
    const int roleInt = attrs->get<int>("user_role");
    ctx.role = (roleInt == static_cast<int>(UserRole::ADMIN))
                   ? UserRole::ADMIN
                   : UserRole::CUSTOMER;
    return ctx;
}

} // namespace fos::api
