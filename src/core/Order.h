#ifndef ORDER_H
#define ORDER_H

#include <string>
#include <vector>
#include <memory>
#include "../model/Food.h"
#include "../model/Delivery.h"

// Order status tracking
enum class OrderStatus
{
    PENDING,
    CONFIRMED,
    PREPARING,
    DELIVERING,
    DELIVERED,
    CANCELLED
};

std::string orderStatusToString(OrderStatus status);
OrderStatus stringToOrderStatus(const std::string& str);

// Single item in an order
struct OrderItem
{
    std::shared_ptr<Food> food;
    int quantity;
    std::string specialInstruction;
    std::string selectedPreference;
};

class Order
{
private:
    int orderId_ = 0;
    int userId_ = 0;
    std::string username_;
    std::string restaurantName_;
    std::vector<OrderItem> items_;
    double totalPrice_ = 0.0;
    double discountPercentage_ = 0.0;
    std::unique_ptr<Delivery> delivery_;
    std::string paymentMethod_;
    std::string riderName_;
    std::string riderPhone_;
    OrderStatus status_ = OrderStatus::PENDING;
    std::string createdAt_;
    double rating_ = 0.0;

public:
    Order() = default;

    // Item management
    void addItem(std::shared_ptr<Food> food, int quantity,
                 const std::string& instruction, const std::string& preference);
    void deleteItem(int index);
    void modifyItem(int index, int quantity,
                    const std::string& instruction, const std::string& preference);

    // Pricing
    void recalculateTotal();
    void applyDiscount(double percentage);

    // Getters
    int getOrderId() const;
    int getUserId() const;
    std::string getUsername() const;
    std::string getRestaurantName() const;
    const std::vector<OrderItem>& getItems() const;
    double getTotalPrice() const;
    double getDiscountPercentage() const;
    const Delivery* getDelivery() const;
    std::string getPaymentMethod() const;
    std::string getRiderName() const;
    std::string getRiderPhone() const;
    OrderStatus getStatus() const;
    std::string getCreatedAt() const;
    double getRating() const;

    // Setters
    void setOrderId(int id);
    void setUserId(int id);
    void setUsername(const std::string& username);
    void setRestaurantName(const std::string& name);
    void setTotalPrice(double price);
    void setDiscountPercentage(double pct);
    void setDelivery(std::unique_ptr<Delivery> delivery);
    void setPaymentMethod(const std::string& method);
    void setRider(const std::string& name, const std::string& phone);
    void setStatus(OrderStatus status);
    void setCreatedAt(const std::string& dt);
    void setRating(double rating);

    // Display
    void displaySummary(bool showPayment = true) const;
    void displayConfirmation() const;

    // Get total including delivery
    double getGrandTotal() const;
};

#endif // ORDER_H
