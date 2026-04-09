#include "FoodOrderSystem.h"
#include "../db/Database.h"
#include "../ui/Color.h"
#include "../util/InputHelper.h"
#include "../model/FoodFactory.h"
#include <iostream>
#include <iomanip>

void FoodOrderSystem::setCurrentUser(const User& user)
{
    currentUser_ = user;
    loadRestaurants();
}

void FoodOrderSystem::loadRestaurants()
{
    restaurants_ = Database::instance().getAllRestaurants();
}

// ==================== Main Menus ====================

void FoodOrderSystem::showMainMenu()
{
    while (true)
    {
        std::cout << "\n" << Color::BOLD << Color::BLUE
                  << "=== Food Order System ===" << Color::RESET << "\n"
                  << "1. New Food Order\n"
                  << "2. View Past Orders\n"
                  << "3. Browse Restaurants\n"
                  << "4. Reorder\n"
                  << "5. Delete Order\n"
                  << "6. Modify Order\n"
                  << "7. Rate Order\n"
                  << "8. Search Restaurants\n"
                  << "9. Search by Price\n"
                  << "10. My Analytics\n";

        int maxChoice = 11;
        if (currentUser_.isAdmin())
        {
            std::cout << Color::YELLOW << "11. Admin Panel" << Color::RESET << "\n";
            maxChoice = 12;
        }
        std::cout << maxChoice << ". Exit\n";

        int choice = InputHelper::readInt("Choose: ", 1, maxChoice);

        InputHelper::clearScreen();
        switch (choice)
        {
            case 1:  newFoodOrder(); break;
            case 2:  viewPastOrders(); break;
            case 3:  displayRestaurants(); break;
            case 4:  reorder(); break;
            case 5:  deleteOrder(); break;
            case 6:  modifyOrder(); break;
            case 7:  rateOrder(); break;
            case 8:  searchRestaurants(); break;
            case 9:  searchByPrice(); break;
            case 10: viewAnalytics(); break;
            case 11:
                if (currentUser_.isAdmin()) { adminPanel(); break; }
                [[fallthrough]];
            default:
                std::cout << Color::GREEN << "Goodbye!" << Color::RESET << std::endl;
                return;
        }
    }
}

// ==================== Customer Features ====================

