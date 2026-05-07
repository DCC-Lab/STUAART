// Host-side unit tests for the LoadCell class : safe_read retry on
// corruption signatures, averaging that excludes corrupted samples, and
// the lifetime counters introduced for the `stats` serial command.
//
// These tests use a programmable mock HX711 (test/native/stubs/HX711.h)
// that scripts the next return value of `read()`. The production sketch
// is unchanged ; only the include path differs at build time.

#include "LoadCell.h"
#include <cstdio>
#include <cstdlib>

// ----------------------------------------------------------------------------
// Tiny zero-deps assertion framework
// ----------------------------------------------------------------------------
static int passes = 0;
static int failures = 0;
static const char* current_test = "(none)";

#define TEST(name)                                                 \
    static void name();                                            \
    static void run_##name() { current_test = #name; name(); }     \
    static void name()

#define ASSERT_EQ(a, b) do {                                       \
    long long _a = (long long)(a), _b = (long long)(b);            \
    if (_a != _b) {                                                \
        printf("  FAIL %s:%d in %s : expected %lld == %lld, got %lld\n",  \
               __FILE__, __LINE__, current_test, _b, _b, _a);      \
        failures++;                                                \
    } else passes++;                                               \
} while(0)

#define ASSERT_TRUE(x) do {                                        \
    if (!(x)) {                                                    \
        printf("  FAIL %s:%d in %s : expected (%s) to be true\n",  \
               __FILE__, __LINE__, current_test, #x);              \
        failures++;                                                \
    } else passes++;                                               \
} while(0)

#define ASSERT_FALSE(x) ASSERT_TRUE(!(x))

// ----------------------------------------------------------------------------
// Fixture helper : fresh LoadCell with the mock state cleared.
// ----------------------------------------------------------------------------
static LoadCell make_cell() {
    LoadCell c;
    c.mock_reset();
    return c;
}

// ----------------------------------------------------------------------------
// Tests
// ----------------------------------------------------------------------------

TEST(safe_read_returns_clean_value_on_first_try) {
    LoadCell c = make_cell();
    c.mock_push(123456L);
    long got = c.safe_read();
    ASSERT_EQ(got, 123456L);
    ASSERT_EQ(c.read_calls, 1);
    ASSERT_EQ(c.total_reads, 1);
    ASSERT_EQ(c.total_corrupted(), 0);
}

TEST(safe_read_retries_on_neg1_then_succeeds) {
    LoadCell c = make_cell();
    c.mock_push(-1L);
    c.mock_push(-1L);
    c.mock_push(-1212208L);     // good
    long got = c.safe_read();
    ASSERT_EQ(got, -1212208L);
    ASSERT_EQ(c.read_calls, 3);
    ASSERT_EQ(c.total_reads, 3);
    ASSERT_EQ(c.corrupted_neg1, 2);
}

TEST(safe_read_retries_on_negsat) {
    LoadCell c = make_cell();
    c.mock_push(-8388608L);
    c.mock_push(-1212208L);
    long got = c.safe_read();
    ASSERT_EQ(got, -1212208L);
    ASSERT_EQ(c.corrupted_negsat, 1);
    ASSERT_EQ(c.corrupted_neg1, 0);
}

TEST(safe_read_retries_on_possat) {
    LoadCell c = make_cell();
    c.mock_push(8388607L);
    c.mock_push(0L);
    long got = c.safe_read();
    ASSERT_EQ(got, 0L);
    ASSERT_EQ(c.corrupted_possat, 1);
}

TEST(safe_read_gives_up_after_max_retries) {
    LoadCell c = make_cell();
    // Default queue value is 0 : we explicitly set it to -1 and never push.
    c.default_value = -1L;
    long got = c.safe_read();              // max_retries default is 3
    ASSERT_EQ(got, -1L);
    // 1 initial + 3 retries = 4 read() calls
    ASSERT_EQ(c.read_calls, 4);
    ASSERT_EQ(c.total_reads, 4);
    // 4 observed corruptions : initial + 3 retries
    ASSERT_EQ(c.corrupted_neg1, 4);
}

