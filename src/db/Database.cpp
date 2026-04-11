#include "Database.h"
#include "../auth/HashUtil.h"
#include "../model/FoodFactory.h"
#include "../util/Logger.h"
#include "../util/Exceptions.h"
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
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    conn_ = mysql_init(nullptr);
    if (!conn_)
    {
        LOG_ERROR("mysql_init() failed");
        return false;
    }
    if (!mysql_real_connect(conn_, host.c_str(), user.c_str(), password.c_str(),
                            dbName.c_str(), port, nullptr, 0))
    {
        LOG_ERROR(std::string("MySQL connection error: ") + mysql_error(conn_));
        mysql_close(conn_);
        conn_ = nullptr;
        return false;
    }
    mysql_set_character_set(conn_, "utf8mb4");
    LOG_INFO("Connected to MySQL: " + dbName + "@" + host + ":" + std::to_string(port));
    return true;
}

void Database::disconnect()
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    if (conn_)
    {
        mysql_close(conn_);
        conn_ = nullptr;
        LOG_INFO("MySQL connection closed");
    }
}

bool Database::isConnected() const
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    return conn_ != nullptr;
}

bool Database::executeQuery(const std::string& query)
{
    if (mysql_query(conn_, query.c_str()))
    {
        LOG_ERROR(std::string("SQL Error: ") + mysql_error(conn_) + " | Query: " + query);
        return false;
    }
    return true;
}

MYSQL_RES* Database::executeSelect(const std::string& query)
{
    if (mysql_query(conn_, query.c_str()))
    {
        LOG_ERROR(std::string("SQL Error: ") + mysql_error(conn_) + " | Query: " + query);
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

// ---- Prepared Statement Helpers ----
MYSQL_STMT* Database::prepareStatement(const std::string& query)
{
    MYSQL_STMT* stmt = mysql_stmt_init(conn_);
    if (!stmt)
    {
        LOG_ERROR("mysql_stmt_init() failed");
        return nullptr;
    }
    if (mysql_stmt_prepare(stmt, query.c_str(), query.size()))
    {
        LOG_ERROR(std::string("Prepare failed: ") + mysql_stmt_error(stmt) + " | Query: " + query);
        mysql_stmt_close(stmt);
        return nullptr;
    }
    return stmt;
}

// ---- Schema Initialization ----
void Database::initializeSchema()
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
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
            special_instruction TEXT,
            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
        ))"
    };

    for (const auto& sql : statements)
    {
        executeQuery(sql);
    }
    LOG_DEBUG("Schema initialized");
}

// ---- User operations (Prepared Statements) ----
bool Database::createUser(const std::string& username, const std::string& password, UserRole role)
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    if (userExists(username))
    {
        throw UserExistsException(username);
    }

    std::string salt = HashUtil::generateSalt();
    std::string hash = HashUtil::hashPassword(password, salt);
    std::string roleStr = (role == UserRole::ADMIN) ? "admin" : "customer";

    const std::string sql = "INSERT INTO users (username, password_hash, salt, role) VALUES (?, ?, ?, ?)";
    MYSQL_STMT* stmt = prepareStatement(sql);
    if (!stmt) return false;

    MYSQL_BIND bind[4];
    std::memset(bind, 0, sizeof(bind));
    unsigned long usernameLen = username.size();
    unsigned long hashLen = hash.size();
    unsigned long saltLen = salt.size();
    unsigned long roleLen = roleStr.size();

    bind[0].buffer_type = MYSQL_TYPE_STRING;
    bind[0].buffer = const_cast<char*>(username.c_str());
    bind[0].buffer_length = usernameLen;
    bind[0].length = &usernameLen;

    bind[1].buffer_type = MYSQL_TYPE_STRING;
    bind[1].buffer = const_cast<char*>(hash.c_str());
    bind[1].buffer_length = hashLen;
    bind[1].length = &hashLen;

    bind[2].buffer_type = MYSQL_TYPE_STRING;
    bind[2].buffer = const_cast<char*>(salt.c_str());
    bind[2].buffer_length = saltLen;
    bind[2].length = &saltLen;

    bind[3].buffer_type = MYSQL_TYPE_STRING;
    bind[3].buffer = const_cast<char*>(roleStr.c_str());
    bind[3].buffer_length = roleLen;
    bind[3].length = &roleLen;

    mysql_stmt_bind_param(stmt, bind);
    bool success = (mysql_stmt_execute(stmt) == 0);
    if (!success)
    {
        LOG_ERROR(std::string("createUser failed: ") + mysql_stmt_error(stmt));
    }
    else
    {
        LOG_INFO("User created: " + username + " (role: " + roleStr + ")");
    }
    mysql_stmt_close(stmt);
    return success;
}

