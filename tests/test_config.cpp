#include <gtest/gtest.h>
#include <fstream>
#include "../src/util/Config.h"

// Helper to create a temp config file
class ConfigTest : public ::testing::Test
{
protected:
    std::string tmpFile = "/tmp/test_config_fos.conf";

    void SetUp() override
    {
        std::ofstream f(tmpFile);
        f << "# Comment line\n"
          << "DB_HOST=localhost\n"
          << "DB_PORT=3307\n"
          << "APP_RATING=4.5\n"
          << "ENABLED=true\n"
          << "QUOTED=\"hello world\"\n"
          << "\n"
          << "  TRIMMED  =  value  \n";
        f.close();
    }

    void TearDown() override
    {
        std::remove(tmpFile.c_str());
    }
};

TEST_F(ConfigTest, LoadFromFile)
{
    Config cfg;
    EXPECT_TRUE(cfg.loadFromFile(tmpFile));
}

TEST_F(ConfigTest, GetString)
{
    Config cfg;
    cfg.loadFromFile(tmpFile);
    EXPECT_EQ(cfg.getString("DB_HOST"), "localhost");
}

TEST_F(ConfigTest, GetInt)
{
    Config cfg;
    cfg.loadFromFile(tmpFile);
    EXPECT_EQ(cfg.getInt("DB_PORT"), 3307);
}

TEST_F(ConfigTest, GetDouble)
{
    Config cfg;
    cfg.loadFromFile(tmpFile);
    EXPECT_DOUBLE_EQ(cfg.getDouble("APP_RATING"), 4.5);
}

TEST_F(ConfigTest, GetBool)
{
    Config cfg;
    cfg.loadFromFile(tmpFile);
    EXPECT_TRUE(cfg.getBool("ENABLED"));
}

TEST_F(ConfigTest, DefaultValues)
{
    Config cfg;
    EXPECT_EQ(cfg.getString("NONEXIST", "fallback"), "fallback");
    EXPECT_EQ(cfg.getInt("NONEXIST", 99), 99);
    EXPECT_DOUBLE_EQ(cfg.getDouble("NONEXIST", 1.5), 1.5);
    EXPECT_FALSE(cfg.getBool("NONEXIST", false));
}

TEST_F(ConfigTest, QuotedValue)
{
    Config cfg;
    cfg.loadFromFile(tmpFile);
    EXPECT_EQ(cfg.getString("QUOTED"), "hello world");
}

TEST_F(ConfigTest, TrimmedKeyAndValue)
{
    Config cfg;
    cfg.loadFromFile(tmpFile);
    EXPECT_EQ(cfg.getString("TRIMMED"), "value");
}

TEST_F(ConfigTest, NonexistentFile)
{
    Config cfg;
    EXPECT_FALSE(cfg.loadFromFile("/tmp/does_not_exist_12345.conf"));
}
