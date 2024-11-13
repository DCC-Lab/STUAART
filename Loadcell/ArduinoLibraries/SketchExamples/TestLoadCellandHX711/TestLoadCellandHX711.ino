/**
* Sketch to use when verifying if a load cell or an HX711 is working and can be used
* 
* This code calibrates the LoadCell manually and does a weight reading with a recalibration of the offset when empty.
* Only one known weight should be used for calibration since we only need to verify if the components are working. We don't need a lot of precision.
*
* To verify if all the components work, you should be able to place a known weight on the scale and see a reliable measurement by the
* load cell. If the reading is 0 or nan, the load cell or the HX711 doesn't work and it should be swapped by a functional one to isolate the problem.
*/


#include "LoadCell.h"
#include "LoadCellController.h"
#include "SD.h"
#include "SPI.h"


LoadCell loadcell_1;
LoadCellController controller;

void setup() 
{
  Serial.begin(115200);
  controller.add_loadcell(loadcell_1, 3, 13);
  controller.set_all_loadcells_scale_coeff_n_readings(50);
  controller.set_all_loadcells_tare_n_readings(10);
  controller.set_all_loadcells_weight_n_readings(10);

  Serial.println("Starting in manual calibration mode");
  controller.tare_all_loadcells();
  controller.calibrate_all_loadcells();
}


void loop()
{

  float weight_1 = controller.get_weight_with_auto_recalibration(1);

  Serial.print(F("Weight LoadCell 1: \t"));
  Serial.print(weight_1);
  Serial.print("\t\t\t");
  Serial.println();
}