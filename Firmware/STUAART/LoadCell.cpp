#include <Arduino.h>
#include "LoadCell.h"
#include <SPI.h>

// TEENSYDUINO has a port of Dean Camera's ATOMIC_BLOCK macros for AVR to ARM Cortex M3.
#define HAS_ATOMIC_BLOCK (defined(ARDUINO_ARCH_AVR) || defined(TEENSYDUINO))

// Whether we are running on either the ESP8266 or the ESP32.
#define ARCH_ESPRESSIF (defined(ARDUINO_ARCH_ESP8266) || defined(ARDUINO_ARCH_ESP32))

// Whether we are actually running on FreeRTOS.
#define IS_FREE_RTOS defined(ARDUINO_ARCH_ESP32)

// Define macro designating whether we're running on a reasonable
// fast CPU and so should slow down sampling from GPIO.
#define FAST_CPU \
    ( \
    ARCH_ESPRESSIF || \
    defined(ARDUINO_ARCH_SAM)     || defined(ARDUINO_ARCH_SAMD) || \
    defined(ARDUINO_ARCH_STM32)   || defined(TEENSYDUINO) \
    )

#if HAS_ATOMIC_BLOCK
// Acquire AVR-specific ATOMIC_BLOCK(ATOMIC_RESTORESTATE) macro.
#include <util/atomic.h>
#endif

#if FAST_CPU
// // Make shiftIn() be aware of clockspeed for
// // faster CPUs like ESP32, Teensy 3.x and friends.
// // See also:
// // - https://github.com/bogde/HX711/issues/75
// // - https://github.com/arduino/Arduino/issues/6561
// // - https://community.hiveeyes.org/t/using-bogdans-canonical-hx711-library-on-the-esp32/539
// uint8_t shiftInSlow(uint8_t dataPin, uint8_t clockPin, uint8_t bitOrder) {
//     uint8_t value = 0;
//     uint8_t i;

//     for(i = 0; i < 8; ++i) {
//         digitalWrite(clockPin, HIGH);
//         delayMicroseconds(1);
//         if(bitOrder == LSBFIRST)
//             value |= digitalRead(dataPin) << i;
//         else
//             value |= digitalRead(dataPin) << (7 - i);
//         digitalWrite(clockPin, LOW);
//         delayMicroseconds(1);
//     }
//     return value;
// }
#define SHIFTIN_WITH_SPEED_SUPPORT(data,clock,order) shiftInSlow(data,clock,order)
#else
#define SHIFTIN_WITH_SPEED_SUPPORT(data,clock,order) shiftIn(data,clock,order)
#endif

#if ARCH_ESPRESSIF
// ESP8266 doesn't read values between 0x20000 and 0x30000 when DOUT is pulled up.
#define DOUT_MODE INPUT
#else
#define DOUT_MODE INPUT_PULLUP
#endif


// Forward declaration of the corruption-signature predicate. The full
// implementation, together with all the GPIO 9 / flash-bus mitigation
// machinery, lives at the bottom of this file (see "HX711 corruption
// mitigation" section). The averaging methods below need this helper
// to discard corrupted samples before they pollute the average, so it
// has to be visible up here.
static inline bool hx711_corrupted(long raw);


LoadCell::LoadCell() {
}


long LoadCell::read_raw_average() {
  // Average `weight_n_readings` reads, but exclude any sample that still
  // matches a corruption signature after safe_read's retries. Divide by
  // the number of GOOD samples so the average is not dragged toward 0xFFFFFF.
  // Returns -1L if every sample failed (caller treats as invalid).
  byte times = get_weight_n_readings();
  long sum = 0;
  byte good = 0;

	for (byte i = 0; i < times; i++) {
		long raw = safe_read();
		if (!hx711_corrupted(raw)) {
			sum += raw;
			good++;
		}
		delay(0);  // yield to the ESP32 watchdog / FreeRTOS scheduler
	}
	return good > 0 ? sum / good : -1L;
}

long LoadCell::read_tare_average() {
  // Same shape as read_raw_average() but driven by `tare_n_readings`.
  // Used during the boot tare in auto mode ; keeping the corruption
  // filter here is critical because a corrupted tare offset poisons
  // every subsequent weight reading until a manual `tare` from Serial.
  byte times = get_tare_n_readings();
  long sum = 0;
  byte good = 0;

	for (byte i = 0; i < times; i++) {
		long raw = safe_read();
		if (!hx711_corrupted(raw)) {
			sum += raw;
			good++;
		}
		delay(0);
	}
	return good > 0 ? sum / good : -1L;
}

