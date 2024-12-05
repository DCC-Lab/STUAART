#include "LoadCell.h"
#include "LoadCellController.h"
#include "HX711.h"


LoadCell loadCell;
LoadCellController controller;
const int SCK_PIN = 17; //clock des loadcell/HX711

void setup(){
  Serial.begin(115200);

  controller.add_loadcell(loadCell, 27, SCK_PIN); // loadcell number, dout, sck
  controller.set_all_loadcells_scale_coeff_n_readings(50);
  controller.set_all_loadcells_tare_n_readings(2);
  controller.set_all_loadcells_weight_n_readings(1);

  Serial.println("Starting in manual calibration mode");
  controller.tare_all_loadcells();
  controller.calibrate_all_loadcells();
}


void loop(){
  float weight_1 = controller.get_weight(1);

  Serial.print(F("Weight LoadCell 1: \t"));
  Serial.print(weight_1);
  Serial.println();

  delay(100);
}
