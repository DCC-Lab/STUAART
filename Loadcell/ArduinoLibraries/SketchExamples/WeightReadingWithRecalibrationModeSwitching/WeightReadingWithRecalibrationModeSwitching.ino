/**
* Sketch for the weight reading of two LoadCells.
* This sketch offers two mode of start-up depending on the calibration prerequisites:
*   - Automatic start-up when no computer is connected. The tare is automatic and the scale 
*     coefficients are read from peristent memory automatically
*
*   -  Manual start-up when a computer is connected. The tare is done manually by the user
*      and the scale coefficient is calibrated for each LoadCell
*
* This sketch allows to select which mode by an external switch connected to Vcc and mode_pin (see variables).
*
* If the switch is opened, the mode_pin is HIGH and the automatic start-up is selected
* If the switch is closed, the mode_pin is LOW and the manual start-up is selected
*
* WARNING: This code will delete the file with the same name as file_name if there is one.
 Comment line 67 (write_file_heading()) to prevent this. The data will be written below the
* previous ones in the already existing file.
*/


#include "LoadCell.h"
#include "LoadCellController.h"
#include "SD.h"
#include "SPI.h"


LoadCell loadcell_1;
LoadCell loadcell_2;


LoadCellController controller;

//// FILE
const bool file_writing = true;
const char file_name[50] = "/test_1.csv";
File myFile;

//// PINS
const byte SS_pin = D6;
const byte mode_pin = D7;

void setup() 
{
  Serial.begin(115200);
  pinMode(mode_pin, INPUT_PULLUP);
  controller.add_loadcell(loadcell_1, D2, D3);
  controller.add_loadcell(loadcell_2, D4, D5);
  controller.set_all_loadcells_scale_coeff_n_readings(50);
  controller.set_all_loadcells_tare_n_readings(10);
  controller.set_all_loadcells_weight_n_readings(10);

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

  if (file_writing) 
  {
      write_file_heading();
  }
}


void loop()
{

  float weight_1 = controller.get_weight_with_auto_recalibration(1);
  float weight_2 = controller.get_weight_with_auto_recalibration(2);

  Serial.print(F("Weight LoadCell 1: \t"));
  Serial.print(weight_1);
  Serial.print("\t\t\t");
  Serial.print(F("Weight LoadCell 2: \t"));
  Serial.print(weight_2);
  Serial.println();
  if (file_writing)
  {
      file_write(weight_1, weight_2);
  }
}



void file_write(float reading_1, float reading_2) {

    while (!Serial) {
    ; // wait for serial port to connect. Needed for native USB port only
    }

    Serial.print(F("Initializing SD card..."));

    if (!SD.begin(SS_pin)) {
      Serial.println(F("initialization failed!"));
      while (1);
    }
    Serial.println(F("initialization done."));

    // open the file. note that only one file can be open at a time,
    // so you have to close this one before opening another.
    myFile = SD.open(file_name, FILE_APPEND);

    // if the file opened okay, write to it:
    if (myFile) {
      Serial.print(F("Writing to file..."));
      myFile.print(millis());
      myFile.print(F(","));
      myFile.print(reading_1);
      myFile.print(F(","));
      myFile.print(reading_2);
      myFile.println();
      // close the file:
      myFile.close();
      Serial.println(F("done."));
    } else {
      // if the file didn't open, print an error:
      Serial.println(F("error opening file"));
    }
}


void write_file_heading() {
      while (!Serial) {
    ; // wait for serial port to connect. Needed for native USB port only
    }

    Serial.print(F("Initializing SD card..."));

    if (!SD.begin(SS_pin)) {
      Serial.println(F("initialization failed!"));
      while (1);
    }
    Serial.println(F("initialization done."));

    // open the file. note that only one file can be open at a time,
    // so you have to close this one before opening another.
    myFile = SD.open(file_name, FILE_WRITE);

    // if the file opened okay, write to it:
    if (myFile) {
      Serial.print(F("Writing heading..."));
      myFile.print(F("time (ms)"));
      myFile.print(F(","));
      myFile.print(F("reading 1"));
      myFile.print(F(","));
      myFile.print(F("reading 2"));
      myFile.println();
      // close the file:
      myFile.close();
      Serial.println(F("done."));
    } else {
      // if the file didn't open, print an error:
      Serial.println(F("error opening file"));
    }
}