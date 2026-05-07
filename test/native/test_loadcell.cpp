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
// More tests : averaging variants, safe_read knobs, counters, isolation
// ----------------------------------------------------------------------------

TEST(safe_read_no_retry_returns_corrupted_value) {
    LoadCell c = make_cell();
    c.default_value = -1L;
    long got = c.safe_read(0);          // 0 retries
    ASSERT_EQ(got, -1L);
    ASSERT_EQ(c.read_calls, 1);
    ASSERT_EQ(c.total_reads, 1);
    ASSERT_EQ(c.corrupted_neg1, 1);     // counted once (final still-corrupt)
}

TEST(safe_read_one_retry_caps_at_two_reads) {
    LoadCell c = make_cell();
    c.mock_push(-1L);
    c.mock_push(-1L);                   // both bad, but only 1 retry allowed
    c.default_value = -1L;
    long got = c.safe_read(1);
    ASSERT_EQ(got, -1L);
    ASSERT_EQ(c.read_calls, 2);
    ASSERT_EQ(c.total_reads, 2);
}

TEST(safe_read_mixed_signatures_each_counted) {
    LoadCell c = make_cell();
    c.mock_push(-1L);                   // 0xFFFFFF
    c.mock_push(-8388608L);             // 0x800000
    c.mock_push(8388607L);              // 0x7FFFFF
    c.mock_push(42L);                   // good
    long got = c.safe_read();
    ASSERT_EQ(got, 42L);
    ASSERT_EQ(c.corrupted_neg1, 1);
    ASSERT_EQ(c.corrupted_negsat, 1);
    ASSERT_EQ(c.corrupted_possat, 1);
    ASSERT_EQ(c.total_corrupted(), 3);
    ASSERT_EQ(c.read_calls, 4);
}

TEST(read_tare_average_excludes_corrupted) {
    LoadCell c = make_cell();
    c.set_tare_n_readings(4);
    c.mock_push(-1L); c.mock_push(100L);    // retry succeeds at 100
    c.mock_push(200L);
    c.mock_push(-1L); c.mock_push(300L);
    c.mock_push(400L);
    long avg = c.read_tare_average();
    // safe_read returns : 100, 200, 300, 400 → sum = 1000 / 4 = 250
    ASSERT_EQ(avg, 250L);
    ASSERT_EQ(c.corrupted_neg1, 2);
}

TEST(read_tare_average_returns_minus_one_when_all_corrupt) {
    LoadCell c = make_cell();
    c.set_tare_n_readings(3);
    c.default_value = -1L;
    long avg = c.read_tare_average();
    ASSERT_EQ(avg, -1L);
}

TEST(read_scale_coeff_average_uses_its_own_n_readings) {
    LoadCell c = make_cell();
    c.set_scale_coeff_n_readings(5);
    c.set_weight_n_readings(1);         // make sure not used
    for (int i = 0; i < 5; i++) c.mock_push(1000L * (i + 1));
    long avg = c.read_scale_coeff_average();
    // 1000 + 2000 + 3000 + 4000 + 5000 = 15000 / 5 = 3000
    ASSERT_EQ(avg, 3000L);
    ASSERT_EQ(c.read_calls, 5);
}

TEST(tare_sets_offset_to_average_of_tare_reads) {
    LoadCell c = make_cell();
    c.set_tare_n_readings(3);
    c.mock_push(-1212100L);
    c.mock_push(-1212200L);
    c.mock_push(-1212300L);
    c.tare();
    // Average = -1212200, set as offset.
    long off = c.get_offset();
    ASSERT_EQ(off, -1212200L);
}

TEST(get_raw_value_subtracts_offset) {
    LoadCell c = make_cell();
    c.set_weight_n_readings(1);
    c.set_offset(-1000L);
    c.mock_push(500L);
    double v = c.get_raw_value();
    ASSERT_TRUE(v > 1499.0 && v < 1501.0);   // 500 - (-1000) = 1500
}

TEST(get_weight_zero_load_returns_zero) {
    LoadCell c = make_cell();
    c.set_weight_n_readings(1);
    c.set_offset(123456L);
    c.set_scale(-15701.53f);
    c.mock_push(123456L);                    // raw == offset
    float w = c.get_weight();
    ASSERT_TRUE(w > -0.001f && w < 0.001f);
}

