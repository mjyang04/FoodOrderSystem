#include "Order.h"
#include "../ui/Color.h"
#include <iostream>
#include <iomanip>
#include <stdexcept>

// ---- OrderStatus helpers ----
std::string orderStatusToString(OrderStatus status)
{
    switch (status)
    {
        case OrderStatus::PENDING:    return "Pending";
        case OrderStatus::CONFIRMED:  return "Confirmed";
        case OrderStatus::PREPARING:  return "Preparing";
        case OrderStatus::DELIVERING: return "Delivering";
        case OrderStatus::DELIVERED:  return "Delivered";
        case OrderStatus::CANCELLED:  return "Cancelled";
    }
    return "Unknown";
}

OrderStatus stringToOrderStatus(const std::string& str)
{
    if (str == "Pending")    return OrderStatus::PENDING;
    if (str == "Confirmed")  return OrderStatus::CONFIRMED;
    if (str == "Preparing")  return OrderStatus::PREPARING;
    if (str == "Delivering") return OrderStatus::DELIVERING;
    if (str == "Delivered")  return OrderStatus::DELIVERED;
    if (str == "Cancelled")  return OrderStatus::CANCELLED;
    return OrderStatus::PENDING;
}

// ---- Item management ----
void Order::addItem(std::shared_ptr<Food> food, int quantity,
                    const std::string& instruction, const std::string& preference)
{
    items_.push_back({std::move(food), quantity, instruction, preference});
    recalculateTotal();
}

void Order::deleteItem(int index)
{
    if (index < 0 || index >= static_cast<int>(items_.size()))
    {
        throw std::out_of_range("Invalid item index.");
    }
    items_.erase(items_.begin() + index);
    recalculateTotal();
}

void Order::modifyItem(int index, int quantity,
                       const std::string& instruction, const std::string& preference)
{
    if (index < 0 || index >= static_cast<int>(items_.size()))
    {
        throw std::out_of_range("Invalid item index.");
    }
    items_[index].quantity = quantity;
    items_[index].specialInstruction = instruction;
    items_[index].selectedPreference = preference;
    recalculateTotal();
}

void Order::recalculateTotal()
{
    double subtotal = 0.0;
    for (const auto& item : items_)
    {
        subtotal += item.food->getPrice() * item.quantity;
    }
    totalPrice_ = subtotal * (1.0 - discountPercentage_ / 100.0);
}

void Order::applyDiscount(double percentage)
{
    if (percentage < 0 || percentage > 100)
    {
        throw std::invalid_argument("Discount must be between 0 and 100.");
    }
    discountPercentage_ = percentage;
    recalculateTotal();
}

// ---- Getters ----
int Order::getOrderId() const { return orderId_; }
int Order::getUserId() const { return userId_; }
std::string Order::getUsername() const { return username_; }
std::string Order::getRestaurantName() const { return restaurantName_; }
const std::vector<OrderItem>& Order::getItems() const { return items_; }
double Order::getTotalPrice() const { return totalPrice_; }
double Order::getDiscountPercentage() const { return discountPercentage_; }
const Delivery* Order::getDelivery() const { return delivery_.get(); }
std::string Order::getPaymentMethod() const { return paymentMethod_; }
std::string Order::getRiderName() const { return riderName_; }
std::string Order::getRiderPhone() const { return riderPhone_; }
OrderStatus Order::getStatus() const { return status_; }
std::string Order::getCreatedAt() const { return createdAt_; }
double Order::getRating() const { return rating_; }

double Order::getGrandTotal() const
{
    double total = totalPrice_;
    if (delivery_) total += delivery_->getFee();
    return total;
}

// ---- Setters ----
void Order::setOrderId(int id) { orderId_ = id; }
void Order::setUserId(int id) { userId_ = id; }
void Order::setUsername(const std::string& username) { username_ = username; }
void Order::setRestaurantName(const std::string& name) { restaurantName_ = name; }
void Order::setTotalPrice(double price) { totalPrice_ = price; }
void Order::setDiscountPercentage(double pct) { discountPercentage_ = pct; }
void Order::setDelivery(std::unique_ptr<Delivery> delivery) { delivery_ = std::move(delivery); }
void Order::setPaymentMethod(const std::string& method) { paymentMethod_ = method; }
void Order::setRider(const std::string& name, const std::string& phone) { riderName_ = name; riderPhone_ = phone; }
void Order::setStatus(OrderStatus status) { status_ = status; }
void Order::setCreatedAt(const std::string& dt) { createdAt_ = dt; }
void Order::setRating(double rating) { rating_ = rating; }

// ---- Display ----
void Order::displaySummary(bool showPayment) const
{
    std::cout << Color::BOLD << "Order #" << orderId_
              << "  [" << orderStatusToString(status_) << "]" << Color::RESET << std::endl;
    if (!restaurantName_.empty())
    {
        std::cout << "Restaurant: " << restaurantName_ << std::endl;
    }
    std::cout << std::string(40, '-') << std::endl;

    for (size_t i = 0; i < items_.size(); ++i)
    {
        const auto& item = items_[i];
        std::cout << "  " << i + 1 << ". ";
        item.food->display();
        std::cout << "     Qty: " << item.quantity
                  << "  Subtotal: $" << std::fixed << std::setprecision(2)
                  << item.food->getPrice() * item.quantity << std::endl;
        if (!item.selectedPreference.empty())
            std::cout << "     Preference: " << item.selectedPreference << std::endl;
        if (!item.specialInstruction.empty())
            std::cout << "     Note: " << item.specialInstruction << std::endl;
    }

    std::cout << std::string(40, '-') << std::endl;
    if (discountPercentage_ > 0)
    {
        std::cout << "Discount: " << discountPercentage_ << "%" << std::endl;
    }
    std::cout << "Subtotal: $" << std::fixed << std::setprecision(2) << totalPrice_ << std::endl;

    if (delivery_)
    {
        delivery_->display();
        std::cout << "Delivery Fee: $" << std::fixed << std::setprecision(2) << delivery_->getFee() << std::endl;
        std::cout << Color::BOLD << "Total: $" << std::fixed << std::setprecision(2)
                  << getGrandTotal() << Color::RESET << std::endl;
    }

    if (showPayment && !paymentMethod_.empty())
    {
        std::cout << "Payment: " << paymentMethod_ << std::endl;
    }
    if (!riderName_.empty())
    {
        std::cout << "Rider: " << riderName_ << " (" << riderPhone_ << ")" << std::endl;
    }
    if (rating_ > 0)
    {
        std::cout << "Rating: " << std::fixed << std::setprecision(1) << rating_ << "/5.0" << std::endl;
    }
    if (!createdAt_.empty())
    {
        std::cout << "Date: " << createdAt_ << std::endl;
    }
}

void Order::displayConfirmation() const
{
    std::cout << Color::GREEN << Color::BOLD
              << "========== Order Confirmed ==========" << Color::RESET << std::endl;
    displaySummary(true);
    std::cout << Color::GREEN << Color::BOLD
              << "=====================================" << Color::RESET << std::endl;
}
