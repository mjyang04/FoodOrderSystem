#pragma once

// OrderStatusMachine — Sprint 5 valid status transition map.
//
// Valid transitions:
//   Pending    -> Confirmed, Cancelled
//   Confirmed  -> Preparing, Cancelled
//   Preparing  -> Delivering
//   Delivering -> Delivered
//   Delivered  -> (terminal)
//   Cancelled  -> (terminal)
//
// Rating is allowed only on Delivered orders, range [1.0, 5.0].

#include <string>
#include <unordered_map>
#include <unordered_set>

namespace fos::service {

inline bool isValidTransition(const std::string& from, const std::string& to)
{
    static const std::unordered_map<std::string, std::unordered_set<std::string>>
        kTransitions{
            {"Pending",    {"Confirmed", "Cancelled"}},
            {"Confirmed",  {"Preparing", "Cancelled"}},
            {"Preparing",  {"Delivering"}},
            {"Delivering", {"Delivered"}},
        };

    auto it = kTransitions.find(from);
    if (it == kTransitions.end()) return false;
    return it->second.count(to) > 0;
}

inline bool canRate(const std::string& status)
{
    return status == "Delivered";
}

inline bool isValidRating(double rating)
{
    return rating >= 1.0 && rating <= 5.0;
}

} // namespace fos::service
