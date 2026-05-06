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

static inline bool hx711_corrupted(long raw) {
  // 0xFFFFFF (-1) : DOUT held HIGH (interrupt, flash bus)
  // 0x800000 (-8388608) : 24-bit negative saturation
  // 0x7FFFFF (+8388607) : 24-bit positive saturation
  // None of these can occur during normal operation of a mouse-scale load cell.
  return raw == -1L || raw == -8388608L || raw == 8388607L;
}

long LoadCell::safe_read(byte max_retries) {
  long raw = read();
  for (byte i = 0; hx711_corrupted(raw) && i < max_retries; i++) {
    raw = read();
  }
  return raw;
}

long LoadCell::read_raw_average() {
  byte times = get_weight_n_readings();
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

long LoadCell::read_tare_average() {
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

double LoadCell::get_raw_value() {
  return read_raw_average() - get_offset();
}

float LoadCell::get_weight() {
  return get_raw_value()/get_scale();
}

void LoadCell::tare() {
  double offset = read_tare_average();
  set_offset(offset);
}

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