TEST(read_raw_average_excludes_corrupted_samples) {
    LoadCell c = make_cell();
    c.set_weight_n_readings(5);
    // 5 reads asked. Make 2 of them clean, 3 of them -1L (each retried
    // 3x and still failing). The clean reads return -1212000 and -1212100.
    // The default_value stays 0 (so safe_read on the corrupted slots
    // succeeds on the FIRST retry).
    // Sequence : -1L (corrupt) → 0 (retry succeeds, value 0)
    //            -1212000 (clean, no retry)
    //            -1L → 0
    //            -1212100 (clean)
    //            -1L → 0
    c.mock_push(-1L); c.mock_push(0L);
    c.mock_push(-1212000L);
    c.mock_push(-1L); c.mock_push(0L);
    c.mock_push(-1212100L);
    c.mock_push(-1L); c.mock_push(0L);

    long avg = c.read_raw_average();
    // safe_read returned : 0, -1212000, 0, -1212100, 0  -> all GOOD
    // (none of them match a corruption signature post-retry)
    // sum = 0 + -1212000 + 0 + -1212100 + 0 = -2424100, / 5 = -484820
    ASSERT_EQ(avg, -484820L);

    ASSERT_EQ(c.corrupted_neg1, 3);    // 3 initial corrupted reads observed
    ASSERT_EQ(c.read_calls, 8);        // 5 cells × 1 + 3 retries
    ASSERT_EQ(c.total_reads, 8);
}

TEST(read_raw_average_returns_minus_one_when_all_corrupt) {
    LoadCell c = make_cell();
    c.set_weight_n_readings(3);
    c.default_value = -1L;             // every read is corrupt
    long avg = c.read_raw_average();
    ASSERT_EQ(avg, -1L);
    // No good samples accumulated.
}

TEST(reset_stats_zeros_all_counters) {
    LoadCell c = make_cell();
    c.mock_push(-1L); c.mock_push(0L);
    c.safe_read();
    ASSERT_TRUE(c.total_reads > 0);
    ASSERT_TRUE(c.corrupted_neg1 > 0);
    c.reset_stats();
    ASSERT_EQ(c.total_reads, 0);
    ASSERT_EQ(c.corrupted_neg1, 0);
    ASSERT_EQ(c.corrupted_negsat, 0);
    ASSERT_EQ(c.corrupted_possat, 0);
    ASSERT_EQ(c.total_corrupted(), 0);
}

TEST(set_n_readings_clamps_to_byte_range) {
    LoadCell c = make_cell();
    c.set_weight_n_readings(0);
    ASSERT_EQ(c.get_weight_n_readings(), 1);
    c.set_weight_n_readings(-5);
    ASSERT_EQ(c.get_weight_n_readings(), 1);
    c.set_weight_n_readings(300);
    ASSERT_EQ(c.get_weight_n_readings(), 255);
    c.set_weight_n_readings(42);
    ASSERT_EQ(c.get_weight_n_readings(), 42);
}

TEST(get_weight_uses_offset_and_scale) {
    LoadCell c = make_cell();
    c.set_weight_n_readings(1);
    c.set_offset(-1212208L);
    c.set_scale(-15701.53f);
    c.mock_push(-1212208L);            // raw == offset → mass = 0
    float w = c.get_weight();
    ASSERT_TRUE(w > -0.001f && w < 0.001f);

    c.mock_reset();
    c.set_weight_n_readings(1);
    c.set_offset(-1212208L);
    c.set_scale(-15701.53f);
    // mass = (raw - offset) / scale  →  raw = offset + mass*scale
    // For mass = 100 g and scale = -15701.53 (typical STUAART cell 2/3) :
    //   raw = -1212208 + 100 * -15701.53 = -2782361
    long target = (long)(-1212208.0f + 100.0f * -15701.53f);
    c.mock_push(target);
    w = c.get_weight();
    ASSERT_TRUE(w > 99.9f && w < 100.1f);
}

// ----------------------------------------------------------------------------
// main
// ----------------------------------------------------------------------------
int main() {
    printf("LoadCell host-side unit tests\n");
    printf("=============================\n");

    run_safe_read_returns_clean_value_on_first_try();
    run_safe_read_retries_on_neg1_then_succeeds();
    run_safe_read_retries_on_negsat();
    run_safe_read_retries_on_possat();
    run_safe_read_gives_up_after_max_retries();
    run_read_raw_average_excludes_corrupted_samples();
    run_read_raw_average_returns_minus_one_when_all_corrupt();
    run_reset_stats_zeros_all_counters();
    run_set_n_readings_clamps_to_byte_range();
    run_get_weight_uses_offset_and_scale();

    printf("\n%d passed, %d failed\n", passes, failures);
    return failures == 0 ? 0 : 1;
}
