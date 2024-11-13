/**
* Sketch for the raw reading to characterize linearity of a load cell 100g with a FireBeetle ESP32.
* This sketch for experiment 3.1 in the lab notes
*
* This sketch averages 10 readings of the raw output before printing the averaged value.
*
* Nathan Bérubé, december 9 2023
*/


#include "LoadCell.h"
#include "LoadCellController.h"


LoadCell loadcell_1;


LoadCellController controller;

const byte mode_pin = D7;

void setup() 
{
  Serial.begin(115200);
  pinMode(mode_pin, INPUT_PULLUP);
  controller.add_loadcell(loadcell_1, D2, D3);
  controller.set_all_loadcells_weight_n_readings(10);
}


void loop()
{
  float output_1 = controller.read_raw_average(1);
  Serial.print(F("Output LoadCell 1: \t"));
  Serial.print(output_1);
  Serial.println();
}


