// On-device tests for the STUAART firmware, run on a real Firebeetle ESP32.
// These exercise the parts that the host unit tests cannot reach :
//   - SPIFFS round-trip persistence of offset / scale
//   - HX711 timing under real bus conditions
//   - corruption signature filtering on a real (potentially GPIO-9) cell
//
// Flash with arduino-cli at 115200 baud, then open Serial Monitor at
// 115200 to see the AUnit PASS / FAIL summary.

#include <FS.h>
#include <SPIFFS.h>
#include "LoadCell.h"
#include "LoadCellController.h"
#include <AUnit.h>     // AUnit defines a `test` macro that pollutes
                       // C++ stdlib headers, so include it LAST.

using aunit::TestRunner;

// Production cell pins (V2 PCB). Cell 1 DOUT is on GPIO 9 = flash bus,
// hence the corruption filter is most relevant here. SCK pins are
// per-cell (D2/D3/D4 mapping varies by PCB rev).
static const byte PIN_DOUT[3] = { 9, 27, 16 };
static const byte PIN_SCK [3] = { 17, 26, 25 };

// Shared LoadCell / LoadCellController instances, initialised once in
// setup() and shared across tests. AUnit allows that pattern.
LoadCell loadCell1, loadCell2, loadCell3;
LoadCellController controller;

// ============================================================================
// SPIFFS persistence round-trip
// ============================================================================

test(spiffs_offset_round_trip) {
    // Write a sentinel offset and read it back. Verifies the SPIFFS
    // backend file format and that read_/save_*_to_persistent_memory
    // are wired correctly.
    controller.set_offset(2, -1234567.0f);
    controller.save_offset_to_persistent_memory(2);

    // Clobber RAM, then reload from SPIFFS.
    controller.set_offset(2, 0.0f);
    long readback = controller.read_offset_from_persistent_memory(2);
    assertEqual(readback, -1234567L);
}

test(spiffs_scale_round_trip) {
    controller.set_scale(2, -15701.53f);
    controller.save_scale_coeff_to_persistent_memory(2);

    controller.set_scale(2, 1.0f);
    float readback = controller.read_scale_coeff_from_persistent_memory(2);
    assertNear(readback, -15701.53f, 0.5f);
}

test(spiffs_two_cells_independent) {
    // Save two different values to two cells, verify they stay distinct.
    controller.set_offset(2, 100.0f);
    controller.set_offset(3, 200.0f);
    controller.save_offset_to_persistent_memory(2);
    controller.save_offset_to_persistent_memory(3);
    assertEqual(controller.read_offset_from_persistent_memory(2), 100L);
    assertEqual(controller.read_offset_from_persistent_memory(3), 200L);
}

// ============================================================================
// HX711 hardware sanity
// ============================================================================

test(hx711_cell2_returns_value_in_24bit_range) {
    long raw = controller.read_raw_average(2);
    // Real cell : raw must be in signed 24-bit range. -1L (0xFFFFFF) is
    // either a corruption signature (caught by safe_read) or genuine -1.
    // safe_read either retries or returns -1L if every retry was bad.
    if (raw == -1L) {
        // safe_read gave up. That is acceptable on cell 1 if GPIO 9 is
        // really hosed, but on cell 2 it would suggest a wiring issue.
        // We assert in range below regardless.
    }
    assertMoreOrEqual(raw, -8388608L);
    assertLessOrEqual(raw, 8388607L);
}

test(hx711_cell3_returns_value_in_24bit_range) {
    long raw = controller.read_raw_average(3);
    assertMoreOrEqual(raw, -8388608L);
    assertLessOrEqual(raw, 8388607L);
}

test(hx711_cell2_two_reads_differ_by_at_most_full_scale) {
    // Two consecutive reads on a stable cell should differ by at most a
    // few thousand counts (HX711 noise floor). We use a generous bound
    // to avoid false positives if the platform was just bumped.
    long r1 = controller.read_raw_average(2);
    long r2 = controller.read_raw_average(2);
    long delta = (r1 > r2) ? (r1 - r2) : (r2 - r1);
    // 100 000 counts ~ a few grams at scale = -15700 c/g. Very loose
    // bound : the goal is only to catch a stuck or saturated cell.
    assertLess(delta, 100000L);
}

// ============================================================================
// safe_read counters on real reads
// ============================================================================

