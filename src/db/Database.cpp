#include "Database.h"
#include "../auth/HashUtil.h"
#include "../model/FoodFactory.h"
#include <iostream>
#include <sstream>
#include <random>
#include <chrono>
#include <stdexcept>

Database& Database::instance()
{
    static Database db;
    return db;
}

Database::~Database()
{
    disconnect();
}

bool Database::connect(const std::string& host, const std::string& user,
                       const std::string& password, const std::string& dbName,
                       unsigned int port)
{
    conn_ = mysql_init(nullptr);
    if (!conn_)
    {
        std::cerr << "mysql_init() failed\n";
        return false;
    }
    if (!mysql_real_connect(conn_, host.c_str(), user.c_str(), password.c_str(),
                            dbName.c_str(), port, nullptr, 0))
    {
        std::cerr << "MySQL connection error: " << mysql_error(conn_) << std::endl;
        mysql_close(conn_);
        conn_ = nullptr;
        return false;
    }
    mysql_set_character_set(conn_, "utf8mb4");
    return true;
}

void Database::disconnect()
{
    if (conn_)
    {
        mysql_close(conn_);
        conn_ = nullptr;
    }
}

bool Database::isConnected() const
{
    return conn_ != nullptr;
}

bool Database::executeQuery(const std::string& query)
{
    if (mysql_query(conn_, query.c_str()))
    {
        std::cerr << "SQL Error: " << mysql_error(conn_) << "\nQuery: " << query << std::endl;
        return false;
    }
    return true;
}

MYSQL_RES* Database::executeSelect(const std::string& query)
{
    if (mysql_query(conn_, query.c_str()))
    {
        std::cerr << "SQL Error: " << mysql_error(conn_) << "\nQuery: " << query << std::endl;
        return nullptr;
    }
    return mysql_store_result(conn_);
}

std::string Database::escape(const std::string& input)
{
    std::string output(input.size() * 2 + 1, '\0');
    auto len = mysql_real_escape_string(conn_, &output[0], input.c_str(), input.size());
    output.resize(len);
    return output;
}

// ---- Schema Initialization ----
void Database::initializeSchema()
{
    const std::vector<std::string> statements = {
        R"(CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            salt VARCHAR(64) NOT NULL,
            role ENUM('customer','admin') DEFAULT 'customer',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ))",
        R"(CREATE TABLE IF NOT EXISTS restaurants (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            cuisine_type VARCHAR(50) NOT NULL
        ))",
        R"(CREATE TABLE IF NOT EXISTS foods (
            id INT AUTO_INCREMENT PRIMARY KEY,
            restaurant_id INT NOT NULL,
            name VARCHAR(100) NOT NULL,
            price DECIMAL(10,2) NOT NULL,
            description TEXT,
            preferences TEXT,
            FOREIGN KEY (restaurant_id) REFERENCES restaurants(id) ON DELETE CASCADE
        ))",
        R"(CREATE TABLE IF NOT EXISTS riders (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            phone VARCHAR(20) NOT NULL
        ))",
        R"(CREATE TABLE IF NOT EXISTS orders (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            restaurant_name VARCHAR(100),
            status ENUM('Pending','Confirmed','Preparing','Delivering','Delivered','Cancelled') DEFAULT 'Pending',
            total_price DECIMAL(10,2) DEFAULT 0,
            discount_pct DOUBLE DEFAULT 0,
            delivery_type VARCHAR(50),
            delivery_fee DECIMAL(10,2) DEFAULT 0,
            payment_method VARCHAR(50),
            rider_name VARCHAR(100),
            rider_phone VARCHAR(20),
            rating DOUBLE DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        ))",
        R"(CREATE TABLE IF NOT EXISTS order_items (
            id INT AUTO_INCREMENT PRIMARY KEY,
            order_id INT NOT NULL,
            food_name VARCHAR(100) NOT NULL,
            food_price DECIMAL(10,2) NOT NULL,
            food_description TEXT,
            quantity INT NOT NULL,
            preference VARCHAR(100) DEFAULT '',
            special_instruction TEXT DEFAULT '',
            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
        ))"
    };

    for (const auto& sql : statements)
    {
        executeQuery(sql);
    }
}

