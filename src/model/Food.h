#ifndef FOOD_H
#define FOOD_H

#include <string>
#include <vector>
#include <memory>

class Food
{
protected:
    int id_ = 0;
    std::string name_;
    double price_;
    std::string description_;
    std::vector<std::string> preferences_;

public:
    Food(const std::string& name, double price, const std::string& description,
         const std::vector<std::string>& prefs = {});
    virtual ~Food() = default;

    int getId() const;
    void setId(int id);
    std::string getName() const;
    double getPrice() const;
    std::string getDescription() const;
    std::vector<std::string> getPreferences() const;
    void setPreferences(const std::vector<std::string>& prefs);

    virtual std::string getTypeName() const = 0;
    virtual void display() const = 0;
    virtual std::unique_ptr<Food> clone() const = 0;
};

// ---- Chinese Food ----
class ChineseFood : public Food
{
public:
    using Food::Food;
    std::string getTypeName() const override;
    void display() const override;
    std::unique_ptr<Food> clone() const override;
};

class SichuanCuisine : public ChineseFood
{
public:
    using ChineseFood::ChineseFood;
    std::string getTypeName() const override;
    void display() const override;
    std::unique_ptr<Food> clone() const override;
};

class CantoneseCuisine : public ChineseFood
{
public:
    using ChineseFood::ChineseFood;
    std::string getTypeName() const override;
    void display() const override;
    std::unique_ptr<Food> clone() const override;
};

// ---- Western Food ----
class WesternFood : public Food
{
public:
    using Food::Food;
    std::string getTypeName() const override;
    void display() const override;
    std::unique_ptr<Food> clone() const override;
};

class ItalianCuisine : public WesternFood
{
public:
    using WesternFood::WesternFood;
    std::string getTypeName() const override;
    void display() const override;
    std::unique_ptr<Food> clone() const override;
};

class FrenchCuisine : public WesternFood
{
public:
    using WesternFood::WesternFood;
    std::string getTypeName() const override;
    void display() const override;
    std::unique_ptr<Food> clone() const override;
};

// ---- Arabic Food ----
class ArabicFood : public Food
{
public:
    using Food::Food;
    std::string getTypeName() const override;
    void display() const override;
    std::unique_ptr<Food> clone() const override;
};

class LebaneseCuisine : public ArabicFood
{
public:
    using ArabicFood::ArabicFood;
    std::string getTypeName() const override;
    void display() const override;
    std::unique_ptr<Food> clone() const override;
};

class MoroccanCuisine : public ArabicFood
{
public:
    using ArabicFood::ArabicFood;
    std::string getTypeName() const override;
    void display() const override;
    std::unique_ptr<Food> clone() const override;
};

// ---- Mexican Food ----
class MexicanFood : public Food
{
public:
    using Food::Food;
    std::string getTypeName() const override;
    void display() const override;
    std::unique_ptr<Food> clone() const override;
};

class TexMexCuisine : public MexicanFood
{
public:
    using MexicanFood::MexicanFood;
    std::string getTypeName() const override;
    void display() const override;
    std::unique_ptr<Food> clone() const override;
};

class TraditionalMexicanCuisine : public MexicanFood
{
public:
    using MexicanFood::MexicanFood;
    std::string getTypeName() const override;
    void display() const override;
    std::unique_ptr<Food> clone() const override;
};

// ---- Japanese Food ----
class JapaneseFood : public Food
{
public:
    using Food::Food;
    std::string getTypeName() const override;
    void display() const override;
    std::unique_ptr<Food> clone() const override;
};

class SushiCuisine : public JapaneseFood
{
public:
    using JapaneseFood::JapaneseFood;
    std::string getTypeName() const override;
    void display() const override;
    std::unique_ptr<Food> clone() const override;
};

class RamenCuisine : public JapaneseFood
{
public:
    using JapaneseFood::JapaneseFood;
    std::string getTypeName() const override;
    void display() const override;
    std::unique_ptr<Food> clone() const override;
};

#endif // FOOD_H
