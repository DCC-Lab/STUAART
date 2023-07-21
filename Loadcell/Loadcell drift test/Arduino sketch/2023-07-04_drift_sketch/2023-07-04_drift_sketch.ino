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
bool file_writing = true; // set to true to write in a file
char file[] = "testdj4.csv"; // name of the file to write readings in

// *** drift parameters ***
// *** Pin numbers ***
const int LOADCELL_DOUT_PIN = 6;
const int LOADCELL_SCK_PIN = 5;
const int SS_pin = 4;

dht DHT;
#define DHT22_PIN 3

Loadcell scale; // initialize the scale
File myFile; // initialize the file

void setup() {
  Serial.begin(57600);
  Serial.println();
  Serial.println("Starting...");
  scale.begin(LOADCELL_DOUT_PIN, LOADCELL_SCK_PIN);
  Serial.println("Connection to the loadcell...");
  scale.wait_ready(1000); // wait for scale to be ready before starting calibration
  scale.set_weight_n_readings(50);
}

void loop() {
  while (!scale.is_ready()) {
    // waiting for scale to be ready
    delay(500);
  }
    float raw = scale.read_raw_average();
    float mass = scale.get_weight(); 
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
    Serial.print("Raw reading: ");
    Serial.print(raw);  ;  
    Serial.print("\t");
    Serial.print("\t");
    Serial.print("Temp reading: ");
    Serial.print(temp);
    Serial.print("\t");
    Serial.print("Humidity reading: ");
    Serial.print(humidity);
    Serial.print("\t");
    Serial.println();
    if (file_writing){
      file_write(raw, mass, temp, humidity);
    }
    Serial.println("***");
}


void file_write(float raw, float mass, float temp, float humidity) {
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
      myFile.print(raw);
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