User Database::findUserByUsername(const std::string& username)
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    const std::string sql = "SELECT id, username, password_hash, salt, role FROM users WHERE username=?";
    MYSQL_STMT* stmt = prepareStatement(sql);
    if (!stmt) return {};

    MYSQL_BIND paramBind[1];
    std::memset(paramBind, 0, sizeof(paramBind));
    unsigned long usernameLen = username.size();
    paramBind[0].buffer_type = MYSQL_TYPE_STRING;
    paramBind[0].buffer = const_cast<char*>(username.c_str());
    paramBind[0].buffer_length = usernameLen;
    paramBind[0].length = &usernameLen;

    mysql_stmt_bind_param(stmt, paramBind);
    if (mysql_stmt_execute(stmt))
    {
        LOG_ERROR(std::string("findUserByUsername exec failed: ") + mysql_stmt_error(stmt));
        mysql_stmt_close(stmt);
        return {};
    }

    // Bind result columns
    MYSQL_BIND resultBind[5];
    std::memset(resultBind, 0, sizeof(resultBind));
    int id = 0;
    char unameBuf[64] = {};
    char hashBuf[256] = {};
    char saltBuf[128] = {};
    char roleBuf[16] = {};
    unsigned long unameLen = 0, hashBufLen = 0, saltBufLen = 0, roleBufLen = 0;

    resultBind[0].buffer_type = MYSQL_TYPE_LONG;
    resultBind[0].buffer = &id;

    resultBind[1].buffer_type = MYSQL_TYPE_STRING;
    resultBind[1].buffer = unameBuf;
    resultBind[1].buffer_length = sizeof(unameBuf);
    resultBind[1].length = &unameLen;

    resultBind[2].buffer_type = MYSQL_TYPE_STRING;
    resultBind[2].buffer = hashBuf;
    resultBind[2].buffer_length = sizeof(hashBuf);
    resultBind[2].length = &hashBufLen;

    resultBind[3].buffer_type = MYSQL_TYPE_STRING;
    resultBind[3].buffer = saltBuf;
    resultBind[3].buffer_length = sizeof(saltBuf);
    resultBind[3].length = &saltBufLen;

    resultBind[4].buffer_type = MYSQL_TYPE_STRING;
    resultBind[4].buffer = roleBuf;
    resultBind[4].buffer_length = sizeof(roleBuf);
    resultBind[4].length = &roleBufLen;

    mysql_stmt_bind_result(stmt, resultBind);
    mysql_stmt_store_result(stmt);

    User user;
    if (mysql_stmt_fetch(stmt) == 0)
    {
        UserRole role = (std::string(roleBuf, roleBufLen) == "admin") ? UserRole::ADMIN : UserRole::CUSTOMER;
        user = User(id, std::string(unameBuf, unameLen), std::string(hashBuf, hashBufLen),
                    std::string(saltBuf, saltBufLen), role);
    }

    mysql_stmt_close(stmt);
    return user;
}

bool Database::userExists(const std::string& username)
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
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
    std::lock_guard<std::recursive_mutex> lock(mutex_);
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
    std::lock_guard<std::recursive_mutex> lock(mutex_);
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