void FoodOrderSystem::newFoodOrder()
{
    auto& db = Database::instance();

    try
    {
        std::cout << Color::BOLD << Color::BLUE << "=== New Food Order ===" << Color::RESET << std::endl;
        displayRestaurants();

        int rIdx = InputHelper::readInt("Select restaurant: ", 1, static_cast<int>(restaurants_.size()));
        Restaurant& restaurant = restaurants_[rIdx - 1];

        Order order;
        order.setUserId(currentUser_.getId());
        order.setUsername(currentUser_.getUsername());
        order.setRestaurantName(restaurant.getName());

        const auto& menu = restaurant.getMenu();

        // Add items loop
        while (true)
        {
            InputHelper::clearScreen();
            restaurant.displayMenu();
            std::cout << "\n0. Done adding items\n";

            int fIdx = InputHelper::readInt("Select food (0 to finish): ", 0, static_cast<int>(menu.size()));
            if (fIdx == 0) break;

            auto& food = menu[fIdx - 1];
            int qty = InputHelper::readInt("Quantity: ", 1, 100);

            // Preferences
            std::string preference;
            auto prefs = food->getPreferences();
            if (!prefs.empty())
            {
                std::cout << "Preferences: ";
                for (size_t i = 0; i < prefs.size(); ++i)
                    std::cout << i + 1 << ". " << prefs[i] << "  ";
                std::cout << "\n";
                int pIdx = InputHelper::readInt("Select preference (0 to skip): ", 0, static_cast<int>(prefs.size()));
                if (pIdx > 0) preference = prefs[pIdx - 1];
            }

            std::cout << "Special instructions (press Enter to skip): ";
            std::string instruction;
            std::cin.ignore(std::numeric_limits<std::streamsize>::max(), '\n');
            std::getline(std::cin, instruction);

            order.addItem(food, qty, instruction, preference);
            std::cout << Color::GREEN << "Added!" << Color::RESET << std::endl;
        }

        if (order.getItems().empty())
        {
            std::cout << Color::RED << "No items added. Order cancelled." << Color::RESET << std::endl;
            return;
        }

        // Discount
        double discount = InputHelper::readDouble("Discount percentage (0-100): ", 0, 100);
        order.applyDiscount(discount);

        // Delivery
        std::cout << "\nDelivery options:\n";
        std::cout << "1. Direct Delivery  - 30 min - $5.00\n";
        std::cout << "2. Standard Delivery - 45 min - $3.00\n";
        std::cout << "3. Saver Delivery   - 60 min - $2.00\n";
        int dChoice = InputHelper::readInt("Select delivery: ", 1, 3);

        if (dChoice == 1) order.setDelivery(std::make_unique<DirectDelivery>());
        else if (dChoice == 2) order.setDelivery(std::make_unique<StandardDelivery>());
        else order.setDelivery(std::make_unique<SaverDelivery>());

        // Review items
        while (true)
        {
            InputHelper::clearScreen();
            std::cout << Color::GREEN << "=== Order Review ===" << Color::RESET << std::endl;
            order.displaySummary(false);
            std::cout << "\n0. Confirm order\n";
            int delIdx = InputHelper::readInt("Delete item (0 to proceed): ", 0,
                                              static_cast<int>(order.getItems().size()));
            if (delIdx == 0) break;
            order.deleteItem(delIdx - 1);
        }

        // Payment
        std::cout << "\nPayment method:\n1. Credit Card\n2. E-wallet\n3. Cash on Delivery\n";
        int pChoice = InputHelper::readInt("Select: ", 1, 3);
        if (pChoice == 1) order.setPaymentMethod("Credit Card");
        else if (pChoice == 2) order.setPaymentMethod("E-wallet");
        else order.setPaymentMethod("Cash on Delivery");

        // Assign rider
        auto rider = db.getRandomRider();
        order.setRider(rider.name, rider.phone);
        order.setStatus(OrderStatus::CONFIRMED);

        // Save to DB
        int orderId = db.createOrder(order);
        order.setOrderId(orderId);

        InputHelper::clearScreen();
        order.displayConfirmation();
    }
    catch (const std::exception& e)
    {
        std::cout << Color::RED << "Error: " << e.what() << Color::RESET << std::endl;
    }
}

void FoodOrderSystem::viewPastOrders()
{
    auto& db = Database::instance();
    auto orders = db.getOrdersByUser(currentUser_.getId(), restaurants_);

    std::cout << Color::BOLD << Color::BLUE << "=== Your Orders ===" << Color::RESET << std::endl;
    if (orders.empty())
    {
        std::cout << "No past orders found.\n";
        return;
    }

    for (const auto& order : orders)
    {
        std::cout << std::endl;
        order.displaySummary();
        std::cout << std::string(40, '-') << std::endl;
    }
}

void FoodOrderSystem::reorder()
{
    auto& db = Database::instance();
    auto orders = db.getOrdersByUser(currentUser_.getId(), restaurants_);

    if (orders.empty())
    {
        std::cout << "No past orders to reorder.\n";
        return;
    }

    std::cout << Color::BOLD << "Your orders:\n" << Color::RESET;
    for (const auto& o : orders)
    {
        std::cout << "  #" << o.getOrderId() << " - " << o.getRestaurantName()
                  << " ($" << std::fixed << std::setprecision(2) << o.getGrandTotal() << ")\n";
    }

    int orderId = InputHelper::readInt("Enter Order ID to reorder: ", 1, 999999);

    // Find the order
    const Order* found = nullptr;
    for (const auto& o : orders)
    {
        if (o.getOrderId() == orderId) { found = &o; break; }
    }

    if (!found)
    {
        std::cout << Color::RED << "Order not found." << Color::RESET << std::endl;
        return;
    }

    // Create new order from old
    Order newOrder;
    newOrder.setUserId(currentUser_.getId());
    newOrder.setUsername(currentUser_.getUsername());
    newOrder.setRestaurantName(found->getRestaurantName());

    for (const auto& item : found->getItems())
    {
        newOrder.addItem(item.food, item.quantity, item.specialInstruction, item.selectedPreference);
    }

    // Delivery
    std::cout << "\nDelivery options:\n";
    std::cout << "1. Direct Delivery  - $5.00\n2. Standard Delivery - $3.00\n3. Saver Delivery - $2.00\n";
    int dChoice = InputHelper::readInt("Select delivery: ", 1, 3);
    if (dChoice == 1) newOrder.setDelivery(std::make_unique<DirectDelivery>());
    else if (dChoice == 2) newOrder.setDelivery(std::make_unique<StandardDelivery>());
    else newOrder.setDelivery(std::make_unique<SaverDelivery>());

    // Payment
    std::cout << "Payment: 1. Credit Card  2. E-wallet  3. Cash on Delivery\n";
    int pChoice = InputHelper::readInt("Select: ", 1, 3);
    if (pChoice == 1) newOrder.setPaymentMethod("Credit Card");
    else if (pChoice == 2) newOrder.setPaymentMethod("E-wallet");
    else newOrder.setPaymentMethod("Cash on Delivery");

    auto rider = db.getRandomRider();
    newOrder.setRider(rider.name, rider.phone);
    newOrder.setStatus(OrderStatus::CONFIRMED);

    int newId = db.createOrder(newOrder);
    newOrder.setOrderId(newId);

    InputHelper::clearScreen();
    newOrder.displayConfirmation();
}

