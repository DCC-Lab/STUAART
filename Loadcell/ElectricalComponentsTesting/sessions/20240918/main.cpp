#include "SPI.h"
#include "SD.h"

#include "LoadCell.h"
#include "LoadCellController.h"


LoadCell loadcell_1;
LoadCellController controller;


void setup(){
  Serial.begin(115200);
  controller.add_loadcell(loadcell_1, 11, SCK); // loadcell number, dout, sck
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
