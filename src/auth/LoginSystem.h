#ifndef LOGINSYSTEM_H
#define LOGINSYSTEM_H

#include <string>
#include "User.h"

class LoginSystem
{
public:
    // Authenticate user, returns the logged-in User object
    User login();

    // Register a new user
    bool registerUser();
};

#endif // LOGINSYSTEM_H
