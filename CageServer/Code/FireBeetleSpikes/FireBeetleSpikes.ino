#include "HX711.h"
#include "LoadCell.h"
#include "LoadCellController.h"


LoadCell loadCell1;
LoadCell loadCell2;
LoadCell loadCell3;
LoadCellController controller;
const int SCK_PIN = 17; //clock des loadcell/HX711
const int SS_PIN = 21; // seule pin de carte SD à spécifier

void setup(){
  Serial.begin(115200);

  controller.add_loadcell(loadCell1, 27, SCK_PIN); // loadcell number, dout, sck
  controller.add_loadcell(loadCell2, 9, 16); // loadcell number, dout, sck
  // controller.add_loadcell(loadCell3, 5, SCK_PIN); // loadcell number, dout, sck
  controller.set_all_loadcells_scale_coeff_n_readings(50);
  controller.set_all_loadcells_tare_n_readings(2);
  controller.set_all_loadcells_weight_n_readings(1);

  Serial.println("Starting in manual calibration mode");
  Serial.println(FAST_CPU);
  controller.tare_all_loadcells();
  controller.calibrate_all_loadcells();
}


void loop(){
  float weight_1 = controller.get_weight(1);
  float weight_2 = controller.get_weight(2);
  // float weight_3 = controller.get_weight(3);

  Serial.print(F("Weight LoadCell 1 2 3: \t,"));
  Serial.print(weight_1);
  Serial.print(",");
  Serial.print(weight_2);
  // Serial.print(",");
  // Serial.print(weight_3);
  Serial.println();

  delay(0);
}
