#ifndef USER_H
#define USER_H

#include <string>

enum class UserRole { CUSTOMER, ADMIN };

class User
{
private:
    int id_ = 0;
    std::string username_;
    std::string passwordHash_;
    std::string salt_;
    UserRole role_ = UserRole::CUSTOMER;

public:
    User() = default;
    User(int id, const std::string& username, const std::string& passwordHash,
         const std::string& salt, UserRole role = UserRole::CUSTOMER);

    int getId() const;
    std::string getUsername() const;
    std::string getPasswordHash() const;
    std::string getSalt() const;
    UserRole getRole() const;
    bool isAdmin() const;

    bool verifyPassword(const std::string& password) const;
};

#endif // USER_H
