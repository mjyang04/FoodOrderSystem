#include <gtest/gtest.h>
#include "../src/auth/HashUtil.h"

// SHA-256 correctness: test against known values
TEST(HashUtilTest, SHA256_EmptyString)
{
    // SHA-256("") is a well-known value
    std::string hash = HashUtil::sha256("");
    EXPECT_EQ(hash, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
}

TEST(HashUtilTest, SHA256_HelloWorld)
{
    std::string hash = HashUtil::sha256("hello");
    EXPECT_EQ(hash, "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824");
}

TEST(HashUtilTest, SHA256_Deterministic)
{
    std::string hash1 = HashUtil::sha256("test input 123");
    std::string hash2 = HashUtil::sha256("test input 123");
    EXPECT_EQ(hash1, hash2);
}

TEST(HashUtilTest, SHA256_DifferentInputDifferentOutput)
{
    EXPECT_NE(HashUtil::sha256("hello"), HashUtil::sha256("world"));
    EXPECT_NE(HashUtil::sha256("abc"), HashUtil::sha256("abd"));
}

TEST(HashUtilTest, SHA256_OutputLength)
{
    // SHA-256 always produces 64 hex characters
    EXPECT_EQ(HashUtil::sha256("").size(), 64u);
    EXPECT_EQ(HashUtil::sha256("short").size(), 64u);
    EXPECT_EQ(HashUtil::sha256(std::string(1000, 'a')).size(), 64u);
}

// Salt generation tests
TEST(HashUtilTest, GenerateSalt_DefaultLength)
{
    std::string salt = HashUtil::generateSalt();
    EXPECT_EQ(salt.size(), 16u);
}

TEST(HashUtilTest, GenerateSalt_CustomLength)
{
    EXPECT_EQ(HashUtil::generateSalt(8).size(), 8u);
    EXPECT_EQ(HashUtil::generateSalt(32).size(), 32u);
}

TEST(HashUtilTest, GenerateSalt_RandomEachTime)
{
    std::string salt1 = HashUtil::generateSalt();
    std::string salt2 = HashUtil::generateSalt();
    // Extremely unlikely to be equal (62^16 possibilities)
    EXPECT_NE(salt1, salt2);
}

TEST(HashUtilTest, GenerateSalt_OnlyAlphanumeric)
{
    std::string salt = HashUtil::generateSalt(100);
    for (char c : salt)
    {
        EXPECT_TRUE(std::isalnum(static_cast<unsigned char>(c)))
            << "Non-alphanumeric character found: " << c;
    }
}

// Password hashing tests
TEST(HashUtilTest, HashPassword_Deterministic)
{
    std::string hash1 = HashUtil::hashPassword("mypassword", "mysalt");
    std::string hash2 = HashUtil::hashPassword("mypassword", "mysalt");
    EXPECT_EQ(hash1, hash2);
}

TEST(HashUtilTest, HashPassword_DifferentSalt)
{
    std::string hash1 = HashUtil::hashPassword("password", "salt1");
    std::string hash2 = HashUtil::hashPassword("password", "salt2");
    EXPECT_NE(hash1, hash2);
}

TEST(HashUtilTest, HashPassword_DifferentPassword)
{
    std::string hash1 = HashUtil::hashPassword("pass1", "samesalt");
    std::string hash2 = HashUtil::hashPassword("pass2", "samesalt");
    EXPECT_NE(hash1, hash2);
}
