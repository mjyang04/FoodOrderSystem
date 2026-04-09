#include "User.h"
#include "HashUtil.h"

User::User(int id, const std::string& username, const std::string& passwordHash,
           const std::string& salt, UserRole role)
    : id_(id), username_(username), passwordHash_(passwordHash), salt_(salt), role_(role) {}

int User::getId() const { return id_; }
std::string User::getUsername() const { return username_; }
std::string User::getPasswordHash() const { return passwordHash_; }
std::string User::getSalt() const { return salt_; }
UserRole User::getRole() const { return role_; }
bool User::isAdmin() const { return role_ == UserRole::ADMIN; }

bool User::verifyPassword(const std::string& password) const
{
    return HashUtil::hashPassword(password, salt_) == passwordHash_;
}