long LoadCell::read_scale_coeff_average() {
  // Same shape as read_raw_average() but driven by `scale_coeff_n_readings`.
  // Used during the `cal <n> <w>` calibration sequence to compute
  // scale = (raw - offset) / w with a stable raw average.
  byte times = get_scale_coeff_n_readings();
  long sum = 0;
  byte good = 0;

	for (byte i = 0; i < times; i++) {
		long raw = safe_read();
		if (!hx711_corrupted(raw)) {
			sum += raw;
			good++;
		}
		delay(0);
	}
	return good > 0 ? sum / good : -1L;
}

// `raw - offset` : the deviation of the current ADC reading from the
// stored tare reference. Used inside get_weight() ; rarely called directly.
double LoadCell::get_raw_value() {
  return read_raw_average() - get_offset();
}

// Convert the deviation to grams via the stored scale coefficient.
// Note that scale can be either positive or negative depending on
// the polarity of the load cell wiring (E+/E-/A+/A- swap).
float LoadCell::get_weight() {
  return get_raw_value()/get_scale();
}

// Re-read the current raw output as the new zero offset. Caller must
// ensure the cell is empty before calling.
void LoadCell::tare() {
  double offset = read_tare_average();
  set_offset(offset);
}

// All three n_readings setters share the same clamp logic : the field
// is a `byte` so the upper bound is 255 ; non-positive values would
// cause a divide-by-zero in the averaging loops, so clamp to 1.
void LoadCell::set_tare_n_readings(int n_readings){
  if (n_readings <= 0){
    tare_n_readings = 1;
  }
  else if (n_readings >= 255) {
    tare_n_readings = 255;
  }
  else {tare_n_readings = n_readings;}
}

int LoadCell::get_tare_n_readings(){
  return tare_n_readings;
}

void LoadCell::set_scale_coeff_n_readings(int n_readings){
  if (n_readings <= 0){
    scale_coeff_n_readings = 1;
  }
  else if (n_readings >= 255) {
    scale_coeff_n_readings = 255;
  }
  else {scale_coeff_n_readings = n_readings;}
}

int LoadCell::get_scale_coeff_n_readings(){
  return scale_coeff_n_readings;
}


void LoadCell::set_weight_n_readings(int n_readings){
  if (n_readings <= 0){
    weight_n_readings = 1;
  }
    else if (n_readings >= 255) {
    weight_n_readings = 255;
  }
  else {weight_n_readings = n_readings;}
}

int LoadCell::get_weight_n_readings(){
  return weight_n_readings;
}


// ============================================================================
// HX711 corruption mitigation : everything below this banner exists solely to
// work around the STUAART V2 PCB error that wires HX711 cell 1 DOUT to GPIO 9
// (= ESP32 SD_DATA2 of the on-package SPI flash). On future PCB revisions
// that route DOUT off GPIO 6-11 entirely, `needs_flash_collision_protection()`
// returns false on every cell, `safe_read()` collapses to a direct call into
// `HX711::read()`, and none of the machinery below is exercised at runtime.
//
// Background : on the ESP32-D0WD die, GPIO 6 to 11 are physically bonded to
// the external SPI flash bus. The flash controller drives those pads on every
// cache miss, in parallel with the HX711 pulling its DOUT to that same pad.
// The two drivers fight, and the read occasionally samples the flash signal
// instead of the HX711 data.
//
// In ~98 % of the corrupted reads observed on STUAART production data the
// HX711 returns 0xFFFFFF (= -1L after sign extension), the signature of a
// DOUT held HIGH for the entire 24-bit shift. Two saturation values
// (0x800000 and 0x7FFFFF) appear less frequently when the boot tare hits a
// fully-corrupted read. None of these values can physically occur during
// normal operation of a strain-gauge load cell weighing a 20-30 g mouse, so
// they make a reliable signature.
//
// Two layers of protection on cells whose DOUT lands on GPIO 6-11 :
//
//   1. `HX711::read()` and `HX711::_shiftIn()` are patched in the local copy
//      of the bogde HX711 library to live in IRAM (`IRAM_ATTR`). Combined
//      with arduino-esp32 already keeping `digitalRead` / `digitalWrite` /
//      `delayMicroseconds` in IRAM (`ARDUINO_ISR_ATTR`), the entire HX711
//      read path is now flash-free : no instruction fetched from flash
//      during the 24-bit shift, no flash bus burst that could corrupt DOUT.
//
//   2. The actual `read()` call is wrapped in a `portENTER_CRITICAL` section
//      so no FreeRTOS task switch and no ISR can interrupt the shift. ISR
//      handlers usually live in flash and would themselves trigger a flash
//      burst the moment they run.
//
// Layer 2 is gated by `needs_flash_collision_protection()` so it costs zero
// on clean cells. Layer 1 is unconditional but is just code placement, no
// runtime cost.
//
// `safe_read()` retries up to `max_retries` times when a known corruption
// signature appears, and increments per-signature lifetime counters so the
// corruption rate of each cell can be inspected at runtime via the `stats`
// serial command.
// ============================================================================

