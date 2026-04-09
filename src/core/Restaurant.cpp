#include "Restaurant.h"
#include "../ui/Color.h"
#include <iostream>

Restaurant::Restaurant(const std::string& name, const std::string& type)
    : name_(name), type_(type) {}

Restaurant::Restaurant(int id, const std::string& name, const std::string& type)
    : id_(id), name_(name), type_(type) {}

int Restaurant::getId() const { return id_; }
void Restaurant::setId(int id) { id_ = id; }
std::string Restaurant::getName() const { return name_; }
std::string Restaurant::getType() const { return type_; }

void Restaurant::addFoodItem(std::shared_ptr<Food> food)
{
    menu_.push_back(std::move(food));
}

const std::vector<std::shared_ptr<Food>>& Restaurant::getMenu() const
{
    return menu_;
}

void Restaurant::displayMenu() const
{
    std::cout << Color::BOLD << Color::GREEN << "Menu for " << name_
              << " (" << type_ << ")" << Color::RESET << std::endl;
    for (size_t i = 0; i < menu_.size(); ++i)
    {
        std::cout << "  " << i + 1 << ". ";
        menu_[i]->display();
    }
}
