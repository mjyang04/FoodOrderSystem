cmake_minimum_required(VERSION 3.16)
project(FoodOrderSystem VERSION 3.0 LANGUAGES CXX)

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

# Shared library of all source files (excluding main.cpp)
set(LIB_SOURCES
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

# Static library for reuse in main and tests
add_library(fos_lib STATIC ${LIB_SOURCES})
target_include_directories(fos_lib PUBLIC
    ${CMAKE_SOURCE_DIR}/src
    ${MYSQL_INCLUDE_DIRS}
)
target_link_libraries(fos_lib PUBLIC ${MYSQL_LIBRARIES})

# Compiler warnings for library
if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU" OR CMAKE_CXX_COMPILER_ID STREQUAL "Clang" OR CMAKE_CXX_COMPILER_ID STREQUAL "AppleClang")
    target_compile_options(fos_lib PRIVATE -Wall -Wextra -Wpedantic)
endif()

# Main executable
add_executable(${PROJECT_NAME} src/main.cpp)
target_link_libraries(${PROJECT_NAME} PRIVATE fos_lib)

# Compiler warnings for main
if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU" OR CMAKE_CXX_COMPILER_ID STREQUAL "Clang" OR CMAKE_CXX_COMPILER_ID STREQUAL "AppleClang")
    target_compile_options(${PROJECT_NAME} PRIVATE -Wall -Wextra -Wpedantic)
endif()

# Install
install(TARGETS ${PROJECT_NAME} DESTINATION bin)

# ---- Unit Tests (GoogleTest via FetchContent) ----
option(BUILD_TESTS "Build unit tests" ON)

if(BUILD_TESTS)
    include(FetchContent)
    FetchContent_Declare(
        googletest
        GIT_REPOSITORY https://github.com/google/googletest.git
        GIT_TAG v1.14.0
    )
    # Prevent GTest from overriding compiler/linker settings on Windows
    set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
    FetchContent_MakeAvailable(googletest)

    enable_testing()

    set(TEST_SOURCES
        tests/test_hashutil.cpp
        tests/test_food.cpp
        tests/test_delivery.cpp
        tests/test_order.cpp
        tests/test_config.cpp
    )

    add_executable(fos_tests ${TEST_SOURCES})
    target_link_libraries(fos_tests PRIVATE fos_lib gtest_main)

    if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU" OR CMAKE_CXX_COMPILER_ID STREQUAL "Clang" OR CMAKE_CXX_COMPILER_ID STREQUAL "AppleClang")
        target_compile_options(fos_tests PRIVATE -Wall -Wextra -Wpedantic)
    endif()

    include(GoogleTest)
    gtest_discover_tests(fos_tests)

    message(STATUS "Unit tests enabled (GoogleTest via FetchContent)")
endif()
