#ifndef FOODORDERSYSTEM_H
#define FOODORDERSYSTEM_H

#include <vector>
#include <string>
#include <memory>
#include "../auth/User.h"
#include "Restaurant.h"
#include "Order.h"

class FoodOrderSystem
{
private:
    User currentUser_;
    std::vector<Restaurant> restaurants_;

    void loadRestaurants();

public:
    void setCurrentUser(const User& user);

    // ---- Customer features ----
    void newFoodOrder();
    void viewPastOrders();
    void reorder();
    void deleteOrder();
    void modifyOrder();
    void rateOrder();
    void viewAnalytics();
    void updateOrderStatus();

    // ---- Browse & Search ----
    void displayRestaurants() const;
    void searchRestaurants();
    void searchByPrice();

    // ---- Admin features ----
    void adminPanel();
    void manageRestaurants();
    void manageMenu();
    void manageRiders();
    void manageUsers();
    void viewAllOrders();

    // ---- Main menu ----
    void showMainMenu();
    void showAdminMenu();
};

#endif // FOODORDERSYSTEM_H
