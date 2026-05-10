// Flash-bus / HX711-corruption correlation experiment.
//
// Idea : sample the flash chip-select line (GPIO 11) immediately before
// each HX711 read on cell 1 (DOUT = GPIO 9, the flash-bus pin). If the
// flash bus is active (CS LOW) at that moment, the HX711 read is more
// likely to be corrupted by the bus collision. We also measure CPU
// cycles taken by each read as a coarse proxy for cache stalls.
//
// At the end, we print conditional probabilities :
//
//   P(corrupt | CS LOW just before read)
//   P(corrupt | CS HIGH just before read)
//
// Strong correlation (LOW >> HIGH) would justify a "look-before-you-leap"
// strategy in the production sketch : skip the read window if the bus
// is busy, instead of paying the retry cost.
//
// We also stress the flash bus during the experiment by reading from
// PROGMEM in a tight loop, to provoke more corruption than the bench
// idle would naturally produce.

#include "LoadCell.h"
#include "LoadCellController.h"

LoadCell loadCell1;
LoadCellController controller;

static const byte FLASH_CS_PIN = 11;     // ESP32 flash CS
static const byte CELL1_DOUT   = 9;
static const byte CELL1_SCK    = 17;
static const int  N_READS      = 20000;

// 4 KB of flash data we intentionally re-read every iteration to keep
// the cache thrashing and the flash bus busy.
static const uint8_t THRASH_BLOB[4096] PROGMEM = {
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
static volatile uint32_t thrash_sink = 0;
static void thrash() {
    uint32_t s = thrash_sink;
    for (size_t i = 0; i < sizeof(THRASH_BLOB); i += 4) {
        uint32_t w;
        memcpy_P(&w, THRASH_BLOB + i, sizeof(w));
        s += w;
    }
    thrash_sink = s;
}

static inline bool is_corrupt(long raw) {
    return raw == -1L || raw == -8388608L || raw == 8388607L;
}

void setup() {
    Serial.begin(115200);
    while (!Serial) delay(10);
    delay(500);
    Serial.println();
    Serial.println(F("=== Flash CS vs HX711 corruption correlation ==="));
    Serial.print(F("Cell 1 DOUT = GPIO ")); Serial.println(CELL1_DOUT);
    Serial.print(F("Flash CS    = GPIO ")); Serial.println(FLASH_CS_PIN);

    controller.add_loadcell(loadCell1, CELL1_DOUT, CELL1_SCK);
    loadCell1.set_weight_n_readings(1);
    loadCell1.reset_stats();

    // Try to read GPIO 11 directly. We do NOT call pinMode() on it :
    // the pad is already configured by the flash peripheral, and any
    // GPIO-matrix reconfiguration could disrupt the flash bus and
    // brick the chip.

    // Counters for the 2x2 contingency table.
    long cs_low_corrupt  = 0;
    long cs_low_clean    = 0;
    long cs_high_corrupt = 0;
    long cs_high_clean   = 0;
    long total_corrupt   = 0;

    // Cycle stats : separate for clean and corrupt reads to see if cache
    // stalls (= shorter read durations because wait_ready exits early)
    // correlate with corruption.
    uint64_t cycles_corrupt_sum = 0;
    uint64_t cycles_clean_sum   = 0;
    uint32_t cycles_clean_min   = 0xFFFFFFFFu;
    uint32_t cycles_clean_max   = 0;
    uint32_t cycles_corrupt_min = 0xFFFFFFFFu;
    uint32_t cycles_corrupt_max = 0;

    // Histogram of cycle durations in 1 ms wide bins (240k cycles each).
    const int N_BINS = 20;
    long hist_clean[N_BINS]   = {0};
    long hist_corrupt[N_BINS] = {0};

    for (int i = 0; i < N_READS; i++) {
        thrash();                                    // keep flash busy

        // Sample CS rapidly for ~50 us just before the read. If we see
        // it LOW even once, mark the window as "flash was active".
        bool flash_was_busy = false;
        for (int s = 0; s < 50 && !flash_was_busy; s++) {
            if (digitalRead(FLASH_CS_PIN) == LOW) flash_was_busy = true;
        }

        // Time the actual read. ESP.getCycleCount() ticks at 240 MHz.
        uint32_t c0 = ESP.getCycleCount();
        long raw   = loadCell1.read();               // bypass safe_read
        uint32_t c1 = ESP.getCycleCount();
        uint32_t cycles = c1 - c0;

        bool corrupt = is_corrupt(raw);
        int bin = cycles / 240000;          // 1 ms wide bins
        if (bin >= N_BINS) bin = N_BINS - 1;

        if (corrupt) {
            total_corrupt++;
            cycles_corrupt_sum += cycles;
            if (cycles < cycles_corrupt_min) cycles_corrupt_min = cycles;
            if (cycles > cycles_corrupt_max) cycles_corrupt_max = cycles;
            hist_corrupt[bin]++;
            if (flash_was_busy) cs_low_corrupt++;
            else                cs_high_corrupt++;
            // Log each corrupt event for inspection.
            Serial.print(F("[corrupt @ "));
            Serial.print(i);
            Serial.print(F("] raw=")); Serial.print(raw);
            Serial.print(F(" cycles=")); Serial.println(cycles);
        } else {
            cycles_clean_sum += cycles;
            if (cycles < cycles_clean_min) cycles_clean_min = cycles;
            if (cycles > cycles_clean_max) cycles_clean_max = cycles;
            hist_clean[bin]++;
            if (flash_was_busy) cs_low_clean++;
            else                cs_high_clean++;
        }

        if ((i + 1) % 5000 == 0) {
            Serial.print(F("[progress ")); Serial.print(i + 1);
            Serial.print(F("/")); Serial.print(N_READS);
            Serial.print(F("] corrupt so far: ")); Serial.println(total_corrupt);
        }
    }

    long low_total  = cs_low_corrupt  + cs_low_clean;
    long high_total = cs_high_corrupt + cs_high_clean;
    long clean_total = cs_low_clean + cs_high_clean;

    Serial.println();
    Serial.println(F("--- Results ---"));
    Serial.print(F("Total reads      : ")); Serial.println(N_READS);
    Serial.print(F("Total corrupt    : ")); Serial.println(total_corrupt);
    Serial.print(F("CS LOW  windows  : ")); Serial.println(low_total);
    Serial.print(F("CS HIGH windows  : ")); Serial.println(high_total);

    Serial.println();
    Serial.println(F("Contingency table :"));
    Serial.print(F("  CS LOW  + corrupt = ")); Serial.println(cs_low_corrupt);
    Serial.print(F("  CS LOW  + clean   = ")); Serial.println(cs_low_clean);
    Serial.print(F("  CS HIGH + corrupt = ")); Serial.println(cs_high_corrupt);
    Serial.print(F("  CS HIGH + clean   = ")); Serial.println(cs_high_clean);

    Serial.println();
    if (low_total > 0) {
        Serial.print(F("P(corrupt | CS LOW)  = "));
        Serial.print(100.0f * cs_low_corrupt / low_total, 4);
        Serial.println(F(" %"));
    }
    if (high_total > 0) {
        Serial.print(F("P(corrupt | CS HIGH) = "));
        Serial.print(100.0f * cs_high_corrupt / high_total, 4);
        Serial.println(F(" %"));
    }

    Serial.println();
    Serial.println(F("Cycle counts (240 MHz, 240k cycles = 1 ms) :"));
    if (clean_total > 0) {
        Serial.print(F("  clean   : avg=")); Serial.print((unsigned long)(cycles_clean_sum / clean_total));
        Serial.print(F(" min="));            Serial.print(cycles_clean_min);
        Serial.print(F(" max="));            Serial.println(cycles_clean_max);
    }
    if (total_corrupt > 0) {
        Serial.print(F("  corrupt : avg=")); Serial.print((unsigned long)(cycles_corrupt_sum / total_corrupt));
        Serial.print(F(" min="));            Serial.print(cycles_corrupt_min);
        Serial.print(F(" max="));            Serial.println(cycles_corrupt_max);
    }

    Serial.println();
    Serial.println(F("Histogram (1 ms bins, count per bin) :"));
    Serial.println(F("ms  clean    corrupt"));
    for (int b = 0; b < N_BINS; b++) {
        if (hist_clean[b] == 0 && hist_corrupt[b] == 0) continue;
        if (b < 10) Serial.print(' ');
        Serial.print(b); Serial.print(F("  "));
        Serial.print(hist_clean[b]); Serial.print(F("\t"));
        Serial.println(hist_corrupt[b]);
    }

    Serial.println();
    Serial.println(F("DONE. Reset to run again."));
}

void loop() {}