static inline bool hx711_corrupted(long raw) {
  // 0xFFFFFF (-1)        : DOUT held HIGH (interrupt running from flash, or
  //                        flash-bus contention on GPIO 9 — the dominant
  //                        case on STUAART V2).
  // 0x800000 (-8388608)  : 24-bit negative saturation, mostly seen when the
  //                        boot tare hits a fully-corrupted read.
  // 0x7FFFFF (+8388607)  : 24-bit positive saturation, mirror image.
  return raw == -1L || raw == -8388608L || raw == 8388607L;
}

// Helper : increment the matching corruption counter for a value that
// already failed hx711_corrupted().
inline void LoadCell_count_corruption(LoadCell* self, long raw) {
  if      (raw == -1L)        self->corrupted_neg1++;
  else if (raw == -8388608L)  self->corrupted_negsat++;
  else if (raw == 8388607L)   self->corrupted_possat++;
}

#if defined(STUAART_v5_CORRUPTED_GPIO9)

#include "freertos/FreeRTOS.h"

// Override of `HX711::begin` that mirrors the DOUT pin into our public
// `pin_dout` field so `needs_flash_collision_protection()` can inspect
// it without touching the bogde private state.
void LoadCell::begin(uint8_t dout, uint8_t sck, uint8_t gain) {
    pin_dout = dout;
    HX711::begin(dout, sck, gain);
}

static portMUX_TYPE _stuaart_hx_mux = portMUX_INITIALIZER_UNLOCKED;

// Hardened read used only when DOUT lands on GPIO 6-11. Each underlying
// HX711::read() runs inside a critical section so no ISR can fire mid
// 24-bit shift, and the result is filtered against the three known
// corruption signatures with up to `max_retries` retries.
static long safe_read_hardened(LoadCell* self, byte max_retries) {
    long raw;
    portENTER_CRITICAL(&_stuaart_hx_mux);
    raw = self->read();
    portEXIT_CRITICAL(&_stuaart_hx_mux);
    self->total_reads++;
    while (hx711_corrupted(raw) && max_retries > 0) {
        LoadCell_count_corruption(self, raw);
        portENTER_CRITICAL(&_stuaart_hx_mux);
        raw = self->read();
        portEXIT_CRITICAL(&_stuaart_hx_mux);
        self->total_reads++;
        max_retries--;
    }
    if (hx711_corrupted(raw)) {
        LoadCell_count_corruption(self, raw);
    }
    return raw;
}

// Public dispatcher. Clean cells (DOUT not on GPIO 6-11) get a direct
// call into the bogde `HX711::read()` with zero overhead — no critical
// section, no signature filter, no retry, no stats. Hardened cells go
// through `safe_read_hardened()` above.
long LoadCell::safe_read(byte max_retries) {
    if (!needs_flash_collision_protection()) {
        return read();
    }
    return safe_read_hardened(this, max_retries);
}

#else  // STUAART_v5_CORRUPTED_GPIO9 not defined : the PCB is clean,
       // so safe_read collapses to a direct read() with zero overhead
       // and `LoadCell::begin` is inherited from HX711 unchanged.

long LoadCell::safe_read(byte /*max_retries*/) {
    return read();
}

#endif
