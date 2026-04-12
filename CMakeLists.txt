cmake_minimum_required(VERSION 3.16)
project(FoodOrderSystem VERSION 3.1 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Sprint 2.5 (L-FETCHCONTENT-HOIST): hoisted here so the jwt-cpp block
# (fos_api) and the googletest block (fos_tests) share a single include.
# include() is idempotent in practice, but leaving two copies invites
# drift if one block starts tweaking FetchContent defaults later.
include(FetchContent)

# Help find_package locate Homebrew-installed packages on macOS
if(APPLE)
    list(APPEND CMAKE_PREFIX_PATH
        /opt/homebrew
        /opt/homebrew/opt/drogon
        /opt/homebrew/opt/jsoncpp
        /opt/homebrew/opt/openssl@3
    )
endif()

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
#
# Note: AuthService, RestaurantService and DefaultServices intentionally live
# in fos_lib rather than fos_api so that unit tests (fos_tests) can link the
# service layer without depending on Drogon/jwt-cpp. JwtService stays in
# fos_api because it is the single hard dependency on jwt-cpp.
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
    src/service/AuthService.cpp
    src/service/RestaurantService.cpp
    src/service/OrderService.cpp
    src/service/DefaultServices.cpp
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

# ---- CLI executable (legacy interactive client) ----
add_executable(fos_cli src/main.cpp)
target_link_libraries(fos_cli PRIVATE fos_lib)

if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU" OR CMAKE_CXX_COMPILER_ID STREQUAL "Clang" OR CMAKE_CXX_COMPILER_ID STREQUAL "AppleClang")
    target_compile_options(fos_cli PRIVATE -Wall -Wextra -Wpedantic)
endif()

# ---- HTTP API executable (Drogon-based backend) ----
find_package(Drogon CONFIG QUIET)

if(Drogon_FOUND)
    # jwt-cpp is header-only and not in Homebrew on macOS, so we pull it via
    # FetchContent. It is linked ONLY into fos_api, never into fos_lib or
    # fos_cli — the CLI does not need JWT, and keeping the library free of
    # jwt-cpp avoids propagating the dependency to the unit test target.
    FetchContent_Declare(
        jwt-cpp
        GIT_REPOSITORY https://github.com/Thalhammer/jwt-cpp.git
        GIT_TAG v0.7.0
    )
    # Skip jwt-cpp's own tests/examples to speed up configure.
    set(JWT_BUILD_EXAMPLES OFF CACHE INTERNAL "")
    set(JWT_BUILD_TESTS OFF CACHE INTERNAL "")
    set(JWT_EXTERNAL_PICOJSON OFF CACHE INTERNAL "")
    FetchContent_MakeAvailable(jwt-cpp)

    set(API_SOURCES
        src/api/main_api.cpp
        src/api/AuthContext.cpp
        src/api/controllers/HealthController.cc
        src/api/controllers/AuthController.cc
        src/api/controllers/RestaurantController.cc
        src/api/controllers/OrderController.cc
        src/api/controllers/AiController.cc
        src/api/filters/JwtAuthFilter.cc
        src/service/JwtService.cpp
    )

    add_executable(fos_api ${API_SOURCES})
    target_link_libraries(fos_api
        PRIVATE
            fos_lib
            Drogon::Drogon
            jwt-cpp::jwt-cpp
    )
    target_include_directories(fos_api PRIVATE ${CMAKE_SOURCE_DIR}/src)

    if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU" OR CMAKE_CXX_COMPILER_ID STREQUAL "Clang" OR CMAKE_CXX_COMPILER_ID STREQUAL "AppleClang")
        target_compile_options(fos_api PRIVATE -Wall -Wextra -Wpedantic)
    endif()

    message(STATUS "Drogon found: HTTP API target 'fos_api' enabled")
    message(STATUS "jwt-cpp fetched via FetchContent (v0.7.0, header-only)")
    install(TARGETS fos_api DESTINATION bin)
else()
    message(WARNING
        "Drogon not found. HTTP API target 'fos_api' will NOT be built.\n"
        "Install it via:\n"
        "  macOS:   brew install drogon\n"
        "  Ubuntu:  see https://drogon.docsforge.com/master/installation/"
    )
endif()

# Install CLI binary
install(TARGETS fos_cli DESTINATION bin)

# ---- Unit Tests (GoogleTest via FetchContent) ----
option(BUILD_TESTS "Build unit tests" ON)

if(BUILD_TESTS)
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
        tests/test_auth_service.cpp
        tests/test_order_service.cpp
        tests/test_order_status.cpp
    )

    add_executable(fos_tests ${TEST_SOURCES})
    target_link_libraries(fos_tests PRIVATE fos_lib gtest_main)
    target_include_directories(fos_tests PRIVATE ${CMAKE_SOURCE_DIR}/tests)

    if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU" OR CMAKE_CXX_COMPILER_ID STREQUAL "Clang" OR CMAKE_CXX_COMPILER_ID STREQUAL "AppleClang")
        target_compile_options(fos_tests PRIVATE -Wall -Wextra -Wpedantic)
    endif()

    include(GoogleTest)
    gtest_discover_tests(fos_tests)

    # Sprint 4: AI error code mapping tests (depend on Drogon headers for
    # HttpStatusCode enum, so they get their own target).
    if(Drogon_FOUND)
        add_executable(fos_ai_tests tests/test_ai_error_codes.cpp)
        target_link_libraries(fos_ai_tests PRIVATE gtest_main Drogon::Drogon)
        target_include_directories(fos_ai_tests PRIVATE ${CMAKE_SOURCE_DIR}/src)
        gtest_discover_tests(fos_ai_tests)
    endif()

    message(STATUS "Unit tests enabled (GoogleTest via FetchContent)")
endif()
