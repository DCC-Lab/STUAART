// Arduino sketch to calibrate and read value from loadcell and HX711 amp
// Based on Bodge/HX711 arduino library
//   micro-SD card attached to DFRobot DFR0229 micro_SD reader
// ** MOSI - pin 11
// ** MISO - pin 12
// ** SCK - pin 13
// ** SS - pin 4
// ** Vcc = 5V

#include <SPI.h>
#include <SD.h>
#include "Loadcell.h"

#if defined(ESP8266)|| defined(ESP32) || defined(AVR)
#include <EEPROM.h>
#endif

// *** File parameters ***
bool file_writing = true; // set to true to write in a file
char file[] = "testd15.csv"; // name of the file to write readings in

// *** Pin numbers ***
const int LOADCELL_DOUT_PIN = 6;
const int LOADCELL_SCK_PIN = 5;
const int SS_pin = 4;
const int cal_coeff_eepromAdress = 0; // EEPROM adress of the calibration value for the loadcell

Loadcell Scale; // initialize the scale
File myFile; // initialize the file

void setup() {
  Serial.begin(57600);
  Serial.println();
  Serial.println("Starting...");
  Scale.start(LOADCELL_DOUT_PIN, LOADCELL_SCK_PIN, 128, true);
  Serial.println("Connection to the loadcell...");
  Scale.wait_ready(1000); // wait for scale to be ready before starting calibration
  //Scale.calibrate_all();
  Scale.set_weight_n_readings(5);
  //Serial.println(Scale.get_offset());
  //Serial.println(Scale.get_scale());
  Scale.set_offset(853686);
  Scale.set_scale(-16127.08);
}

void loop() {
  while (!Scale.is_ready()) {
    // waiting for scale to be ready
    delay(500);
  }
    float reading = Scale.get_units(Scale.get_weight_n_readings()); 
    Serial.print("Loadcell reading: ");
    Serial.println(reading);
    if (file_writing){
      file_write(reading, file);
    }
}


void file_write(float reading, char file) {
    while (!Serial) {
    ; // wait for serial port to connect. Needed for native USB port only
    }

    Serial.print("Initializing SD card...");

    if (!SD.begin(SS_pin)) {
      Serial.println("initialization failed!");
      while (1);
    }
    Serial.println("initialization done.");

    // open the file. note that only one file can be open at a time,
    myFile = SD.open(file, FILE_WRITE);

    // if the file opened okay, write to it:
    if (myFile) {
      Serial.print(("Writing to file..."));
      myFile.print(reading);
      myFile.print(",");
      myFile.println(millis());
      // close the file:
      myFile.close();
      Serial.println("done.");
    } else {
      // if the file didn't open, print an error:
      Serial.println("error opening file");
    }
}