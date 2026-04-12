#ifndef DATABASE_H
#define DATABASE_H

#include <mutex>
#include <optional>
#include <string>
#include <vector>
#include <memory>
#include <mysql/mysql.h>
#include "../auth/User.h"
#include "../core/Restaurant.h"
#include "../core/Order.h"
#include "../model/Food.h"
#include "IUserRepo.h"
#include "IRestaurantRepo.h"
#include "IOrderRepo.h"

// Singleton MySQL database manager. Implements IUserRepo, IRestaurantRepo
// and IOrderRepo so the service layer can be constructed against either the
// real singleton or an in-memory fake (see tests/fakes/*). See Sprint 2.5
// H-DI and Sprint 3 in plan/sprint_2_5_hardening.md / plan/sprint_3_orders.md
// for the rationale.
class Database : public IUserRepo, public IRestaurantRepo, public IOrderRepo
{
public:
    static Database& instance();

    // Connection management
    bool connect(const std::string& host, const std::string& user,
                 const std::string& password, const std::string& dbName,
                 unsigned int port = 3306);
    void disconnect();
    bool isConnected() const override;

    // Schema initialization
    void initializeSchema();

    // ---- User operations ----
    bool createUser(const std::string& username, const std::string& password,
                    UserRole role = UserRole::CUSTOMER) override;
    User findUserByUsername(const std::string& username) override;
    bool userExists(const std::string& username) override;
    std::vector<User> getAllUsers();

    // ---- Restaurant operations ----
    std::vector<Restaurant> getAllRestaurants() override;
    std::optional<Restaurant> findRestaurantById(int id) override;
    int addRestaurant(const std::string& name, const std::string& type);
    bool deleteRestaurant(int id);

    // ---- Food operations ----
    std::vector<std::shared_ptr<Food>> getFoodsByRestaurant(int restaurantId,
                                                            const std::string& cuisineType) override;
    int addFood(int restaurantId, const std::string& name, double price,
                const std::string& description, const std::string& preferences);
    bool deleteFood(int id);
    bool updateFoodPrice(int id, double newPrice);

    // ---- Order operations (legacy CLI path) ----
    // Unhide the IOrderRepo::createOrder overload so the legacy overload
    // below doesn't trigger -Woverloaded-virtual.
    using IOrderRepo::createOrder;
    int createOrder(const Order& order);
    void addOrderItems(int orderId, const std::vector<OrderItem>& items);
    std::vector<Order> getOrdersByUser(int userId, const std::vector<Restaurant>& restaurants);
    std::vector<Order> getAllOrders(const std::vector<Restaurant>& restaurants);
    bool updateOrderStatus(int orderId, OrderStatus status);
    bool deleteOrder(int orderId);
    bool rateOrder(int orderId, double rating);

    // ---- Order operations (Sprint 3 DTO / IOrderRepo path) ----
    // These four methods satisfy IOrderRepo and power the HTTP API. They
    // live side-by-side with the legacy createOrder(const Order&) above —
    // the CLI still wants the rich Order model, but the HTTP path only
    // needs the minimal OrderDto surface.
    std::optional<int> createOrder(const fos::service::OrderDto& order) override;
    std::optional<fos::service::OrderDto> findOrderById(int orderId) override;
    std::vector<fos::service::OrderDto> listOrdersByCustomer(int customerId) override;
    std::vector<fos::service::OrderDto> listAllOrders() override;

    // Sprint 5: IOrderRepo overrides for string-based status + rating.
    bool updateOrderStatus(int orderId, const std::string& newStatus) override;
    bool updateOrderRating(int orderId, double rating) override;

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
    mutable std::recursive_mutex mutex_;

    // Helper: execute query and handle errors
    bool executeQuery(const std::string& query);
    MYSQL_RES* executeSelect(const std::string& query);
    std::string escape(const std::string& input);
    MYSQL_STMT* prepareStatement(const std::string& query);
};

#endif // DATABASE_H