std::optional<Restaurant> Database::findRestaurantById(int id)
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    const std::string sql = "SELECT id, name, cuisine_type FROM restaurants WHERE id=?";
    MYSQL_STMT* stmt = prepareStatement(sql);
    if (!stmt) return std::nullopt;

    MYSQL_BIND paramBind[1];
    std::memset(paramBind, 0, sizeof(paramBind));
    int idParam = id;
    paramBind[0].buffer_type = MYSQL_TYPE_LONG;
    paramBind[0].buffer = &idParam;

    mysql_stmt_bind_param(stmt, paramBind);
    if (mysql_stmt_execute(stmt))
    {
        LOG_ERROR(std::string("findRestaurantById exec failed: ") + mysql_stmt_error(stmt));
        mysql_stmt_close(stmt);
        return std::nullopt;
    }

    MYSQL_BIND resultBind[3];
    std::memset(resultBind, 0, sizeof(resultBind));
    int rowId = 0;
    char nameBuf[128] = {};
    char typeBuf[64] = {};
    unsigned long nameLen = 0;
    unsigned long typeLen = 0;

    resultBind[0].buffer_type = MYSQL_TYPE_LONG;
    resultBind[0].buffer = &rowId;

    resultBind[1].buffer_type = MYSQL_TYPE_STRING;
    resultBind[1].buffer = nameBuf;
    resultBind[1].buffer_length = sizeof(nameBuf);
    resultBind[1].length = &nameLen;

    resultBind[2].buffer_type = MYSQL_TYPE_STRING;
    resultBind[2].buffer = typeBuf;
    resultBind[2].buffer_length = sizeof(typeBuf);
    resultBind[2].length = &typeLen;

    mysql_stmt_bind_result(stmt, resultBind);
    mysql_stmt_store_result(stmt);

    std::optional<Restaurant> result;
    if (mysql_stmt_fetch(stmt) == 0)
    {
        result.emplace(rowId,
                       std::string(nameBuf, nameLen),
                       std::string(typeBuf, typeLen));
    }

    mysql_stmt_close(stmt);
    return result;
}

int Database::addRestaurant(const std::string& name, const std::string& type)
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    std::string sql = "INSERT INTO restaurants (name, cuisine_type) VALUES ('"
        + escape(name) + "','" + escape(type) + "')";
    if (!executeQuery(sql)) return -1;
    LOG_INFO("Restaurant added: " + name + " (" + type + ")");
    return static_cast<int>(mysql_insert_id(conn_));
}

bool Database::deleteRestaurant(int id)
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    bool result = executeQuery("DELETE FROM restaurants WHERE id=" + std::to_string(id));
    if (result) LOG_INFO("Restaurant deleted: #" + std::to_string(id));
    return result;
}

// ---- Food operations ----
std::vector<std::shared_ptr<Food>> Database::getFoodsByRestaurant(int restaurantId,
                                                                   const std::string& cuisineType)
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
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

            // Parse preferences (pipe-separated in DB)
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
            LOG_ERROR(std::string("Error loading food: ") + e.what());
        }
    }
    mysql_free_result(res);
    return foods;
}

int Database::addFood(int restaurantId, const std::string& name, double price,
                      const std::string& description, const std::string& preferences)
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    std::ostringstream sql;
    sql << "INSERT INTO foods (restaurant_id, name, price, description, preferences) VALUES ("
        << restaurantId << ",'" << escape(name) << "'," << price << ",'"
        << escape(description) << "','" << escape(preferences) << "')";
    if (!executeQuery(sql.str())) return -1;
    LOG_INFO("Food added: " + name + " ($" + std::to_string(price) + ")");
    return static_cast<int>(mysql_insert_id(conn_));
}

bool Database::deleteFood(int id)
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    return executeQuery("DELETE FROM foods WHERE id=" + std::to_string(id));
}

bool Database::updateFoodPrice(int id, double newPrice)
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    std::ostringstream sql;
    sql << "UPDATE foods SET price=" << newPrice << " WHERE id=" << id;
    return executeQuery(sql.str());
}

