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



LoadCell::LoadCell() {
}

// ----------------------------------------------------------------------------
// HX711 corruption mitigation
//
// Background : the STUAART V2 PCB routes cell 1 DOUT to the FireBeetle pin
// labelled D5 (= ESP32 GPIO 9). On the ESP32-D0WD die, GPIO 6 to 11 are
// physically bonded to the external SPI flash bus. The flash controller
// drives those pads on every CPU cache miss, in parallel with the HX711
// pulling its DOUT to that same pad. The two drivers fight, and the read
// occasionally samples the flash signal instead of the HX711 data.
//
// In ~98 % of the corrupted reads observed on STUAART production data the
// HX711 returns 0xFFFFFF (= -1L after sign extension), the signature of a
// DOUT held HIGH for the entire 24-bit shift. Two saturation values
// (0x800000 and 0x7FFFFF) appear less frequently when the boot tare hits
// a fully-corrupted read.
//
// The proper fix is a hardware strap rerouting cell 1 DOUT off GPIO 9 to
// a free pin (D2 = GPIO 25 or D3 = GPIO 26 are unconnected on V2). Until
// every board is reworked, this software mitigation drops the three known
// corruption signatures so they never enter the data stream.
// ----------------------------------------------------------------------------

static inline bool hx711_corrupted(long raw) {
  // 0xFFFFFF (-1) : DOUT held HIGH (interrupt, or flash-bus contention on
  //                 GPIO 9 — the dominant case on STUAART V2).
  // 0x800000 (-8388608) : 24-bit negative saturation, mostly seen when
  //                       the boot tare hits a fully-corrupted read.
  // 0x7FFFFF (+8388607) : 24-bit positive saturation, mirror image.
  // None of these can physically occur during normal operation of a
  // strain-gauge load cell weighing a 20-30 g mouse.
  return raw == -1L || raw == -8388608L || raw == 8388607L;
}

// Helper : increment the matching corruption counter for a value that
// already failed hx711_corrupted().
inline void LoadCell_count_corruption(LoadCell* self, long raw) {
  if      (raw == -1L)        self->corrupted_neg1++;
  else if (raw == -8388608L)  self->corrupted_negsat++;
  else if (raw == 8388607L)   self->corrupted_possat++;
}

long LoadCell::safe_read(byte max_retries) {
  // First read. If it matches a known corruption signature, retry up to
  // max_retries times. read() blocks until the HX711 has a fresh sample
  // ready (~12.5 ms at 80 Hz) so each retry costs at most one conversion
  // period. We do NOT add an extra wait_ready_timeout here : a previous
  // version did, and it dragged the loop rate from ~85 Hz to ~1 Hz when
  // cell 1 was corrupted on every iteration.
  //
  // Every read() call counts toward total_reads ; every observed
  // corruption signature (whether on the initial read or a retry)
  // increments the matching corrupted_* counter, so the lifetime stats
  // give a faithful corruption rate per cell.
  long raw = read();
  total_reads++;
  while (hx711_corrupted(raw) && max_retries > 0) {
    LoadCell_count_corruption(this, raw);
    raw = read();
    total_reads++;
    max_retries--;
  }
  // If we are exiting with a still-corrupt value, count it once more.
  if (hx711_corrupted(raw)) {
    LoadCell_count_corruption(this, raw);
  }
  return raw;
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