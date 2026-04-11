#pragma once

// ErrorCodes — canonical string constants for service-layer Result<T> errors.
//
// These codes are part of the machine-readable contract between the service
// layer, the HTTP JSON envelope, and (in Sprint 5) the LLM function-calling
// layer. Keeping them in one header prevents duplicate literals from drifting
// and gives the future AI layer a single place to introspect.
//
// Stability: once a code is added here, treat it as a public API and only
// append new codes. Do not rename or repurpose existing ones.

namespace fos::service::err {

// ---- Validation ----
inline constexpr const char* kValidationError    = "VALIDATION_ERROR";

// ---- Authentication ----
inline constexpr const char* kUserExists         = "USER_EXISTS";
inline constexpr const char* kInvalidCredentials = "INVALID_CREDENTIALS";

// ---- JWT ----
inline constexpr const char* kJwtNotConfigured   = "JWT_NOT_CONFIGURED";
inline constexpr const char* kMissingToken       = "MISSING_TOKEN";
inline constexpr const char* kInvalidToken       = "INVALID_TOKEN";

// ---- Domain lookups ----
inline constexpr const char* kRestaurantNotFound = "RESTAURANT_NOT_FOUND";
inline constexpr const char* kOrderNotFound      = "ORDER_NOT_FOUND";

// ---- Order creation ----
// Sprint 3 (plan/sprint_3_orders.md §4). EMPTY_ORDER and INVALID_QUANTITY
// are split out from kValidationError so clients can localise them
// separately; MENU_ITEM_MISMATCH is the cross-restaurant guard.
inline constexpr const char* kEmptyOrder         = "EMPTY_ORDER";
inline constexpr const char* kInvalidQuantity    = "INVALID_QUANTITY";
inline constexpr const char* kMenuItemMismatch   = "MENU_ITEM_MISMATCH";

// ---- Authorization ----
// Reserved for future admin-only endpoints. Sprint 3 currently collapses
// "not your order" into kOrderNotFound (404) per OWASP guidance, but a
// dedicated 403 code stays in the vocabulary so Sprint 4+ can distinguish
// the two cases without re-drafting the protocol.
inline constexpr const char* kForbidden          = "FORBIDDEN";

// ---- Database ----
inline constexpr const char* kDbUnavailable      = "DB_UNAVAILABLE";
inline constexpr const char* kDbError            = "DB_ERROR";

} // namespace fos::service::err