void FoodOrderSystem::deleteOrder()
{
    auto& db = Database::instance();
    viewPastOrders();

    int orderId = InputHelper::readInt("Enter Order ID to delete (0 to cancel): ", 0, 999999);
    if (orderId == 0) return;

    if (db.deleteOrder(orderId))
    {
        std::cout << Color::GREEN << "Order #" << orderId << " deleted." << Color::RESET << std::endl;
    }
    else
    {
        std::cout << Color::RED << "Failed to delete order." << Color::RESET << std::endl;
    }
}

void FoodOrderSystem::modifyOrder()
{
    auto& db = Database::instance();
    auto orders = db.getOrdersByUser(currentUser_.getId(), restaurants_);

    if (orders.empty())
    {
        std::cout << "No orders to modify.\n";
        return;
    }

    for (const auto& o : orders)
    {
        std::cout << "  #" << o.getOrderId() << " - " << o.getRestaurantName()
                  << " [" << orderStatusToString(o.getStatus()) << "]\n";
    }

    int orderId = InputHelper::readInt("Enter Order ID to modify status: ", 1, 999999);

    std::cout << "New status:\n"
              << "1. Pending\n2. Confirmed\n3. Preparing\n4. Delivering\n5. Delivered\n6. Cancelled\n";
    int sChoice = InputHelper::readInt("Select: ", 1, 6);

    OrderStatus newStatus;
    switch (sChoice)
    {
        case 1: newStatus = OrderStatus::PENDING; break;
        case 2: newStatus = OrderStatus::CONFIRMED; break;
        case 3: newStatus = OrderStatus::PREPARING; break;
        case 4: newStatus = OrderStatus::DELIVERING; break;
        case 5: newStatus = OrderStatus::DELIVERED; break;
        case 6: newStatus = OrderStatus::CANCELLED; break;
        default: return;
    }

    if (db.updateOrderStatus(orderId, newStatus))
    {
        std::cout << Color::GREEN << "Order status updated." << Color::RESET << std::endl;
    }
    else
    {
        std::cout << Color::RED << "Failed to update status." << Color::RESET << std::endl;
    }
}

void FoodOrderSystem::rateOrder()
{
    auto& db = Database::instance();
    auto orders = db.getOrdersByUser(currentUser_.getId(), restaurants_);

    if (orders.empty())
    {
        std::cout << "No orders to rate.\n";
        return;
    }

    for (const auto& o : orders)
    {
        std::string ratingStr = (o.getRating() > 0)
            ? std::to_string(o.getRating()).substr(0, 3) + "/5.0"
            : "Not rated";
        std::cout << "  #" << o.getOrderId() << " - " << o.getRestaurantName()
                  << " [" << ratingStr << "]\n";
    }

    int orderId = InputHelper::readInt("Enter Order ID to rate: ", 1, 999999);
    double rating = InputHelper::readDouble("Rating (1.0 - 5.0): ", 1.0, 5.0);

    if (db.rateOrder(orderId, rating))
    {
        std::cout << Color::GREEN << "Thank you for your rating!" << Color::RESET << std::endl;
    }
}

