#include "SPI.h"
#include "SD.h"

#include "LoadCell.h"
#include "LoadCellController.h"


LoadCell loadcell_1;
LoadCell loadcell_2;
LoadCell loadcell_3;
LoadCellController controller;

const int sck_pin = 13; //clock des loadcell/HX711

//// FILE
// const bool file_writing = false;
// File myFile;

//// PINS
const byte SS_pin = 10;
const byte mode_pin = 8;

void setup(){
  Serial.begin(115200);
  controller.add_loadcell(loadcell_1, 11, SCK); // loadcell number, dout, sck
  controller.add_loadcell(loadcell_2, 3, sck_pin); // loadcell number, dout, sck
  controller.add_loadcell(loadcell_3, 5, sck_pin); // loadcell number, dout, sck
  controller.set_all_loadcells_scale_coeff_n_readings(50);
  controller.set_all_loadcells_tare_n_readings(2);
  controller.set_all_loadcells_weight_n_readings(1);

  if (digitalRead(mode_pin) == LOW)
  {
    Serial.println("Starting in auto mode");
    controller.tare_all_loadcells(false);
    controller.read_all_scale_coeff_from_persistent_memory();
  }
  else
  {
    Serial.println("Starting in manual calibration mode");
    controller.tare_all_loadcells();
    controller.calibrate_all_loadcells();
  }
}


void loop(){
  float weight_1 = controller.get_weight(1);
  float weight_2 = controller.get_weight(2);
  float weight_3 = controller.get_weight(3);

  Serial.print(F("Weight LoadCell 1: \t"));
  Serial.print(weight_1);
  Serial.print("\t\t\t");
  Serial.print(weight_2);
  Serial.print("\t\t\t");
  Serial.print(weight_3);
  Serial.println();

  delay(100);
}
