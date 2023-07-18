// Arduino sketch to calibrate and read value from loadcell and HX711 amp
// Based on Bodge/HX711 arduino library
//   micro-SD card attached to DFRobot DFR0229 micro_SD reader

// SPI on Arduino Uno
// ** MOSI - pin 11
// ** MISO - pin 12
// ** SCK - pin 13
// ** SS - pin 4
// ** Vcc = 5V

// HX711 circuit wiring
#include "HX711.h"
#include <SPI.h>
#include <SD.h>

const int tare_n_readings = 20; // number of readings averaged to determine tare offset, a high value provides mores precision
const int scale_n_readings = 50; // number of readings averaged to determine scale calibration coefficient, a high value provides mores precision
const int LOADCELL_DOUT_PIN = 6;
const int LOADCELL_SCK_PIN = 5;
const int SS_pin = 4;

HX711 Scale;
File myFile;

void setup() {
  Serial.begin(57600);
  Serial.println();
  Serial.println("Starting...");
  Scale.begin(LOADCELL_DOUT_PIN, LOADCELL_SCK_PIN);
  Serial.println("Connection to the loadcell...");
  Scale.wait_ready(1000); // wait for scale to be ready before starting calibration
}

void loop() {
  if (Scale.is_ready()) {
    float reading = Scale.read();
    Serial.print("Loadcell reading: ");
    Serial.println(reading);
    filewrite(reading);
  } else {
    Serial.println("HX711 not found.");
  }

  delay(1000);
  
}

void filewrite(float reading) {
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
    // so you have to close this one before opening another.
    myFile = SD.open("data.csv", FILE_WRITE);

    // if the file opened okay, write to it:
    if (myFile) {
      Serial.print("Writing to data.csv...");
      myFile.print(reading);
      myFile.print(",");
      myFile.println(millis());
      // close the file:
      myFile.close();
      Serial.println("done.");
    } else {
      // if the file didn't open, print an error:
      Serial.println("error opening data.csv");
    }
  }
