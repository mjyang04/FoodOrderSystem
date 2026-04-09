#ifndef DELIVERY_H
#define DELIVERY_H

#include <string>
#include <memory>

class Delivery
{
protected:
    std::string name_;
    int deliveryTime_;
    double fee_;

public:
    Delivery(const std::string& name, int deliveryTime, double fee);
    virtual ~Delivery() = default;

    std::string getName() const;
    int getDeliveryTime() const;
    double getFee() const;

    virtual void display() const = 0;
    virtual std::unique_ptr<Delivery> clone() const = 0;
};

class DirectDelivery : public Delivery
{
public:
    DirectDelivery();
    void display() const override;
    std::unique_ptr<Delivery> clone() const override;
};

class StandardDelivery : public Delivery
{
public:
    StandardDelivery();
    void display() const override;
    std::unique_ptr<Delivery> clone() const override;
};

class SaverDelivery : public Delivery
{
public:
    SaverDelivery();
    void display() const override;
    std::unique_ptr<Delivery> clone() const override;
};

// Factory function to create delivery by name
std::unique_ptr<Delivery> createDelivery(const std::string& name);

#endif // DELIVERY_H
