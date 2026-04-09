#include "InputHelper.h"
#include "../ui/Color.h"

namespace InputHelper {

int readInt(const std::string& prompt, int min, int max)
{
    int value;
    while (true)
    {
        std::cout << prompt;
        if (std::cin >> value && value >= min && value <= max)
        {
            return value;
        }
        std::cin.clear();
        std::cin.ignore(std::numeric_limits<std::streamsize>::max(), '\n');
        std::cout << Color::RED << "Invalid input. Please enter a number";
        if (min != std::numeric_limits<int>::min() || max != std::numeric_limits<int>::max())
        {
            std::cout << " between " << min << " and " << max;
        }
        std::cout << "." << Color::RESET << std::endl;
    }
}

double readDouble(const std::string& prompt, double min, double max)
{
    double value;
    while (true)
    {
        std::cout << prompt;
        if (std::cin >> value && value >= min && value <= max)
        {
            return value;
        }
        std::cin.clear();
        std::cin.ignore(std::numeric_limits<std::streamsize>::max(), '\n');
        std::cout << Color::RED << "Invalid input. Please enter a number between "
                  << min << " and " << max << "." << Color::RESET << std::endl;
    }
}

std::string readString(const std::string& prompt)
{
    std::string value;
    while (true)
    {
        std::cout << prompt;
        std::cin >> value;
        if (!value.empty())
        {
            return value;
        }
        std::cout << Color::RED << "Input cannot be empty." << Color::RESET << std::endl;
    }
}

std::string readLine(const std::string& prompt)
{
    std::string value;
    std::cout << prompt;
    std::cin.ignore(std::numeric_limits<std::streamsize>::max(), '\n');
    std::getline(std::cin, value);
    return value;
}

void clearScreen()
{
#ifdef _WIN32
    std::system("cls");
#else
    std::system("clear");
#endif
}

void pauseScreen()
{
    std::cout << "\nPress Enter to continue...";
    std::cin.ignore(std::numeric_limits<std::streamsize>::max(), '\n');
    std::cin.get();
}

} // namespace InputHelper