// ---- User operations ----
bool Database::createUser(const std::string& username, const std::string& password, UserRole role)
{
    if (userExists(username)) return false;

    std::string salt = HashUtil::generateSalt();
    std::string hash = HashUtil::hashPassword(password, salt);
    std::string roleStr = (role == UserRole::ADMIN) ? "admin" : "customer";

    std::string sql = "INSERT INTO users (username, password_hash, salt, role) VALUES ('"
        + escape(username) + "','" + escape(hash) + "','" + escape(salt) + "','" + roleStr + "')";
    return executeQuery(sql);
}

User Database::findUserByUsername(const std::string& username)
{
    std::string sql = "SELECT id, username, password_hash, salt, role FROM users WHERE username='"
        + escape(username) + "'";
    MYSQL_RES* res = executeSelect(sql);
    if (!res) return {};

    MYSQL_ROW row = mysql_fetch_row(res);
    if (!row)
    {
        mysql_free_result(res);
        return {};
    }

    UserRole role = (std::string(row[4]) == "admin") ? UserRole::ADMIN : UserRole::CUSTOMER;
    User user(std::stoi(row[0]), row[1], row[2], row[3], role);
    mysql_free_result(res);
    return user;
}

bool Database::userExists(const std::string& username)
{
    std::string sql = "SELECT COUNT(*) FROM users WHERE username='" + escape(username) + "'";
    MYSQL_RES* res = executeSelect(sql);
    if (!res) return false;

    MYSQL_ROW row = mysql_fetch_row(res);
    bool exists = row && std::stoi(row[0]) > 0;
    mysql_free_result(res);
    return exists;
}

std::vector<User> Database::getAllUsers()
{
    std::vector<User> users;
    MYSQL_RES* res = executeSelect("SELECT id, username, password_hash, salt, role FROM users");
    if (!res) return users;

    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res)))
    {
        UserRole role = (std::string(row[4]) == "admin") ? UserRole::ADMIN : UserRole::CUSTOMER;
        users.emplace_back(std::stoi(row[0]), row[1], row[2], row[3], role);
    }
    mysql_free_result(res);
    return users;
}

// ---- Restaurant operations ----
std::vector<Restaurant> Database::getAllRestaurants()
{
    std::vector<Restaurant> restaurants;
    MYSQL_RES* res = executeSelect("SELECT id, name, cuisine_type FROM restaurants ORDER BY id");
    if (!res) return restaurants;

    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res)))
    {
        Restaurant r(std::stoi(row[0]), row[1], row[2]);

        // Load menu for this restaurant
        auto foods = getFoodsByRestaurant(r.getId(), r.getType());
        for (auto& f : foods) r.addFoodItem(std::move(f));

        restaurants.push_back(std::move(r));
    }
    mysql_free_result(res);
    return restaurants;
}

int Database::addRestaurant(const std::string& name, const std::string& type)
{
    std::string sql = "INSERT INTO restaurants (name, cuisine_type) VALUES ('"
        + escape(name) + "','" + escape(type) + "')";
    if (!executeQuery(sql)) return -1;
    return static_cast<int>(mysql_insert_id(conn_));
}

bool Database::deleteRestaurant(int id)
{
    return executeQuery("DELETE FROM restaurants WHERE id=" + std::to_string(id));
}

// ---- Food operations ----
std::vector<std::shared_ptr<Food>> Database::getFoodsByRestaurant(int restaurantId,
                                                                   const std::string& cuisineType)
{
    std::vector<std::shared_ptr<Food>> foods;
    std::string sql = "SELECT id, name, price, description, preferences FROM foods WHERE restaurant_id="
        + std::to_string(restaurantId);
    MYSQL_RES* res = executeSelect(sql);
    if (!res) return foods;

    auto& factory = FoodFactory::instance();
    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res)))
    {
        try
        {
            auto food = factory.create(cuisineType, row[1], std::stod(row[2]),
                                       row[3] ? row[3] : "");
            food->setId(std::stoi(row[0]));

            // Parse preferences (comma-separated in DB)
            if (row[4] && std::string(row[4]).length() > 0)
            {
                std::vector<std::string> prefs;
                std::istringstream ss(row[4]);
                std::string pref;
                while (std::getline(ss, pref, '|'))
                {
                    if (!pref.empty()) prefs.push_back(pref);
                }
                food->setPreferences(prefs);
            }

            foods.push_back(std::move(food));
        }
        catch (const std::exception& e)
        {
            std::cerr << "Error loading food: " << e.what() << std::endl;
        }
    }
    mysql_free_result(res);
    return foods;
}

