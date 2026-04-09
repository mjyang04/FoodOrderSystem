cmake_minimum_required(VERSION 3.16)
project(FoodOrderSystem VERSION 2.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Find MySQL client library
find_package(PkgConfig QUIET)
if(PkgConfig_FOUND)
    pkg_check_modules(MYSQL QUIET mysqlclient)
endif()

if(NOT MYSQL_FOUND)
    # Try common MySQL install paths
    find_path(MYSQL_INCLUDE_DIR mysql/mysql.h
        PATHS
            /usr/include
            /usr/local/include
            /usr/local/mysql/include
            /opt/homebrew/include
            /opt/homebrew/opt/mysql/include
            /opt/homebrew/opt/mysql-client/include
            $ENV{MYSQL_DIR}/include
    )
    find_library(MYSQL_LIBRARY
        NAMES mysqlclient mysql
        PATHS
            /usr/lib
            /usr/local/lib
            /usr/local/mysql/lib
            /opt/homebrew/lib
            /opt/homebrew/opt/mysql/lib
            /opt/homebrew/opt/mysql-client/lib
            $ENV{MYSQL_DIR}/lib
    )

    if(MYSQL_INCLUDE_DIR AND MYSQL_LIBRARY)
        set(MYSQL_FOUND TRUE)
        set(MYSQL_INCLUDE_DIRS ${MYSQL_INCLUDE_DIR})
        set(MYSQL_LIBRARIES ${MYSQL_LIBRARY})
    endif()
endif()

if(NOT MYSQL_FOUND)
    message(FATAL_ERROR
        "MySQL client library not found.\n"
        "Install it via:\n"
        "  macOS:   brew install mysql-client\n"
        "  Ubuntu:  sudo apt install libmysqlclient-dev\n"
        "  CentOS:  sudo yum install mysql-devel\n"
        "Then re-run cmake."
    )
endif()

# Source files
set(SOURCES
    src/main.cpp
    src/model/Food.cpp
    src/model/FoodFactory.cpp
    src/model/Delivery.cpp
    src/core/Restaurant.cpp
    src/core/Order.cpp
    src/core/FoodOrderSystem.cpp
    src/auth/User.cpp
    src/auth/LoginSystem.cpp
    src/auth/HashUtil.cpp
    src/db/Database.cpp
    src/util/InputHelper.cpp
)

# Build executable
add_executable(${PROJECT_NAME} ${SOURCES})

target_include_directories(${PROJECT_NAME} PRIVATE
    ${CMAKE_SOURCE_DIR}/src
    ${MYSQL_INCLUDE_DIRS}
)

target_link_libraries(${PROJECT_NAME} PRIVATE
    ${MYSQL_LIBRARIES}
)

# Compiler warnings
if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU" OR CMAKE_CXX_COMPILER_ID STREQUAL "Clang" OR CMAKE_CXX_COMPILER_ID STREQUAL "AppleClang")
    target_compile_options(${PROJECT_NAME} PRIVATE -Wall -Wextra -Wpedantic)
endif()

# Install
install(TARGETS ${PROJECT_NAME} DESTINATION bin)
