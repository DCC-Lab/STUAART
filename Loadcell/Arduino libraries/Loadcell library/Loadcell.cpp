/**
 *
 * HX711 library for Arduino
 * https://github.com/bogde/HX711
 *
 * MIT License
 * (c) 2018 Bogdan Necula
 *
**/
#include <Arduino.h>
#include "Loadcell.h"
#include <SPI.h>
#include <SD.h>

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
// Make shiftIn() be aware of clockspeed for
// faster CPUs like ESP32, Teensy 3.x and friends.
// See also:
// - https://github.com/bogde/HX711/issues/75
// - https://github.com/arduino/Arduino/issues/6561
// - https://community.hiveeyes.org/t/using-bogdans-canonical-hx711-library-on-the-esp32/539
uint8_t shiftInSlow(uint8_t dataPin, uint8_t clockPin, uint8_t bitOrder) {
    uint8_t value = 0;
    uint8_t i;

    for(i = 0; i < 8; ++i) {
        digitalWrite(clockPin, HIGH);
        delayMicroseconds(1);
        if(bitOrder == LSBFIRST)
            value |= digitalRead(dataPin) << i;
        else
            value |= digitalRead(dataPin) << (7 - i);
        digitalWrite(clockPin, LOW);
        delayMicroseconds(1);
    }
    return value;
}
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

// tout ce qui est au-dessus est au début du fichier .ccp de la librarie HX711 de laquelle Loadcell est dérivée.


Loadcell::Loadcell() {
}

// void Loadcell::easy_start(byte dout, byte pd_sck, byte gain, bool calibrate_tare, bool calibrate_scale){
//   begin(dout, pd_sck, gain);
// }

// void Loadcell::start(byte dout, byte pd_sck, byte gain, bool calibrate) {
//   begin(dout, pd_sck, gain);
// }

// void Loadcell::calibrate_all(){
//   Serial.println("***");
//   Serial.println("Start calibration:");
//   calibrate_tare_offset();
//   delay(500);
//   calibrate_scale_coeff();
//   delay(500);
//   Serial.println("Calibration of tare offset and scale coeff is done.");
//   Serial.println("---------***---------");
// }

// void Loadcell::calibrate_tare_offset() {
//   double tare_offset = determine_tare_offset();
//   set_offset(tare_offset);
// }

// void Loadcell::calibrate_scale_coeff() {
//   double scale_coeff = determine_scale_coeff();
//   set_scale(scale_coeff);
// }

// double Loadcell::determine_tare_offset() {
//   Serial.println("---------***---------");
//   Serial.println("Determination of the tare offset");
//   Serial.println("---------***---------");
//   Serial.println("Remove any load applied to the load cell.");
//   Serial.println("Send 't' from serial monitor to set the tare offset.");
//   delay(3000); // delay to allow stabilization of the output before tare
//   bool _resume = false;
//   while(_resume == false){
//     if (Serial.available() > 0){
//       char serial_reading = Serial.read();
//       if (serial_reading == 't'){
//         Serial.println("Reading...");
//         double tare_offset = read_average(tare_n_readings);;
//         Serial.print("Tare offset is");
//         Serial.println(tare_offset);
//         _resume = true;
//         return tare_offset;
//       }
//     }
//   }
// }

// double Loadcell::determine_scale_coeff(){
//   Serial.println("---------***---------");
//   Serial.println("Determination of the scale coeff");
//   Serial.println("---------***---------");
//   Serial.println("Send with the serial monitor how many weights will be used to calibrate the loadcell.");
//   int num_weights = 0;
//   bool _resume = false;
//   while(_resume == false){
//     if (Serial.available() > 0){
//       num_weights = Serial.parseInt();
//       if (num_weights!= 0) {
//         Serial.println("---------***---------");
//         Serial.print(num_weights);
//         Serial.println(" calibration weight(s) will be used to determine scale coeff.");
//         _resume = true;
//       }
//     }
//   }
//   float scale_coeff_sum = 0;
//   for (int i=1; i<(num_weights+1); i++){
//     Serial.println("---------***---------");
//     Serial.print("Place weight #");
//     Serial.print(i);
//     Serial.println(" on the loadcell.");
//     Serial.println("Then send its weight from serial monitor.");
//     float known_mass = 0;
//     _resume = false;
//     while(_resume == false){
//       if (Serial.available() > 0){
//         known_mass = Serial.parseFloat();
//         if (known_mass != 0) {
//           Serial.print("Known mass is: ");
//           Serial.println(known_mass);
//           _resume = true;
//         }
//       }
//     }
//   delay(2000); // delay before beginning readings for stabilization of the output
//   float known_output = read_average(scale_coeff_n_readings);
//   float mass_scale_coeff = calculate_scale_coeff(known_output, known_mass);
//   Serial.print("The scale coefficient for this mass is ");
//   Serial.println(mass_scale_coeff);
//   scale_coeff_sum += mass_scale_coeff;
//   } 
//   double scale_coeff = scale_coeff_sum/num_weights;
//   Serial.print("Scale calibration coefficient is set to: ");
//   Serial.println(scale_coeff);
//   Serial.println("---------***---------");
//   return scale_coeff;
// }

// float Loadcell::calculate_scale_coeff(float output, float mass){
//   return (output - get_offset())/mass;
// }




long Loadcell::read_average() {
  byte times = get_weight_n_readings();
  long sum = 0;

	for (byte i = 0; i < times; i++) {
		sum += read();
		delay(0);
	}
	return sum / times;
}

double Loadcell::get_value() {
  return read_average() - get_offset();
}

float Loadcell::get_weight() {
  return get_value()/get_scale();
}

void Loadcell::tare() {
  double offset = read_average();
  set_offset(offset);
}

void Loadcell::set_tare_n_readings(int n_readings){
  if (n_readings <= 0){
    tare_n_readings = 1;
  }
  else if (n_readings >= 255) {
    tare_n_readings = 255;
  }
  else {tare_n_readings = n_readings;}
}

int Loadcell::get_tare_n_readings(){
  return tare_n_readings;
}

void Loadcell::set_scale_coeff_n_readings(int n_readings){
  if (n_readings <= 0){
    scale_coeff_n_readings = 1;
  }
  else if (n_readings >= 255) {
    scale_coeff_n_readings = 255;
  }
  else {scale_coeff_n_readings = n_readings;}
}

int Loadcell::get_scale_coeff_n_readings(){
  return scale_coeff_n_readings;
}

void Loadcell::set_weight_n_readings(int n_readings){
  if (n_readings <= 0){
    weight_n_readings = 1;
  }
    else if (n_readings >= 255) {
    weight_n_readings = 255;
  }
  else {weight_n_readings = n_readings;}
}

int Loadcell::get_weight_n_readings(){
  return weight_n_readings;
}