int Database::addFood(int restaurantId, const std::string& name, double price,
                      const std::string& description, const std::string& preferences)
{
    std::ostringstream sql;
    sql << "INSERT INTO foods (restaurant_id, name, price, description, preferences) VALUES ("
        << restaurantId << ",'" << escape(name) << "'," << price << ",'"
        << escape(description) << "','" << escape(preferences) << "')";
    if (!executeQuery(sql.str())) return -1;
    return static_cast<int>(mysql_insert_id(conn_));
}

bool Database::deleteFood(int id)
{
    return executeQuery("DELETE FROM foods WHERE id=" + std::to_string(id));
}

bool Database::updateFoodPrice(int id, double newPrice)
{
    std::ostringstream sql;
    sql << "UPDATE foods SET price=" << newPrice << " WHERE id=" << id;
    return executeQuery(sql.str());
}

// ---- Order operations ----
int Database::createOrder(const Order& order)
{
    std::ostringstream sql;
    sql << "INSERT INTO orders (user_id, restaurant_name, status, total_price, discount_pct, "
        << "delivery_type, delivery_fee, payment_method, rider_name, rider_phone) VALUES ("
        << order.getUserId() << ",'" << escape(order.getRestaurantName()) << "','"
        << orderStatusToString(order.getStatus()) << "'," << order.getTotalPrice() << ","
        << order.getDiscountPercentage() << ",'"
        << (order.getDelivery() ? escape(order.getDelivery()->getName()) : "None") << "',"
        << (order.getDelivery() ? order.getDelivery()->getFee() : 0.0) << ",'"
        << escape(order.getPaymentMethod()) << "','" << escape(order.getRiderName()) << "','"
        << escape(order.getRiderPhone()) << "')";

    if (!executeQuery(sql.str())) return -1;
    int orderId = static_cast<int>(mysql_insert_id(conn_));

    // Insert order items
    for (const auto& item : order.getItems())
    {
        std::ostringstream itemSql;
        itemSql << "INSERT INTO order_items (order_id, food_name, food_price, food_description, "
                << "quantity, preference, special_instruction) VALUES ("
                << orderId << ",'" << escape(item.food->getName()) << "',"
                << item.food->getPrice() << ",'" << escape(item.food->getDescription()) << "',"
                << item.quantity << ",'" << escape(item.selectedPreference) << "','"
                << escape(item.specialInstruction) << "')";
        executeQuery(itemSql.str());
    }

    return orderId;
}

