// Xtensa LX6 performance counter exploration on ESP32.
//
// Goal : count flash bus / cache miss events that overlap each HX711
// read on cell 1 (GPIO 9 = flash bus pin), so we can discard reads
// that coincide with bus activity instead of relying on retry-after-
// corruption.
//
// Uses the ESP-IDF `xtensa_perfmon_*` API (libperfmon.a from
// tools/esp32-libs/3.3.8/lib). The relevant counter is
// XTPERF_CNT_ICACHE_MISSES (0x8005) which counts the penalty cycles
// caused by instruction-cache misses ; this is a direct measurement
// of "how much the CPU stalled waiting for the flash bus" during the
// window we monitor.

#include "LoadCell.h"
#include "LoadCellController.h"
extern "C" {
  #include "xtensa_perfmon_access.h"
  #include "xtensa/xt_perf_consts.h"
  #include "xtensa_perfmon_masks.h"
}

LoadCell loadCell1;
LoadCellController controller;

static const byte CELL1_DOUT = 9;
static const byte CELL1_SCK  = 17;

// Provoke flash bus activity by reading PROGMEM data sequentially.
static const uint8_t BIG_BLOB[8192] PROGMEM = {
    #define X16 1, 2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47,
    #define X64 X16 X16 X16 X16
    #define X256 X64 X64 X64 X64
    X256 X256 X256 X256
    X256 X256 X256 X256
    X256 X256 X256 X256
    X256 X256 X256 X256
    X256 X256 X256 X256
    X256 X256 X256 X256
    X256 X256 X256 X256
    X256 X256 X256 X256
    #undef X16
    #undef X64
    #undef X256
};
static volatile uint32_t blob_sink = 0;

static void thrash_cache_lines() {
    uint32_t s = blob_sink;
    for (size_t i = 0; i < sizeof(BIG_BLOB); i += 32) {
        s += pgm_read_byte(BIG_BLOB + i);
    }
    blob_sink = s;
}

void setup() {
    Serial.begin(115200);
    while (!Serial) delay(10);
    delay(500);
    Serial.println();
    Serial.println(F("=== Xtensa perf counter : ICACHE_MISSES window ==="));

    // Configure PM0 to count ICACHE miss penalty cycles. kernelcnt=0
    // means count only in user mode (kernel mode is what FreeRTOS uses
    // for ISRs and scheduler). tracelevel=15 means count at all levels.
    // Sanity test : start with CYCLES which is guaranteed to count.
    // If even this doesn't tick, the API is fundamentally not running.
    esp_err_t r = xtensa_perfmon_init(
        0,
        XTPERF_CNT_CYCLES,            // 0 = every cycle
        XTPERF_MASK_CYCLES,           // 0x0001
        1,                            // kernelcnt = 1 : count in any mode
        -1);                          // tracelevel : -1 = no filter
    if (r != ESP_OK) {
        Serial.print(F("perfmon_init failed : ")); Serial.println(r);
        return;
    }
    xtensa_perfmon_start();

    // Sanity : the counter should tick during a known cache thrashing
    // operation. Print the value before and after.
    xtensa_perfmon_reset(0);
    uint32_t v_before = xtensa_perfmon_value(0);
    thrash_cache_lines();
    uint32_t v_after  = xtensa_perfmon_value(0);
    Serial.print(F("Sanity check : counter went from "));
    Serial.print(v_before); Serial.print(F(" to "));
    Serial.print(v_after);  Serial.print(F(" during thrash (delta = "));
    Serial.print(v_after - v_before); Serial.println(F(")"));
    if (v_after == v_before) {
        Serial.println(F("Counter not ticking ; perfmon may be disabled."));
        return;
    }

    // Now run HX711 reads on cell 1, snapshot the counter immediately
    // before and after each read, and correlate the delta with whether
    // the read came back corrupted.
    controller.add_loadcell(loadCell1, CELL1_DOUT, CELL1_SCK);
    loadCell1.set_weight_n_readings(1);
    loadCell1.reset_stats();

    const int N = 5000;
    int corrupt_count = 0;
    uint64_t sum_clean = 0, sum_corrupt = 0;
    uint32_t max_clean = 0, min_corrupt = 0xFFFFFFFFu;
    long hist_clean[10]   = {0};
    long hist_corrupt[10] = {0};

    Serial.println();
    Serial.print(F("Sampling ")); Serial.print(N);
    Serial.println(F(" reads on cell 1, with cache thrash between each."));

    for (int i = 0; i < N; i++) {
        thrash_cache_lines();
        xtensa_perfmon_reset(0);
        long raw  = loadCell1.read();
        uint32_t pm = xtensa_perfmon_value(0);
        bool corrupt = (raw == -1L || raw == -8388608L || raw == 8388607L);

        // bins of 100 cycles each, 0..900+
        int bin = pm / 100;
        if (bin >= 10) bin = 9;

        if (corrupt) {
            corrupt_count++;
            sum_corrupt += pm;
            if (pm < min_corrupt) min_corrupt = pm;
            hist_corrupt[bin]++;
            if (corrupt_count <= 20) {
                Serial.print(F("[corrupt @ ")); Serial.print(i);
                Serial.print(F("] raw=")); Serial.print(raw);
                Serial.print(F(" miss_cycles=")); Serial.println(pm);
            }
        } else {
            sum_clean += pm;
            if (pm > max_clean) max_clean = pm;
            hist_clean[bin]++;
        }
    }

    long clean_count = N - corrupt_count;
    Serial.println();
    Serial.print(F("Total reads     : ")); Serial.println(N);
    Serial.print(F("Total corrupt   : ")); Serial.println(corrupt_count);
    if (clean_count > 0) {
        Serial.print(F("clean   miss_cycles : avg="));
        Serial.print((unsigned long)(sum_clean / clean_count));
        Serial.print(F(" max=")); Serial.println(max_clean);
    }
    if (corrupt_count > 0) {
        Serial.print(F("corrupt miss_cycles : avg="));
        Serial.print((unsigned long)(sum_corrupt / corrupt_count));
        Serial.print(F(" min=")); Serial.println(min_corrupt);
    }

    Serial.println();
    Serial.println(F("Histogram of miss_cycles per read (bins of 100) :"));
    Serial.println(F("bin    clean    corrupt"));
    for (int b = 0; b < 10; b++) {
        if (hist_clean[b] == 0 && hist_corrupt[b] == 0) continue;
        if (b < 9) {
            Serial.print(b * 100); Serial.print(F("-")); Serial.print(b * 100 + 99);
        } else {
            Serial.print(F("900+"));
        }
        Serial.print(F("\t"));
        Serial.print(hist_clean[b]);   Serial.print(F("\t"));
        Serial.println(hist_corrupt[b]);
    }

    Serial.println();
    Serial.println(F("DONE. Reset to run again."));
}

void loop() {}
