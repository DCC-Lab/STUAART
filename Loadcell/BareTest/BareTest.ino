#include "LoadCell.h"
#include "LoadCellController.h"
#include "SD.h"
#include "SPI.h"

LoadCell loadcell_1;
// LoadCell loadcell_2;
// LoadCell loadcell_3;
LoadCellController controller;

const int sck_pin = 13; //clock des loadcell/HX711

//// FILE
const bool file_writing = false;
const char file_name[50] = "/20240917_2.csv";
File myFile;

//// PINS
const byte SS_pin = 10;
// const byte mode_pin = 8;

void setup()
{
  Serial.begin(115200);
  // pinMode(mode_pin, HIGH);
  controller.add_loadcell(loadcell_1, 11, sck_pin); // loadcell number, dout, sck
  // controller.add_loadcell(loadcell_2, 3, sck_pin); // loadcell number, dout, sck
  // controller.add_loadcell(loadcell_3, 5, sck_pin); // loadcell number, dout, sck
  controller.set_all_loadcells_scale_coeff_n_readings(50);
  controller.set_all_loadcells_tare_n_readings(2);
  controller.set_all_loadcells_weight_n_readings(1);

  // if (digitalRead(mode_pin) == LOW)
  // {
  //   Serial.println("Starting in auto mode");
  //   controller.tare_all_loadcells(false);
  //   controller.read_all_scale_coeff_from_persistent_memory();
  // }
  // else
  // {
  Serial.println("Starting in manual calibration mode");
  controller.tare_all_loadcells();
  controller.calibrate_all_loadcells();
  // }

  // if (file_writing)
  // {
  //     write_file_heading();
  // }
}


void loop()
{
  float weight_1 = controller.get_weight(1);
  // float weight_2 = controller.get_weight(2);
  // float weight_3 = controller.get_weight(3);

  Serial.print(F("Weight LoadCell 1: \t"));
  Serial.print(weight_1);
  // Serial.print("\t\t\t");
  // Serial.print(weight_2);
  // Serial.print("\t\t\t");
  // Serial.print(weight_3);
  Serial.println();

    // if (file_writing)
  // {
      // file_write(weight_1, weight_2);
  //     file_write(weight_1);
  // }

  delay(100);
}


// void file_write(float reading_1, float reading_2, float reading_3) {
// void file_write(float reading_1, float reading_2) {
void file_write(float reading_1) {

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
    // myFile = SD.open(file_name, O_APPEND);
    myFile = SD.open(file_name, FILE_WRITE);

    // if the file opened okay, write to it:
    if (myFile) {
      Serial.print(F("Writing to file..."));
      myFile.print(millis());
      myFile.print(F(","));
      myFile.print(reading_1);
      // myFile.print(F(","));
      // myFile.print(reading_2);
      // myFile.print(F(","));
      // myFile.print(reading_3);
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
    // myFile = SD.open(file_name, O_WRITE);
    // myFile = SD.open(file_name, O_APPEND);

    // if the file opened okay, write to it:
    if (myFile) {
      Serial.print(F("Writing heading..."));
      myFile.print(F("time (ms), reading 1, reading 2, reading 3"));
      myFile.println();
      // close the file:
      myFile.close();
      Serial.println(F("done."));
    } else {
      // if the file didn't open, print an error:
      Serial.println(F("error opening file"));
    }
}
