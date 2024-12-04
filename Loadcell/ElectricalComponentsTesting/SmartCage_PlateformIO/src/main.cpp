#include "SPI.h"
#include "SD.h"

#include "LoadCell.h"
#include "LoadCellController.h"


LoadCell loadcell_1;
LoadCellController controller;

const int sck_pin = 13; //clock des loadcell/HX711

// Misc variables
// float offset = 0;


void setup(){
  Serial.begin(115200);
  controller.add_loadcell(loadcell_1, 5, sck_pin); // loadcell number, dout, sck
  // controller.add_loadcell(loadcell_1, 11, SCK); // loadcell number, dout, sck
  controller.set_all_loadcells_scale_coeff_n_readings(50);
  controller.set_all_loadcells_tare_n_readings(2);
  controller.set_all_loadcells_weight_n_readings(1);

  // Automatic callibrations (if already callibrated through manual mode)
  // Serial.println("Starting in auto mode");
  // controller.tare_all_loadcells(false);
  // controller.read_all_scale_coeff_from_persistent_memory();

  // Manual calibration
  Serial.println("Starting in manual calibration mode");
  // controller.tare_all_loadcells();
  // controller.calibrate_all_loadcells();

  // Wait for user to be ready
  Serial.println(F("---------***---------"));
  Serial.println(F("\nReady to acquire, send 'a' to proceed ?"));
  bool _resume = false;
  while (_resume == false)
    {
      if (Serial.available() > 0)
      {
          char serial_reading = Serial.read();
          if (serial_reading == 'a')
          {
              Serial.println(F("Starting acquisitions..."));
              _resume = true;
          }
      }
    }

  // For test with inputs at GND, correct offset due to missing loadcell
  // offset = controller.get_weight(1);
}


void loop(){
  // float weight_1 = controller.get_weight(1) - offset;
  float weight_1 = controller.get_weight(1);

  Serial.print(F("Weight LoadCell 1: \t"));
  Serial.print(weight_1);
  Serial.println();
  delay(1000);
}
