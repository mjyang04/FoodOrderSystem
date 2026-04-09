#include "Delivery.h"
#include "../ui/Color.h"
#include <iostream>
#include <stdexcept>

Delivery::Delivery(const std::string& name, int deliveryTime, double fee)
    : name_(name), deliveryTime_(deliveryTime), fee_(fee) {}

std::string Delivery::getName() const { return name_; }
int Delivery::getDeliveryTime() const { return deliveryTime_; }
double Delivery::getFee() const { return fee_; }

// ---- DirectDelivery ----
DirectDelivery::DirectDelivery()
    : Delivery("Direct Delivery", 30, 5.0) {}

void DirectDelivery::display() const
{
    std::cout << Color::GREEN << "Direct Delivery" << Color::RESET
              << " - " << deliveryTime_ << " mins, $" << fee_ << std::endl;
}

std::unique_ptr<Delivery> DirectDelivery::clone() const
{
    return std::make_unique<DirectDelivery>(*this);
}

// ---- StandardDelivery ----
StandardDelivery::StandardDelivery()
    : Delivery("Standard Delivery", 45, 3.0) {}

void StandardDelivery::display() const
{
    std::cout << Color::BLUE << "Standard Delivery" << Color::RESET
              << " - " << deliveryTime_ << " mins, $" << fee_ << std::endl;
}

std::unique_ptr<Delivery> StandardDelivery::clone() const
{
    return std::make_unique<StandardDelivery>(*this);
}

// ---- SaverDelivery ----
SaverDelivery::SaverDelivery()
    : Delivery("Saver Delivery", 60, 2.0) {}

void SaverDelivery::display() const
{
    std::cout << Color::YELLOW << "Saver Delivery" << Color::RESET
              << " - " << deliveryTime_ << " mins, $" << fee_ << std::endl;
}

std::unique_ptr<Delivery> SaverDelivery::clone() const
{
    return std::make_unique<SaverDelivery>(*this);
}

// ---- Factory ----
std::unique_ptr<Delivery> createDelivery(const std::string& name)
{
    if (name == "Direct Delivery") return std::make_unique<DirectDelivery>();
    if (name == "Standard Delivery") return std::make_unique<StandardDelivery>();
    if (name == "Saver Delivery") return std::make_unique<SaverDelivery>();
    throw std::runtime_error("Unknown delivery type: " + name);
}
