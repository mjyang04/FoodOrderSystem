#ifndef RESTAURANT_H
#define RESTAURANT_H

#include <string>
#include <vector>
#include <memory>
#include "../model/Food.h"

class Restaurant
{
private:
    int id_ = 0;
    std::string name_;
    std::string type_;
    std::vector<std::shared_ptr<Food>> menu_;

public:
    Restaurant() = default;
    Restaurant(int id, const std::string& name, const std::string& type);

    int getId() const;
    void setId(int id);
    std::string getName() const;
    std::string getType() const;

    void addFoodItem(std::shared_ptr<Food> food);
    const std::vector<std::shared_ptr<Food>>& getMenu() const;
    void displayMenu() const;
};

#endif // RESTAURANT_H