void FoodOrderSystem::viewAnalytics()
{
    auto& db = Database::instance();

    std::cout << Color::BOLD << Color::CYAN << "=== Your Order Analytics ===" << Color::RESET << std::endl;
    std::cout << "Total orders: " << db.getTotalOrdersByUser(currentUser_.getId()) << std::endl;
    std::cout << "Total spent: $" << std::fixed << std::setprecision(2)
              << db.getTotalSpentByUser(currentUser_.getId()) << std::endl;
    std::cout << "Favorite restaurant: " << db.getFavoriteRestaurant(currentUser_.getId()) << std::endl;
}

// ==================== Browse & Search ====================

void FoodOrderSystem::displayRestaurants() const
{
    std::cout << Color::BOLD << Color::GREEN << "=== Restaurants ===" << Color::RESET << std::endl;
    for (size_t i = 0; i < restaurants_.size(); ++i)
    {
        std::cout << "  " << i + 1 << ". " << restaurants_[i].getName()
                  << " (" << restaurants_[i].getType() << ")" << std::endl;
    }
}

void FoodOrderSystem::searchRestaurants()
{
    auto& db = Database::instance();
    std::string keyword = InputHelper::readString("Search keyword: ");
    auto results = db.searchRestaurants(keyword);

    if (results.empty())
    {
        std::cout << "No restaurants found.\n";
        return;
    }

    std::cout << Color::BOLD << "Search results:\n" << Color::RESET;
    for (const auto& r : results)
    {
        std::cout << "  " << r.getName() << " (" << r.getType() << ") - "
                  << r.getMenu().size() << " items\n";
    }
}

void FoodOrderSystem::searchByPrice()
{
    auto& db = Database::instance();
    double minP = InputHelper::readDouble("Min price: $", 0, 1000);
    double maxP = InputHelper::readDouble("Max price: $", minP, 1000);

    auto results = db.searchFoodByPriceRange(minP, maxP);
    if (results.empty())
    {
        std::cout << "No items found in this price range.\n";
        return;
    }

    std::cout << Color::BOLD << "Items between $" << minP << " - $" << maxP << ":\n" << Color::RESET;
    for (const auto& f : results)
    {
        std::cout << "  ";
        f->display();
    }
}

// ==================== Admin Panel ====================

void FoodOrderSystem::adminPanel()
{
    while (true)
    {
        std::cout << "\n" << Color::BOLD << Color::YELLOW
                  << "=== Admin Panel ===" << Color::RESET << "\n"
                  << "1. Manage Restaurants\n"
                  << "2. Manage Menu Items\n"
                  << "3. Manage Riders\n"
                  << "4. Manage Users\n"
                  << "5. View All Orders\n"
                  << "6. Back to Main Menu\n";

        int choice = InputHelper::readInt("Choose: ", 1, 6);
        InputHelper::clearScreen();

        switch (choice)
        {
            case 1: manageRestaurants(); break;
            case 2: manageMenu(); break;
            case 3: manageRiders(); break;
            case 4: manageUsers(); break;
            case 5: viewAllOrders(); break;
            case 6: return;
        }
    }
}

void FoodOrderSystem::manageRestaurants()
{
    auto& db = Database::instance();

    std::cout << Color::BOLD << "=== Manage Restaurants ===" << Color::RESET << std::endl;
    displayRestaurants();

    std::cout << "\n1. Add Restaurant\n2. Delete Restaurant\n3. Back\n";
    int choice = InputHelper::readInt("Choose: ", 1, 3);

    if (choice == 1)
    {
        std::string name = InputHelper::readString("Restaurant name: ");

        std::cout << "Cuisine types: Sichuan, Cantonese, Italian, French, Lebanese, "
                  << "Moroccan, TexMex, TraditionalMexican, Sushi, Ramen\n";
        std::string type = InputHelper::readString("Cuisine type: ");

        int id = db.addRestaurant(name, type);
        if (id > 0)
        {
            std::cout << Color::GREEN << "Restaurant added (ID: " << id << ")" << Color::RESET << std::endl;
            loadRestaurants();
        }
    }
    else if (choice == 2)
    {
        int id = InputHelper::readInt("Restaurant ID to delete: ", 1, 999999);
        if (db.deleteRestaurant(id))
        {
            std::cout << Color::GREEN << "Restaurant deleted." << Color::RESET << std::endl;
            loadRestaurants();
        }
    }
}

