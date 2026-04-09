#include "Food.h"
#include "../ui/Color.h"
#include <iostream>

// ---- Food base ----
Food::Food(const std::string& name, double price, const std::string& description,
           const std::vector<std::string>& prefs)
    : name_(name), price_(price), description_(description), preferences_(prefs) {}

int Food::getId() const { return id_; }
void Food::setId(int id) { id_ = id; }
std::string Food::getName() const { return name_; }
double Food::getPrice() const { return price_; }
std::string Food::getDescription() const { return description_; }
std::vector<std::string> Food::getPreferences() const { return preferences_; }
void Food::setPreferences(const std::vector<std::string>& prefs) { preferences_ = prefs; }

// ---- Chinese Food ----
std::string ChineseFood::getTypeName() const { return "Chinese"; }
void ChineseFood::display() const
{
    std::cout << Color::CYAN << "[Chinese] " << Color::RESET
              << name_ << " - $" << price_ << "\n  " << description_ << std::endl;
}
std::unique_ptr<Food> ChineseFood::clone() const { return std::make_unique<ChineseFood>(*this); }

std::string SichuanCuisine::getTypeName() const { return "Sichuan"; }
void SichuanCuisine::display() const
{
    std::cout << Color::RED << "[Sichuan] " << Color::RESET
              << name_ << " - $" << price_ << "\n  " << description_ << std::endl;
}
std::unique_ptr<Food> SichuanCuisine::clone() const { return std::make_unique<SichuanCuisine>(*this); }

std::string CantoneseCuisine::getTypeName() const { return "Cantonese"; }
void CantoneseCuisine::display() const
{
    std::cout << Color::YELLOW << "[Cantonese] " << Color::RESET
              << name_ << " - $" << price_ << "\n  " << description_ << std::endl;
}
std::unique_ptr<Food> CantoneseCuisine::clone() const { return std::make_unique<CantoneseCuisine>(*this); }

// ---- Western Food ----
std::string WesternFood::getTypeName() const { return "Western"; }
void WesternFood::display() const
{
    std::cout << Color::BLUE << "[Western] " << Color::RESET
              << name_ << " - $" << price_ << "\n  " << description_ << std::endl;
}
std::unique_ptr<Food> WesternFood::clone() const { return std::make_unique<WesternFood>(*this); }

std::string ItalianCuisine::getTypeName() const { return "Italian"; }
void ItalianCuisine::display() const
{
    std::cout << Color::GREEN << "[Italian] " << Color::RESET
              << name_ << " - $" << price_ << "\n  " << description_ << std::endl;
}
std::unique_ptr<Food> ItalianCuisine::clone() const { return std::make_unique<ItalianCuisine>(*this); }

std::string FrenchCuisine::getTypeName() const { return "French"; }
void FrenchCuisine::display() const
{
    std::cout << Color::BLUE << "[French] " << Color::RESET
              << name_ << " - $" << price_ << "\n  " << description_ << std::endl;
}
std::unique_ptr<Food> FrenchCuisine::clone() const { return std::make_unique<FrenchCuisine>(*this); }

// ---- Arabic Food ----
std::string ArabicFood::getTypeName() const { return "Arabic"; }
void ArabicFood::display() const
{
    std::cout << Color::YELLOW << "[Arabic] " << Color::RESET
              << name_ << " - $" << price_ << "\n  " << description_ << std::endl;
}
std::unique_ptr<Food> ArabicFood::clone() const { return std::make_unique<ArabicFood>(*this); }

std::string LebaneseCuisine::getTypeName() const { return "Lebanese"; }
void LebaneseCuisine::display() const
{
    std::cout << Color::YELLOW << "[Lebanese] " << Color::RESET
              << name_ << " - $" << price_ << "\n  " << description_ << std::endl;
}
std::unique_ptr<Food> LebaneseCuisine::clone() const { return std::make_unique<LebaneseCuisine>(*this); }

std::string MoroccanCuisine::getTypeName() const { return "Moroccan"; }
void MoroccanCuisine::display() const
{
    std::cout << Color::YELLOW << "[Moroccan] " << Color::RESET
              << name_ << " - $" << price_ << "\n  " << description_ << std::endl;
}
std::unique_ptr<Food> MoroccanCuisine::clone() const { return std::make_unique<MoroccanCuisine>(*this); }

// ---- Mexican Food ----
std::string MexicanFood::getTypeName() const { return "Mexican"; }
void MexicanFood::display() const
{
    std::cout << Color::RED << "[Mexican] " << Color::RESET
              << name_ << " - $" << price_ << "\n  " << description_ << std::endl;
}
std::unique_ptr<Food> MexicanFood::clone() const { return std::make_unique<MexicanFood>(*this); }

std::string TexMexCuisine::getTypeName() const { return "TexMex"; }
void TexMexCuisine::display() const
{
    std::cout << Color::RED << "[Tex-Mex] " << Color::RESET
              << name_ << " - $" << price_ << "\n  " << description_ << std::endl;
}
std::unique_ptr<Food> TexMexCuisine::clone() const { return std::make_unique<TexMexCuisine>(*this); }

std::string TraditionalMexicanCuisine::getTypeName() const { return "TraditionalMexican"; }
void TraditionalMexicanCuisine::display() const
{
    std::cout << Color::RED << "[Traditional Mexican] " << Color::RESET
              << name_ << " - $" << price_ << "\n  " << description_ << std::endl;
}
std::unique_ptr<Food> TraditionalMexicanCuisine::clone() const { return std::make_unique<TraditionalMexicanCuisine>(*this); }

// ---- Japanese Food ----
std::string JapaneseFood::getTypeName() const { return "Japanese"; }
void JapaneseFood::display() const
{
    std::cout << Color::CYAN << "[Japanese] " << Color::RESET
              << name_ << " - $" << price_ << "\n  " << description_ << std::endl;
}
std::unique_ptr<Food> JapaneseFood::clone() const { return std::make_unique<JapaneseFood>(*this); }

std::string SushiCuisine::getTypeName() const { return "Sushi"; }
void SushiCuisine::display() const
{
    std::cout << Color::CYAN << "[Sushi] " << Color::RESET
              << name_ << " - $" << price_ << "\n  " << description_ << std::endl;
}
std::unique_ptr<Food> SushiCuisine::clone() const { return std::make_unique<SushiCuisine>(*this); }

std::string RamenCuisine::getTypeName() const { return "Ramen"; }
void RamenCuisine::display() const
{
    std::cout << Color::CYAN << "[Ramen] " << Color::RESET
              << name_ << " - $" << price_ << "\n  " << description_ << std::endl;
}
std::unique_ptr<Food> RamenCuisine::clone() const { return std::make_unique<RamenCuisine>(*this); }
