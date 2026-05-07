// Long-running corruption hunter for STUAART cell 1 (GPIO 9 / flash bus).
// Runs safe_read() in a tight loop for HUNT_DURATION_MS (default 5 min)
// and prints lifetime stats every PROGRESS_INTERVAL_MS (default 30 s).
// At the end, prints a final summary including the "saved by retry"
// count which is the quantitative validation of the safe_read patch.
//
// Use this to compare cell 1 corruption rates :
//   - before the GPIO 9 hardware strap (baseline)
//   - after the strap (should drop toward 0)
//
// Flash, open Serial Monitor at 115200, wait 5 minutes.

#include "LoadCell.h"
#include "LoadCellController.h"

LoadCell loadCell1;
LoadCellController controller;

static const unsigned long HUNT_DURATION_MS    = 5UL * 60UL * 1000UL;  // 5 min
static const unsigned long PROGRESS_INTERVAL_MS = 30UL * 1000UL;        // 30 s

static const byte CELL1_DOUT = 9;   // V2 PCB : GPIO 9 = flash bus
static const byte CELL1_SCK  = 17;

static volatile uint32_t thrash_sink = 0;
static const uint8_t CACHE_THRASH_BLOB[4096] PROGMEM = {
    #define X16 1, 2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47,
    #define X64 X16 X16 X16 X16
    #define X256 X64 X64 X64 X64
    X256 X256 X256 X256
    X256 X256 X256 X256
    X256 X256 X256 X256
    X256 X256 X256 X256
    #undef X16
    #undef X64
    #undef X256
};
static void thrash_cache() {
    uint32_t s = thrash_sink;
    for (size_t i = 0; i < sizeof(CACHE_THRASH_BLOB); i += 4) {
        uint32_t w;
        memcpy_P(&w, CACHE_THRASH_BLOB + i, sizeof(w));
        s += w;
    }
    thrash_sink = s;
}

static inline bool is_corrupt(long raw) {
    return raw == -1L || raw == -8388608L || raw == 8388607L;
}

static void print_progress(unsigned long elapsed_ms,
                           unsigned long calls,
                           unsigned long final_failures) {
    unsigned long observed = loadCell1.total_corrupted();
    unsigned long reads    = loadCell1.total_reads;
    unsigned long saved    = (observed > final_failures)
                                 ? (observed - final_failures) : 0;
    Serial.print(F("[t=")); Serial.print(elapsed_ms / 1000); Serial.print(F("s] "));
    Serial.print(F("calls=")); Serial.print(calls);
    Serial.print(F(" reads=")); Serial.print(reads);
    Serial.print(F(" obs=")); Serial.print(observed);
    Serial.print(F(" final_fail=")); Serial.print(final_failures);
    Serial.print(F(" saved=")); Serial.print(saved);
    Serial.print(F(" rate="));
    if (reads > 0) {
        Serial.print(100.0f * observed / reads, 4);
        Serial.println(F("%"));
    } else {
        Serial.println(F("?"));
    }
}

void setup() {
    Serial.begin(115200);
    while (!Serial) delay(10);
    delay(500);
    Serial.println();
    Serial.println(F("=== STUAART corruption hunter (5 min) ==="));
    Serial.print(F("Cell 1 DOUT=GPIO ")); Serial.print(CELL1_DOUT);
    Serial.print(F(" SCK=GPIO "));        Serial.println(CELL1_SCK);

    controller.add_loadcell(loadCell1, CELL1_DOUT, CELL1_SCK);
    loadCell1.set_weight_n_readings(1);
    loadCell1.reset_stats();

    unsigned long start = millis();
    unsigned long last_progress = start;
    unsigned long calls = 0;
    unsigned long final_failures = 0;

    while (millis() - start < HUNT_DURATION_MS) {
        thrash_cache();
        long r = loadCell1.safe_read();
        if (is_corrupt(r)) final_failures++;
        calls++;
        delay(0);

        unsigned long now = millis();
        if (now - last_progress >= PROGRESS_INTERVAL_MS) {
            print_progress(now - start, calls, final_failures);
            last_progress = now;
        }
    }

    Serial.println();
    Serial.println(F("=== FINAL SUMMARY ==="));
    print_progress(millis() - start, calls, final_failures);
    unsigned long observed = loadCell1.total_corrupted();
    if (observed > 0) {
        unsigned long saved = (observed > final_failures)
                                  ? (observed - final_failures) : 0;
        Serial.print(F("recovery rate : "));
        Serial.print(100.0f * saved / observed, 2);
        Serial.println(F(" %"));
    } else {
        Serial.println(F("no corruption observed in this 5-min window"));
    }
    Serial.println(F("Hunter done. Reset to run again."));
}

void loop() {}