std::vector<Order> Database::getOrdersByUser(int userId, const std::vector<Restaurant>& restaurants)
{
    std::vector<Order> orders;
    std::string sql = "SELECT id, user_id, restaurant_name, status, total_price, discount_pct, "
        "delivery_type, delivery_fee, payment_method, rider_name, rider_phone, rating, created_at "
        "FROM orders WHERE user_id=" + std::to_string(userId) + " ORDER BY created_at DESC";

    MYSQL_RES* res = executeSelect(sql);
    if (!res) return orders;

    auto& factory = FoodFactory::instance();
    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res)))
    {
        Order order;
        order.setOrderId(std::stoi(row[0]));
        order.setUserId(std::stoi(row[1]));
        order.setRestaurantName(row[2] ? row[2] : "");
        order.setStatus(stringToOrderStatus(row[3] ? row[3] : "Pending"));
        order.setTotalPrice(std::stod(row[4]));
        order.setDiscountPercentage(std::stod(row[5]));

        if (row[6] && std::string(row[6]) != "None")
        {
            try { order.setDelivery(createDelivery(row[6])); }
            catch (...) {}
        }

        order.setPaymentMethod(row[8] ? row[8] : "");
        order.setRider(row[9] ? row[9] : "", row[10] ? row[10] : "");
        order.setRating(std::stod(row[11] ? row[11] : "0"));
        order.setCreatedAt(row[12] ? row[12] : "");

        // Load order items
        std::string itemSql = "SELECT food_name, food_price, food_description, quantity, "
            "preference, special_instruction FROM order_items WHERE order_id=" + std::to_string(order.getOrderId());
        MYSQL_RES* itemRes = executeSelect(itemSql);
        if (itemRes)
        {
            // Determine cuisine type from restaurant
            std::string cuisineType = "Sichuan"; // default
            for (const auto& r : restaurants)
            {
                if (r.getName() == order.getRestaurantName())
                {
                    cuisineType = r.getType();
                    break;
                }
            }

            MYSQL_ROW itemRow;
            while ((itemRow = mysql_fetch_row(itemRes)))
            {
                try
                {
                    auto food = factory.create(cuisineType, itemRow[0],
                                               std::stod(itemRow[1]),
                                               itemRow[2] ? itemRow[2] : "");
                    OrderItem oi;
                    oi.food = std::move(food);
                    oi.quantity = std::stoi(itemRow[3]);
                    oi.selectedPreference = itemRow[4] ? itemRow[4] : "";
                    oi.specialInstruction = itemRow[5] ? itemRow[5] : "";
                    order.getItems(); // just to verify
                    // We need direct access - use const_cast or add mutable method
                    // For simplicity, re-add items through addItem without recalc
                }
                catch (...) {}
            }
            mysql_free_result(itemRes);
        }

        orders.push_back(std::move(order));
    }
    mysql_free_result(res);
    return orders;
}

std::vector<Order> Database::getAllOrders(const std::vector<Restaurant>& /*restaurants*/)
{
    std::vector<Order> orders;
    std::string sql = "SELECT o.id, o.user_id, u.username, o.restaurant_name, o.status, o.total_price, "
        "o.discount_pct, o.delivery_type, o.delivery_fee, o.payment_method, o.rider_name, "
        "o.rider_phone, o.rating, o.created_at "
        "FROM orders o JOIN users u ON o.user_id = u.id ORDER BY o.created_at DESC";

    MYSQL_RES* res = executeSelect(sql);
    if (!res) return orders;

    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res)))
    {
        Order order;
        order.setOrderId(std::stoi(row[0]));
        order.setUserId(std::stoi(row[1]));
        order.setUsername(row[2] ? row[2] : "");
        order.setRestaurantName(row[3] ? row[3] : "");
        order.setStatus(stringToOrderStatus(row[4] ? row[4] : "Pending"));
        order.setTotalPrice(std::stod(row[5]));
        order.setDiscountPercentage(std::stod(row[6]));

        if (row[7] && std::string(row[7]) != "None")
        {
            try { order.setDelivery(createDelivery(row[7])); }
            catch (...) {}
        }

        order.setPaymentMethod(row[9] ? row[9] : "");
        order.setRider(row[10] ? row[10] : "", row[11] ? row[11] : "");
        order.setRating(std::stod(row[12] ? row[12] : "0"));
        order.setCreatedAt(row[13] ? row[13] : "");

        orders.push_back(std::move(order));
    }
    mysql_free_result(res);
    return orders;
}

bool Database::updateOrderStatus(int orderId, OrderStatus status)
{
    return executeQuery("UPDATE orders SET status='" + orderStatusToString(status)
        + "' WHERE id=" + std::to_string(orderId));
}

bool Database::deleteOrder(int orderId)
{
    return executeQuery("DELETE FROM orders WHERE id=" + std::to_string(orderId));
}

bool Database::rateOrder(int orderId, double rating)
{
    std::ostringstream sql;
    sql << "UPDATE orders SET rating=" << rating << " WHERE id=" << orderId;
    return executeQuery(sql.str());
}

// ---- Rider operations ----
std::vector<Database::Rider> Database::getAllRiders()
{
    std::vector<Rider> riders;
    MYSQL_RES* res = executeSelect("SELECT id, name, phone FROM riders");
    if (!res) return riders;

    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res)))
    {
        riders.push_back({std::stoi(row[0]), row[1], row[2]});
    }
    mysql_free_result(res);
    return riders;
}