TEST(get_weight_positive_scale) {
    LoadCell c = make_cell();
    c.set_weight_n_readings(1);
    c.set_offset(0L);
    c.set_scale(1000.0f);                    // 1000 counts per gram
    c.mock_push(50000L);                     // raw - offset = 50000
    float w = c.get_weight();
    ASSERT_TRUE(w > 49.999f && w < 50.001f); // 50000 / 1000 = 50 g
}

TEST(set_tare_n_readings_clamps) {
    LoadCell c = make_cell();
    c.set_tare_n_readings(0);
    ASSERT_EQ(c.get_tare_n_readings(), 1);
    c.set_tare_n_readings(500);
    ASSERT_EQ(c.get_tare_n_readings(), 255);
    c.set_tare_n_readings(50);
    ASSERT_EQ(c.get_tare_n_readings(), 50);
}

TEST(set_scale_coeff_n_readings_clamps) {
    LoadCell c = make_cell();
    c.set_scale_coeff_n_readings(-1);
    ASSERT_EQ(c.get_scale_coeff_n_readings(), 1);
    c.set_scale_coeff_n_readings(1000);
    ASSERT_EQ(c.get_scale_coeff_n_readings(), 255);
}

TEST(counters_independent_between_instances) {
    LoadCell a = make_cell();
    LoadCell b = make_cell();
    a.mock_push(-1L); a.mock_push(0L);       // a: one corruption + good
    b.mock_push(42L);                        // b: one clean read
    a.safe_read();
    b.safe_read();
    ASSERT_EQ(a.corrupted_neg1, 1);
    ASSERT_EQ(a.total_reads, 2);
    ASSERT_EQ(b.corrupted_neg1, 0);
    ASSERT_EQ(b.total_reads, 1);
}

TEST(reset_stats_does_not_change_offset_or_scale) {
    LoadCell c = make_cell();
    c.set_offset(-1212208L);
    c.set_scale(-15701.53f);
    c.mock_push(-1L); c.mock_push(0L);
    c.safe_read();
    c.reset_stats();
    ASSERT_EQ(c.get_offset(), -1212208L);
    ASSERT_TRUE(c.get_scale() < -15701.0f && c.get_scale() > -15702.0f);
}

TEST(total_reads_matches_mock_read_calls) {
    LoadCell c = make_cell();
    c.set_weight_n_readings(5);
    c.mock_push(-1L); c.mock_push(100L);     // 1 corruption + retry
    c.mock_push(200L);
    c.mock_push(-1L); c.mock_push(-1L); c.mock_push(300L);
    c.mock_push(400L);
    c.mock_push(500L);
    c.read_raw_average();
    ASSERT_EQ(c.total_reads, c.read_calls);  // strict parity invariant
}

TEST(safe_read_default_value_chain_works) {
    // With default_value = 0 and no scripted sequence, safe_read should
    // return 0 on the first call without retry.
    LoadCell c = make_cell();
    long got = c.safe_read();
    ASSERT_EQ(got, 0L);
    ASSERT_EQ(c.read_calls, 1);
    ASSERT_EQ(c.total_corrupted(), 0);
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

    run_safe_read_no_retry_returns_corrupted_value();
    run_safe_read_one_retry_caps_at_two_reads();
    run_safe_read_mixed_signatures_each_counted();
    run_read_tare_average_excludes_corrupted();
    run_read_tare_average_returns_minus_one_when_all_corrupt();
    run_read_scale_coeff_average_uses_its_own_n_readings();
    run_tare_sets_offset_to_average_of_tare_reads();
    run_get_raw_value_subtracts_offset();
    run_get_weight_zero_load_returns_zero();
    run_get_weight_positive_scale();
    run_set_tare_n_readings_clamps();
    run_set_scale_coeff_n_readings_clamps();
    run_counters_independent_between_instances();
    run_reset_stats_does_not_change_offset_or_scale();
    run_total_reads_matches_mock_read_calls();
    run_safe_read_default_value_chain_works();

    printf("\n%d passed, %d failed\n", passes, failures);
    return failures == 0 ? 0 : 1;
}
