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