test(counters_increment_on_real_reads) {
    loadCell2.reset_stats();
    unsigned long before = loadCell2.total_reads;
    controller.read_raw_average(2);             // weight_n_readings reads
    assertMore(loadCell2.total_reads, before);
}

// Helper : a value that matches one of the three known HX711 corruption
// signatures. Mirrors the static hx711_corrupted() in LoadCell.cpp.
static inline bool is_corrupted_signature(long raw) {
    return raw == -1L || raw == -8388608L || raw == 8388607L;
}

test(safe_read_reduces_corruption_rate_vs_raw_read) {
    // Compare two strategies on the SAME physical cell (cell 1, GPIO 9) :
    //   - raw read() : the inherited HX711 method, no retry, no filter
    //   - safe_read() : retry up to 3x on each corruption signature
    // The expectation is that safe_read drops the observed corruption
    // rate substantially. On the bench, cell 1 typically shows ~1-2 %
    // raw corruption ; after safe_read it should be much lower.
    //
    // The test asserts safe_corrupted <= raw_corrupted (safe never
    // makes things worse) AND, when raw_corrupted > 0, safe_corrupted
    // must be strictly smaller (the retry must recover at least some
    // cases). On a perfectly clean cell both rates are 0 and the
    // strict-less assertion is skipped.
    const int N = 200;

    int raw_corrupted = 0;
    for (int i = 0; i < N; i++) {
        long r = loadCell1.read();          // bypass safe_read
        if (is_corrupted_signature(r)) raw_corrupted++;
    }

    int safe_corrupted = 0;
    for (int i = 0; i < N; i++) {
        long r = loadCell1.safe_read();     // with retry
        if (is_corrupted_signature(r)) safe_corrupted++;
    }

    Serial.print(F("[info] cell 1 raw read corruption: "));
    Serial.print(raw_corrupted);
    Serial.print(F("/")); Serial.print(N);
    Serial.print(F(" = "));
    Serial.print(100.0f * raw_corrupted / N, 2);
    Serial.println(F(" %"));
    Serial.print(F("[info] cell 1 safe_read corruption: "));
    Serial.print(safe_corrupted);
    Serial.print(F("/")); Serial.print(N);
    Serial.print(F(" = "));
    Serial.print(100.0f * safe_corrupted / N, 2);
    Serial.println(F(" %"));

    // Invariant : safe_read never increases the corruption rate.
    assertLessOrEqual(safe_corrupted, raw_corrupted);

    // If raw read saw corruption, safe_read must have caught some of it.
    if (raw_corrupted > 0) {
        assertLess(safe_corrupted, raw_corrupted);
    }
}

test(corrupt_count_on_cell1_GPIO9_baseline) {
    // Cell 1 is on GPIO 9 → expect at least some corruption over many
    // reads. NOT an assertion of correctness ; this test always passes
    // but logs the rate so a human can compare before / after the
    // hardware strap.
    loadCell1.reset_stats();
    for (int i = 0; i < 200; i++) {
        controller.read_raw_average(1);
    }
    Serial.print(F("[info] cell 1 reads="));
    Serial.print(loadCell1.total_reads);
    Serial.print(F(" corrupted="));
    Serial.print(loadCell1.total_corrupted());
    Serial.print(F(" rate="));
    if (loadCell1.total_reads > 0) {
        Serial.print((100.0f * loadCell1.total_corrupted()) /
                     loadCell1.total_reads, 4);
        Serial.println(F("%"));
    } else {
        Serial.println(F("?"));
    }
    assertTrue(loadCell1.total_reads > 0);
}

// ============================================================================
// Setup / loop
// ============================================================================

void setup() {
    Serial.begin(115200);
    while (!Serial) delay(10);
    delay(500);
    Serial.println();
    Serial.println(F("=== STUAART on-device tests (AUnit) ==="));

    if (!SPIFFS.begin(true)) {       // true = format on failure
        Serial.println(F("SPIFFS mount failed"));
    }

    controller.add_loadcell(loadCell1, PIN_DOUT[0], PIN_SCK[0]);
    controller.add_loadcell(loadCell2, PIN_DOUT[1], PIN_SCK[1]);
    controller.add_loadcell(loadCell3, PIN_DOUT[2], PIN_SCK[2]);
    controller.set_all_loadcells_weight_n_readings(1);
    controller.set_all_loadcells_tare_n_readings(2);

    TestRunner::setVerbosity(aunit::Verbosity::kAll);
}

void loop() {
    TestRunner::run();
}
