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
#include <dht.h>
    


#if defined(ESP8266)|| defined(ESP32) || defined(AVR)
#include <EEPROM.h>
#endif

// *** File parameters ***
bool file_writing = false; // set to true to write in a file
char file[] = "testd_j5.csv"; // name of the file to write readings in

// *** drift parameters ***
//float drift_slope = 114.18;
//float threshold = 24;
//float initial_offset = 1428674;
// *** Pin numbers ***
const int LOADCELL_DOUT_PIN_1 = 8;
const int LOADCELL_SCK_PIN_1 = 9;

const int LOADCELL_DOUT_PIN_2 = 2;
const int LOADCELL_SCK_PIN_2 = 3;

const int LOADCELL_DOUT_PIN_3 = 5;
const int LOADCELL_SCK_PIN_3 = 6;

const int SS_pin = 4;

dht DHT;
#define DHT22_PIN 7

Loadcell scale_1;
Loadcell scale_2;
Loadcell scale_3;
File myFile; // initialize the file

void setup() {
  Serial.begin(57600);
  Serial.println();
  scale_1.begin(LOADCELL_DOUT_PIN_1, LOADCELL_SCK_PIN_1);
  scale_2.begin(LOADCELL_DOUT_PIN_2, LOADCELL_SCK_PIN_2);
  scale_3.begin(LOADCELL_DOUT_PIN_3, LOADCELL_SCK_PIN_3);
  Serial.println("Connection to the loadcell...");
  scale_1.wait_ready(1000); // wait for scale to be ready before starting calibration
  scale_2.wait_ready(1000);
  scale_3.wait_ready(1000);
  scale_1.set_weight_n_readings(50);
  scale_2.set_weight_n_readings(50);
  scale_3.set_weight_n_readings(50);
  Serial.println("start");
}

void loop() {
  while (!scale_1.is_ready()) {
    // waiting for scale to be ready
    delay(500);
  }
  while (!scale_2.is_ready()) {
    // waiting for scale to be ready
    delay(500);
  }
  while (!scale_3.is_ready()) {
    // waiting for scale to be ready
    delay(500);
  }
    double raw_1 = scale_1.read_raw_average();
    double raw_2 = scale_2.read_raw_average();
    double raw_3 = scale_3.read_raw_average();
    int chk = DHT.read22(DHT22_PIN); 
      switch (chk)
      {
        case DHTLIB_OK:
                    Serial.print("OK,\t");
                    break;
        case DHTLIB_ERROR_CHECKSUM:
                    Serial.print("Checksum error,\t");
                    break;
        case DHTLIB_ERROR_TIMEOUT:
                    Serial.print("Time out error,\t");
                    break;
        default:
                    Serial.print("Unknown error,\t");
                    break;
      }
    float humidity = DHT.humidity;
    float temp = DHT.temperature;
    Serial.print("Loadcell: ");
    Serial.print(raw_1);  
    Serial.print("\t");
    Serial.print("\t");
    Serial.print(raw_2);
    Serial.print("\t");
    Serial.print("\t"); 
    Serial.print(raw_3);
    Serial.print("\t");
    Serial.print("\t");
    Serial.print("Temp reading: ");
    Serial.print(temp);
    Serial.print("\t");
    Serial.print("Humidity reading: ");
    Serial.print(humidity);
    Serial.println();
    if (file_writing){
      file_write(raw_1, raw_2, raw_3, temp, humidity);
    }
    Serial.println("***");
}


void file_write(double raw_1, double raw_2, double raw_3, float temp, float humidity) {
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
      myFile.print(raw_1);
      myFile.print(",");
      myFile.print(raw_2);
      myFile.print(",");
      myFile.print(raw_3);
      myFile.print(",");
      myFile.print(temp);
      myFile.print(",");
      myFile.print(humidity);
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