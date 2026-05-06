/**
* Sketch for the weight reading of a load cell. The calibration was done
* before and the calibration parameters were saved on the EEPROM.
* 
* The load cell is started through the controller with the easy_start_with_params()
* function. 
* 
*
* 
*/


#include "LoadCell.h"
#include "LoadCellController.h"
#include "SD.h"
#include "SPI.h"


LoadCell loadcell_1;


LoadCellController controller;

//// FILE
const bool file_writing = false;
const char file_name[50] = "20231808.csv";
File myFile;

//// PARAMETERS
const int mouse_weight = 20;

//// VARIABLES
long reading_sum;
long reading;
bool tare;
float weight_1;
byte i;

const byte SS_pin = 4;

void setup() {
  Serial.begin(115200);
  controller.add_loadcell(loadcell_1);
  controller.set_all_loadcells_scale_coeff_n_readings(50);
  controller.set_all_loadcells_tare_n_readings(20);
  controller.set_all_loadcells_weight_n_readings(10);
  controller.easy_start_with_params(
                                    1,         // loadcell_number
                                    D4,         // dout pin
                                    D2,         // sck pin
                                    true,      // calibrate offset
                                    true,      // calibrate scale
                                    false,     // read offset eeprom
                                    false,     // read scale eeprom
                                    true,      // save offset eeprom
                                    true,      // save scale eeprom
                                    0,         // tare offset
                                    0,         // scale coeff
                                    128        // gain
                                 );
  if (file_writing) {
        write_file_heading();
  }
}

void loop() {

  ////LOADCELL1
  while(!loadcell_1.is_ready());

  i = 0;
  reading_sum = 0;
  tare = true;

  // average tare_n_readings for mesurements of new tare offset
  for (i; i < loadcell_1.get_tare_n_readings(); i++) {
    reading = loadcell_1.read();

  // if a measurement is above a threshold, here 1/3 of the mouse weight
  // the tare is cancelled
    if (mass_from_raw(reading) > mouse_weight/3) {
      tare = false;
      break;
    }
    reading_sum += reading;
  }

  // if no mouse came on the scale, we set the new offset to the average value
  if (tare) {
    Serial.println(F("*** TARE 1***"));
    loadcell_1.set_offset(reading_sum/loadcell_1.get_tare_n_readings());
    weight_1 = mass_from_raw(reading_sum/loadcell_1.get_tare_n_readings());
  }
  // if a mouse came, we perform a reading of its weight relative to the previous offset
  else {
    weight_1 = loadcell_1.get_weight();
  }

  Serial.print("Weight: \t\t");
  Serial.println(weight_1);

  if (file_writing) {
      file_write(weight_1, loadcell_1.get_offset());
  }
}

void file_write(float reading_1,long offset_1) {

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
      Serial.print(F("Writing to file..."));
      myFile.print(millis());
      myFile.print(F(","));
      myFile.print(reading_1);
      myFile.print(F(","));
      myFile.print(offset_1);
      myFile.println();
      // close the file:
      myFile.close();
      Serial.println(F("done."));
    } else {
      // if the file didn't open, print an error:
      Serial.println(F("error opening data.csv"));
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
      myFile.print("time (ms)");
      myFile.print(F(","));
      myFile.print("reading 1");
      myFile.print(F(","));
      myFile.print("offset 1");
      myFile.println();
      // close the file:
      myFile.close();
      Serial.println(F("done."));
    } else {
      // if the file didn't open, print an error:
      Serial.println(F("error opening data.csv"));
    }
}

float mass_from_raw(long raw) {
  return (raw - loadcell_1.get_offset())/loadcell_1.get_scale();
}