// ---- Order operations (Prepared Statements for insert) ----
int Database::createOrder(const Order& order)
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    const std::string sql =
        "INSERT INTO orders (user_id, restaurant_name, status, total_price, discount_pct, "
        "delivery_type, delivery_fee, payment_method, rider_name, rider_phone) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)";
    MYSQL_STMT* stmt = prepareStatement(sql);
    if (!stmt) return -1;

    int userId = order.getUserId();
    std::string restName = order.getRestaurantName();
    std::string statusStr = orderStatusToString(order.getStatus());
    double totalPrice = order.getTotalPrice();
    double discountPct = order.getDiscountPercentage();
    std::string deliveryType = order.getDelivery() ? order.getDelivery()->getName() : "None";
    double deliveryFee = order.getDelivery() ? order.getDelivery()->getFee() : 0.0;
    std::string payMethod = order.getPaymentMethod();
    std::string riderName = order.getRiderName();
    std::string riderPhone = order.getRiderPhone();

    unsigned long restNameLen = restName.size();
    unsigned long statusLen = statusStr.size();
    unsigned long delTypeLen = deliveryType.size();
    unsigned long payLen = payMethod.size();
    unsigned long rNameLen = riderName.size();
    unsigned long rPhoneLen = riderPhone.size();

    MYSQL_BIND bind[10];
    std::memset(bind, 0, sizeof(bind));

    bind[0].buffer_type = MYSQL_TYPE_LONG;
    bind[0].buffer = &userId;

    bind[1].buffer_type = MYSQL_TYPE_STRING;
    bind[1].buffer = const_cast<char*>(restName.c_str());
    bind[1].buffer_length = restNameLen;
    bind[1].length = &restNameLen;

    bind[2].buffer_type = MYSQL_TYPE_STRING;
    bind[2].buffer = const_cast<char*>(statusStr.c_str());
    bind[2].buffer_length = statusLen;
    bind[2].length = &statusLen;

    bind[3].buffer_type = MYSQL_TYPE_DOUBLE;
    bind[3].buffer = &totalPrice;

    bind[4].buffer_type = MYSQL_TYPE_DOUBLE;
    bind[4].buffer = &discountPct;

    bind[5].buffer_type = MYSQL_TYPE_STRING;
    bind[5].buffer = const_cast<char*>(deliveryType.c_str());
    bind[5].buffer_length = delTypeLen;
    bind[5].length = &delTypeLen;

    bind[6].buffer_type = MYSQL_TYPE_DOUBLE;
    bind[6].buffer = &deliveryFee;

    bind[7].buffer_type = MYSQL_TYPE_STRING;
    bind[7].buffer = const_cast<char*>(payMethod.c_str());
    bind[7].buffer_length = payLen;
    bind[7].length = &payLen;

    bind[8].buffer_type = MYSQL_TYPE_STRING;
    bind[8].buffer = const_cast<char*>(riderName.c_str());
    bind[8].buffer_length = rNameLen;
    bind[8].length = &rNameLen;

    bind[9].buffer_type = MYSQL_TYPE_STRING;
    bind[9].buffer = const_cast<char*>(riderPhone.c_str());
    bind[9].buffer_length = rPhoneLen;
    bind[9].length = &rPhoneLen;

    mysql_stmt_bind_param(stmt, bind);
    bool success = (mysql_stmt_execute(stmt) == 0);
    int orderId = -1;
    if (success)
    {
        orderId = static_cast<int>(mysql_stmt_insert_id(stmt));
        LOG_INFO("Order #" + std::to_string(orderId) + " created for user #" + std::to_string(userId));
    }
    else
    {
        LOG_ERROR(std::string("createOrder failed: ") + mysql_stmt_error(stmt));
    }
    mysql_stmt_close(stmt);

    if (orderId < 0) return -1;

    // Insert order items using prepared statements
    addOrderItems(orderId, order.getItems());

    return orderId;
}

