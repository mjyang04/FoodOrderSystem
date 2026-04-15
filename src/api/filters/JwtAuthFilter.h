#pragma once

#include <drogon/HttpFilter.h>

// JwtAuthFilter — guards protected routes with Bearer JWT authentication.
//
// Expected header:
//   Authorization: Bearer <token>
//
// On success the decoded claims are attached to the request attributes so
// downstream controllers can read them:
//   req->getAttributes()->get<int>("user_id")
//   req->getAttributes()->get<std::string>("username")
//   req->getAttributes()->get<int>("user_role")  // 0=CUSTOMER, 1=ADMIN
//
// On failure the filter short-circuits with a 401 Unauthorized response in
// the shared JSON envelope format.
//
// Sprint 2 wires this filter but does not yet attach it to any route —
// /api/auth/* is explicitly public, and /api/restaurants GETs are too.
// Sprint 3 /api/orders/* will opt in via ADD_METHOD_TO("...", "JwtAuthFilter").
class JwtAuthFilter : public drogon::HttpFilter<JwtAuthFilter>
{
public:
    void doFilter(const drogon::HttpRequestPtr& req,
                  drogon::FilterCallback&& fcb,
                  drogon::FilterChainCallback&& fccb) override;
};
