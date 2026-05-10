// Test : SPI flash state machine register as a real-time flash-bus indicator.
//
// SPI0 is the flash master. Its EXT2 register (offset 0xF8 from the SPI0
// base 0x3FF43000) exposes a 3-bit state field (SPI_ST). It is 0 when
// the flash bus is idle and non-zero during a transaction.
//
// If this register actually changes during cache-miss / PROGMEM-fetch
// activity, it gives us a direct way to detect "flash bus busy" without
// any perfmon counter. We could then poll it just before each HX711
// SCK pulse and skip the read if the bus is active.
//
// Test design : sample SPI_ST in a tight loop while running different
// stress patterns. Count how often we observe a non-zero state during
// each window. A high non-zero count during PROGMEM stress and a low
// count during RAM/IRAM stress would confirm the register is useful.

#include <Arduino.h>

static const uint32_t SPI0_BASE     = 0x3FF43000;
static const uint32_t SPI0_EXT2_REG = SPI0_BASE + 0xF8;
static const uint32_t SPI1_BASE     = 0x3FF42000;
static const uint32_t SPI1_EXT2_REG = SPI1_BASE + 0xF8;

static inline uint32_t spi0_st() { return (*(volatile uint32_t*)SPI0_EXT2_REG) & 0x7; }
static inline uint32_t spi1_st() { return (*(volatile uint32_t*)SPI1_EXT2_REG) & 0x7; }

// 64 KB PROGMEM blob.
static const uint32_t BIG_FLASH_BLOB[16384] PROGMEM = {
    #define X4   0xDEADBEEF, 0xCAFEBABE, 0x12345678, 0x87654321,
    #define X16  X4 X4 X4 X4
    #define X64  X16 X16 X16 X16
    #define X256 X64 X64 X64 X64
    #define X1024 X256 X256 X256 X256
    X1024 X1024 X1024 X1024
    X1024 X1024 X1024 X1024
    X1024 X1024 X1024 X1024
    X1024 X1024 X1024 X1024
    #undef X4
    #undef X16
    #undef X64
    #undef X256
    #undef X1024
};
static uint32_t BIG_RAM_BLOB[8192];
static volatile uint32_t sink = 0;

// Sample SPI0_ST while running a stress pattern.
struct Result {
    uint32_t cycles;
    uint32_t samples;
    uint32_t st_counts[8];
    uint32_t spi0_busy;
    uint32_t spi1_busy;
};

typedef void (*StressFn)();
static Result probe(StressFn stress, int n_samples);
static void print_result(const char* name, const Result& r);
static Result probe(StressFn stress, int n_samples) {
    Result r = {};
    uint32_t c0 = ESP.getCycleCount();

    // Run stress in parallel with sampling. We can't truly parallelize on a
    // single core, so we interleave : sample, then a small chunk of stress,
    // then sample again. To get high-res sampling we run a tight sampling
    // loop and trigger stress in the middle.
    //
    // Strategy : kick off stress on a separate task on the other core.
    // Simpler : do a few rounds of "stress + sample".
    for (int i = 0; i < n_samples; i++) {
        uint32_t s0 = spi0_st();
        uint32_t s1 = spi1_st();
        r.st_counts[s0]++;
        if (s0 != 0) r.spi0_busy++;
        if (s1 != 0) r.spi1_busy++;
        if ((i & 0xFF) == 0) stress();   // run stress in chunks
    }

    r.cycles = ESP.getCycleCount() - c0;
    r.samples = n_samples;
    return r;
}

static void stress_progmem() {
    uint32_t s = sink;
    for (size_t i = 0; i < 256; i++) {
        uint32_t w;
        memcpy_P(&w, BIG_FLASH_BLOB + (i * 64), sizeof(w));
        s += w;
    }
    sink = s;
}

static void stress_ram() {
    uint32_t s = sink;
    for (size_t i = 0; i < 256; i++) s += BIG_RAM_BLOB[i * 32];
    sink = s;
}

static void stress_idle() {
    // do nothing
    (void)sink;
}

static void print_result(const char* name, const Result& r) {
    Serial.print(name); Serial.print(F(":"));
    Serial.print(F(" cycles=")); Serial.print(r.cycles);
    Serial.print(F(" samples=")); Serial.print(r.samples);
    Serial.print(F(" SPI0_busy=")); Serial.print(r.spi0_busy);
    Serial.print(F(" ("));
    Serial.print(100.0f * r.spi0_busy / r.samples, 2);
    Serial.print(F("%) SPI1_busy=")); Serial.println(r.spi1_busy);
    Serial.print(F("  state distribution :"));
    for (int s = 0; s < 8; s++) {
        if (r.st_counts[s] > 0) {
            Serial.print(F(" ST=")); Serial.print(s);
            Serial.print(':'); Serial.print(r.st_counts[s]);
        }
    }
    Serial.println();
}

// Direct snapshot : just dump the raw register a few times to see if it's
// even changing without us doing anything.
static void raw_snapshot() {
    Serial.println(F("Raw EXT2 snapshots over 1 ms (no stress) :"));
    uint32_t end = micros() + 1000;
    int n = 0;
    while (micros() < end && n < 32) {
        uint32_t v0 = *(volatile uint32_t*)SPI0_EXT2_REG;
        uint32_t v1 = *(volatile uint32_t*)SPI1_EXT2_REG;
        Serial.print(F("  SPI0_EXT2=0x")); Serial.print(v0, HEX);
        Serial.print(F("  SPI1_EXT2=0x")); Serial.println(v1, HEX);
        n++;
        delayMicroseconds(30);
    }
}

void setup() {
    Serial.begin(115200);
    while (!Serial) delay(10);
    delay(500);
    Serial.println();
    Serial.println(F("=== SPI flash state machine probe ==="));

    for (size_t i = 0; i < 8192; i++) BIG_RAM_BLOB[i] = i * 1664525u;

    raw_snapshot();
    Serial.println();

    Serial.println(F("Sampling SPI0_ST 100k times under different stresses :"));
    Result r_idle    = probe(stress_idle,    100000);
    Result r_ram     = probe(stress_ram,     100000);
    Result r_progmem = probe(stress_progmem, 100000);

    print_result("idle    ", r_idle);
    print_result("ram     ", r_ram);
    print_result("progmem ", r_progmem);

    Serial.println();
    Serial.println(F("DONE."));
}

void loop() {}