void FoodOrderSystem::manageMenu()
{
    auto& db = Database::instance();

    std::cout << Color::BOLD << "=== Manage Menu ===" << Color::RESET << std::endl;
    displayRestaurants();

    int rIdx = InputHelper::readInt("Select restaurant: ", 1, static_cast<int>(restaurants_.size()));
    auto& restaurant = restaurants_[rIdx - 1];
    restaurant.displayMenu();

    std::cout << "\n1. Add Food Item\n2. Delete Food Item\n3. Update Price\n4. Back\n";
    int choice = InputHelper::readInt("Choose: ", 1, 4);

    if (choice == 1)
    {
        std::string name = InputHelper::readString("Food name: ");
        double price = InputHelper::readDouble("Price: $", 0.01, 9999);

        std::cout << "Description: ";
        std::string desc;
        std::cin.ignore(std::numeric_limits<std::streamsize>::max(), '\n');
        std::getline(std::cin, desc);

        std::cout << "Preferences (pipe-separated, e.g., Mild|Medium|Spicy, or empty): ";
        std::string prefs;
        std::getline(std::cin, prefs);

        int id = db.addFood(restaurant.getId(), name, price, desc, prefs);
        if (id > 0)
        {
            std::cout << Color::GREEN << "Food item added." << Color::RESET << std::endl;
            loadRestaurants();
        }
    }
    else if (choice == 2)
    {
        int foodId = InputHelper::readInt("Food ID to delete: ", 1, 999999);
        if (db.deleteFood(foodId))
        {
            std::cout << Color::GREEN << "Food item deleted." << Color::RESET << std::endl;
            loadRestaurants();
        }
    }
    else if (choice == 3)
    {
        int foodId = InputHelper::readInt("Food ID to update: ", 1, 999999);
        double newPrice = InputHelper::readDouble("New price: $", 0.01, 9999);
        if (db.updateFoodPrice(foodId, newPrice))
        {
            std::cout << Color::GREEN << "Price updated." << Color::RESET << std::endl;
            loadRestaurants();
        }
    }
}

void FoodOrderSystem::manageRiders()
{
    auto& db = Database::instance();
    auto riders = db.getAllRiders();

    std::cout << Color::BOLD << "=== Manage Riders ===" << Color::RESET << std::endl;
    for (const auto& r : riders)
    {
        std::cout << "  ID: " << r.id << " | " << r.name << " | " << r.phone << std::endl;
    }

    std::cout << "\n1. Add Rider\n2. Delete Rider\n3. Back\n";
    int choice = InputHelper::readInt("Choose: ", 1, 3);

    if (choice == 1)
    {
        std::string name = InputHelper::readString("Rider name: ");
        std::string phone = InputHelper::readString("Phone: ");
        int id = db.addRider(name, phone);
        if (id > 0)
            std::cout << Color::GREEN << "Rider added (ID: " << id << ")" << Color::RESET << std::endl;
    }
    else if (choice == 2)
    {
        int id = InputHelper::readInt("Rider ID to delete: ", 1, 999999);
        if (db.deleteRider(id))
            std::cout << Color::GREEN << "Rider deleted." << Color::RESET << std::endl;
    }
}

void FoodOrderSystem::manageUsers()
{
    auto& db = Database::instance();
    auto users = db.getAllUsers();

    std::cout << Color::BOLD << "=== User List ===" << Color::RESET << std::endl;
    for (const auto& u : users)
    {
        std::cout << "  ID: " << u.getId() << " | " << u.getUsername()
                  << " | " << (u.isAdmin() ? "Admin" : "Customer") << std::endl;
    }

    std::cout << "\n1. Create Admin User\n2. Back\n";
    int choice = InputHelper::readInt("Choose: ", 1, 2);

    if (choice == 1)
    {
        std::string username = InputHelper::readString("Username: ");
        std::string password = InputHelper::readString("Password: ");
        if (db.createUser(username, password, UserRole::ADMIN))
            std::cout << Color::GREEN << "Admin user created." << Color::RESET << std::endl;
    }
}

void FoodOrderSystem::viewAllOrders()
{
    auto& db = Database::instance();
    auto orders = db.getAllOrders(restaurants_);

    std::cout << Color::BOLD << Color::YELLOW << "=== All Orders ===" << Color::RESET << std::endl;
    if (orders.empty())
    {
        std::cout << "No orders in the system.\n";
        return;
    }

    for (const auto& order : orders)
    {
        std::cout << "\nUser: " << order.getUsername() << std::endl;
        order.displaySummary();
        std::cout << std::string(40, '=') << std::endl;
    }
}