void Database::addOrderItems(int orderId, const std::vector<OrderItem>& items)
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    const std::string sql =
        "INSERT INTO order_items (order_id, food_name, food_price, food_description, "
        "quantity, preference, special_instruction) VALUES (?, ?, ?, ?, ?, ?, ?)";

    for (const auto& item : items)
    {
        MYSQL_STMT* stmt = prepareStatement(sql);
        if (!stmt) continue;

        std::string foodName = item.food->getName();
        double foodPrice = item.food->getPrice();
        std::string foodDesc = item.food->getDescription();
        int qty = item.quantity;
        std::string pref = item.selectedPreference;
        std::string instruction = item.specialInstruction;

        unsigned long nameLen = foodName.size();
        unsigned long descLen = foodDesc.size();
        unsigned long prefLen = pref.size();
        unsigned long instrLen = instruction.size();

        MYSQL_BIND bind[7];
        std::memset(bind, 0, sizeof(bind));

        bind[0].buffer_type = MYSQL_TYPE_LONG;
        bind[0].buffer = &orderId;

        bind[1].buffer_type = MYSQL_TYPE_STRING;
        bind[1].buffer = const_cast<char*>(foodName.c_str());
        bind[1].buffer_length = nameLen;
        bind[1].length = &nameLen;

        bind[2].buffer_type = MYSQL_TYPE_DOUBLE;
        bind[2].buffer = &foodPrice;

        bind[3].buffer_type = MYSQL_TYPE_STRING;
        bind[3].buffer = const_cast<char*>(foodDesc.c_str());
        bind[3].buffer_length = descLen;
        bind[3].length = &descLen;

        bind[4].buffer_type = MYSQL_TYPE_LONG;
        bind[4].buffer = &qty;

        bind[5].buffer_type = MYSQL_TYPE_STRING;
        bind[5].buffer = const_cast<char*>(pref.c_str());
        bind[5].buffer_length = prefLen;
        bind[5].length = &prefLen;

        bind[6].buffer_type = MYSQL_TYPE_STRING;
        bind[6].buffer = const_cast<char*>(instruction.c_str());
        bind[6].buffer_length = instrLen;
        bind[6].length = &instrLen;

        mysql_stmt_bind_param(stmt, bind);
        if (mysql_stmt_execute(stmt))
        {
            LOG_ERROR(std::string("addOrderItem failed: ") + mysql_stmt_error(stmt));
        }
        mysql_stmt_close(stmt);
    }
}

std::vector<Order> Database::getOrdersByUser(int userId, const std::vector<Restaurant>& restaurants)
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
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
                    order.addItem(oi.food, oi.quantity, oi.specialInstruction, oi.selectedPreference);
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
    std::lock_guard<std::recursive_mutex> lock(mutex_);
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
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    bool result = executeQuery("UPDATE orders SET status='" + orderStatusToString(status)
        + "' WHERE id=" + std::to_string(orderId));
    if (result) LOG_INFO("Order #" + std::to_string(orderId) + " status -> " + orderStatusToString(status));
    return result;
}

bool Database::deleteOrder(int orderId)
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    bool result = executeQuery("DELETE FROM orders WHERE id=" + std::to_string(orderId));
    if (result) LOG_INFO("Order #" + std::to_string(orderId) + " deleted");
    return result;
}

bool Database::rateOrder(int orderId, double rating)
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    std::ostringstream sql;
    sql << "UPDATE orders SET rating=" << rating << " WHERE id=" << orderId;
    return executeQuery(sql.str());
}

// ---- Rider operations ----
std::vector<Database::Rider> Database::getAllRiders()
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
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
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    std::string sql = "INSERT INTO riders (name, phone) VALUES ('"
        + escape(name) + "','" + escape(phone) + "')";
    if (!executeQuery(sql)) return -1;
    LOG_INFO("Rider added: " + name);
    return static_cast<int>(mysql_insert_id(conn_));
}

bool Database::deleteRider(int id)
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    return executeQuery("DELETE FROM riders WHERE id=" + std::to_string(id));
}

Database::Rider Database::getRandomRider()
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    auto riders = getAllRiders();
    if (riders.empty()) throw OrderException("No riders available");

    auto seed = static_cast<unsigned>(
        std::chrono::high_resolution_clock::now().time_since_epoch().count());
    std::mt19937 rng(seed);
    std::uniform_int_distribution<int> dist(0, static_cast<int>(riders.size()) - 1);
    return riders[dist(rng)];
}

// ---- Analytics ----
double Database::getTotalSpentByUser(int userId)
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
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
    std::lock_guard<std::recursive_mutex> lock(mutex_);
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
    std::lock_guard<std::recursive_mutex> lock(mutex_);
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
    std::lock_guard<std::recursive_mutex> lock(mutex_);
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
    std::lock_guard<std::recursive_mutex> lock(mutex_);
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
