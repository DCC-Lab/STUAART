/**
* Sketch to use two load cells at the same time and output the raw measurements.
* March 30 2025
*/


#include "LoadCell.h"
#include "LoadCellController.h"
#include "SD.h"
#include "SPI.h"


LoadCell loadcell_1;
LoadCell loadcell_2;
LoadCellController controller;

void setup() 
{
  Serial.begin(115200);
  controller.add_loadcell(loadcell_1, 2, 3);
  controller.add_loadcell(loadcell_2, 4, 5);

  controller.set_all_loadcells_weight_n_readings(1);
}


void loop()
{

  float raw_1 = controller.read_raw_average(1);
  float raw_2 = controller.read_raw_average(2);

  Serial.print(F("Raw LoadCell 1: \t"));
  Serial.print(raw_1);
  Serial.print("\t\t\t");
  Serial.println();
  Serial.print(F("Raw LoadCell 2: \t"));
  Serial.print(raw_2);
  Serial.print("\t\t\t");
  Serial.println();
}