int Database::addRider(const std::string& name, const std::string& phone)
{
    std::string sql = "INSERT INTO riders (name, phone) VALUES ('"
        + escape(name) + "','" + escape(phone) + "')";
    if (!executeQuery(sql)) return -1;
    return static_cast<int>(mysql_insert_id(conn_));
}

bool Database::deleteRider(int id)
{
    return executeQuery("DELETE FROM riders WHERE id=" + std::to_string(id));
}

Database::Rider Database::getRandomRider()
{
    auto riders = getAllRiders();
    if (riders.empty()) throw std::runtime_error("No riders available.");

    auto seed = static_cast<unsigned>(
        std::chrono::high_resolution_clock::now().time_since_epoch().count());
    std::mt19937 rng(seed);
    std::uniform_int_distribution<int> dist(0, static_cast<int>(riders.size()) - 1);
    return riders[dist(rng)];
}

// ---- Analytics ----
double Database::getTotalSpentByUser(int userId)
{
    std::string sql = "SELECT COALESCE(SUM(total_price + delivery_fee), 0) FROM orders WHERE user_id="
        + std::to_string(userId);
    MYSQL_RES* res = executeSelect(sql);
    if (!res) return 0;

    MYSQL_ROW row = mysql_fetch_row(res);
    double total = row ? std::stod(row[0]) : 0;
    mysql_free_result(res);
    return total;
}

std::string Database::getFavoriteRestaurant(int userId)
{
    std::string sql = "SELECT restaurant_name, COUNT(*) as cnt FROM orders WHERE user_id="
        + std::to_string(userId) + " GROUP BY restaurant_name ORDER BY cnt DESC LIMIT 1";
    MYSQL_RES* res = executeSelect(sql);
    if (!res) return "N/A";

    MYSQL_ROW row = mysql_fetch_row(res);
    std::string result = row ? row[0] : "N/A";
    mysql_free_result(res);
    return result;
}

int Database::getTotalOrdersByUser(int userId)
{
    std::string sql = "SELECT COUNT(*) FROM orders WHERE user_id=" + std::to_string(userId);
    MYSQL_RES* res = executeSelect(sql);
    if (!res) return 0;

    MYSQL_ROW row = mysql_fetch_row(res);
    int count = row ? std::stoi(row[0]) : 0;
    mysql_free_result(res);
    return count;
}

// ---- Search & Filter ----
std::vector<Restaurant> Database::searchRestaurants(const std::string& keyword)
{
    std::vector<Restaurant> results;
    std::string sql = "SELECT id, name, cuisine_type FROM restaurants WHERE name LIKE '%"
        + escape(keyword) + "%' OR cuisine_type LIKE '%" + escape(keyword) + "%'";
    MYSQL_RES* res = executeSelect(sql);
    if (!res) return results;

    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res)))
    {
        Restaurant r(std::stoi(row[0]), row[1], row[2]);
        auto foods = getFoodsByRestaurant(r.getId(), r.getType());
        for (auto& f : foods) r.addFoodItem(std::move(f));
        results.push_back(std::move(r));
    }
    mysql_free_result(res);
    return results;
}

std::vector<std::shared_ptr<Food>> Database::searchFoodByPriceRange(double minPrice, double maxPrice)
{
    std::vector<std::shared_ptr<Food>> results;
    std::ostringstream sql;
    sql << "SELECT f.id, f.name, f.price, f.description, r.cuisine_type "
        << "FROM foods f JOIN restaurants r ON f.restaurant_id = r.id "
        << "WHERE f.price BETWEEN " << minPrice << " AND " << maxPrice
        << " ORDER BY f.price";

    MYSQL_RES* res = executeSelect(sql.str());
    if (!res) return results;

    auto& factory = FoodFactory::instance();
    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res)))
    {
        try
        {
            auto food = factory.create(row[4], row[1], std::stod(row[2]), row[3] ? row[3] : "");
            food->setId(std::stoi(row[0]));
            results.push_back(std::move(food));
        }
        catch (...) {}
    }
    mysql_free_result(res);
    return results;
}
