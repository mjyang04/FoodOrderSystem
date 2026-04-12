// Unit tests for Sprint 4 AI error codes and statusForError mapping.
//
// This test verifies that the new AI-specific error codes in ErrorCodes.h
// are correctly mapped to HTTP status codes by JsonEnvelope::statusForError.
// It links against Drogon (header-only dependency for HttpTypes) and gtest.

#include <gtest/gtest.h>

#include "api/JsonEnvelope.h"
#include "service/ErrorCodes.h"

namespace err = fos::service::err;
using fos::api::statusForError;

TEST(AiErrorCodes, AiUnavailableMapsTo503)
{
    EXPECT_EQ(statusForError(err::kAiUnavailable),
              drogon::k503ServiceUnavailable);
}

TEST(AiErrorCodes, AiBadRequestMapsTo400)
{
    EXPECT_EQ(statusForError(err::kAiBadRequest),
              drogon::k400BadRequest);
}

TEST(AiErrorCodes, AiUpstreamErrorMapsTo502)
{
    EXPECT_EQ(statusForError(err::kAiUpstreamError),
              drogon::k502BadGateway);
}

TEST(AiErrorCodes, AiLlmRefusedMapsTo422)
{
    EXPECT_EQ(statusForError(err::kAiLlmRefused),
              drogon::k422UnprocessableEntity);
}

TEST(AiErrorCodes, ExistingCodeStillWork)
{
    // Verify existing codes are not broken by the new additions.
    EXPECT_EQ(statusForError(err::kValidationError),
              drogon::k400BadRequest);
    EXPECT_EQ(statusForError(err::kDbUnavailable),
              drogon::k503ServiceUnavailable);
    EXPECT_EQ(statusForError(err::kOrderNotFound),
              drogon::k404NotFound);
    EXPECT_EQ(statusForError(err::kInvalidCredentials),
              drogon::k401Unauthorized);
}

TEST(AiErrorCodes, UnknownCodeDefaultsTo400)
{
    EXPECT_EQ(statusForError("SOME_UNKNOWN_CODE"),
              drogon::k400BadRequest);
}
