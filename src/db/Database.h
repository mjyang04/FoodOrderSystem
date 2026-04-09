#ifndef DATABASE_H
#define DATABASE_H

#include <string>
#include <vector>
#include <memory>
#include <mysql/mysql.h>
#include "../auth/User.h"
#include "../core/Restaurant.h"
#include "../core/Order.h"
#include "../model/Food.h"

// Singleton MySQL database manager
class Database
{
public:
    static Database& instance();

    // Connection management
    bool connect(const std::string& host, const std::string& user,
                 const std::string& password, const std::string& dbName,
                 unsigned int port = 3306);
    void disconnect();
    bool isConnected() const;

    // Schema initialization
    void initializeSchema();

    // ---- User operations ----
    bool createUser(const std::string& username, const std::string& password,
                    UserRole role = UserRole::CUSTOMER);
    User findUserByUsername(const std::string& username);
    bool userExists(const std::string& username);
    std::vector<User> getAllUsers();

    // ---- Restaurant operations ----
    std::vector<Restaurant> getAllRestaurants();
    int addRestaurant(const std::string& name, const std::string& type);
    bool deleteRestaurant(int id);

    // ---- Food operations ----
    std::vector<std::shared_ptr<Food>> getFoodsByRestaurant(int restaurantId,
                                                            const std::string& cuisineType);
    int addFood(int restaurantId, const std::string& name, double price,
                const std::string& description, const std::string& preferences);
    bool deleteFood(int id);
    bool updateFoodPrice(int id, double newPrice);

    // ---- Order operations ----
    int createOrder(const Order& order);
    void addOrderItems(int orderId, const std::vector<OrderItem>& items);
    std::vector<Order> getOrdersByUser(int userId, const std::vector<Restaurant>& restaurants);
    std::vector<Order> getAllOrders(const std::vector<Restaurant>& restaurants);
    bool updateOrderStatus(int orderId, OrderStatus status);
    bool deleteOrder(int orderId);
    bool rateOrder(int orderId, double rating);

    // ---- Rider operations ----
    struct Rider { int id; std::string name; std::string phone; };
    std::vector<Rider> getAllRiders();
    int addRider(const std::string& name, const std::string& phone);
    bool deleteRider(int id);
    Rider getRandomRider();

    // ---- Analytics ----
    double getTotalSpentByUser(int userId);
    std::string getFavoriteRestaurant(int userId);
    int getTotalOrdersByUser(int userId);

    // ---- Search & Filter ----
    std::vector<Restaurant> searchRestaurants(const std::string& keyword);
    std::vector<std::shared_ptr<Food>> searchFoodByPriceRange(double minPrice, double maxPrice);

private:
    Database() = default;
    ~Database();
    Database(const Database&) = delete;
    Database& operator=(const Database&) = delete;

    MYSQL* conn_ = nullptr;

    // Helper: execute query and handle errors
    bool executeQuery(const std::string& query);
    MYSQL_RES* executeSelect(const std::string& query);
    std::string escape(const std::string& input);
};

#endif // DATABASE_H
