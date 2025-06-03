#include <SD.h>
#include <SPI.h>
#include <WiFi.h>
#include <time.h>

#include "Logger.h"

#include "LoadCell.h"
#include "LoadCellController.h"

/************* BEGIN CONSTANTS *************/

/*
  All constants related to the circuit, the network or the file management are
  defined here:

  We have three load cells, with their clock pin
*/

const int SCK1_PIN = 4;
const int SCK2_PIN = 16;
const int SCK3_PIN = 17;

/*
  Pin to put in setup mode.
*/
const int MODE_PIN = 13;

const int READ_CALIBRATION_FROM_MEMORY = LOW;
const int RECALIBRATE = HIGH;
/*
  Pin where the SD card reader is connected
*/
const int SS_PIN = 21;

/*
  The Firebeetle connects to WiFi and offers a web server to allow the user
  to retrieve the data.

  SSID: the name of the wifi network
  PASSWORD: the password
*/
const char *SSID = "TP-Link_37E9";
const char *PASSWORD = "15351210";

// must be the same as in the python code, otherwise they won't be able to recognize one another
const char *REFRESH_CODE = "refresh";

const char *CSV_FILE_EXTENSION = ".csv";

/*
  Infos of the time provider server
*/
const char *NTP_SERVER = "pool.ntp.org";
const long GMT_OFFSET_SEC = -18000;
const int DAYLIGHT_OFFSET_SEC = 3600;

const int SAVE_DATA_INTERVAL = 0;
const int RECONNECT_WIFI_INTERVAL = 3600000;

/************* END CONSTANTS *************/

/*

Instantiate global variables necessary throughout the code

*/

LoadCell loadCell1;
LoadCell loadCell2;
LoadCell loadCell3;
LoadCellController controller;

/* File instance to simplify saving */
File myFile;

/* Web server */
WiFiServer webServer(80);

// Buffers chars
char today[16];
char yesterday[16];

unsigned long saveTimestamp = 0;
unsigned long reconnectTimestamp = 0;

// /* Declaration */
// void logf(const char *format, ...);

/*
This function tries to connect to the wifi using the SSID and the PASSWORD.
Retries every 500 milliseconds until it succeeds and then prints the local IP.

Returns true if succeeded and false if it failed.  Failing to connect should
not prevent the program to run, it should retry every hour.

*/

bool connectToWifi(int timeout_in_secs = 0) {
  Log.noticeln("Attempting to connect to Wifi network : %s, password %s", SSID,
               PASSWORD);

  WiFi.begin(SSID, PASSWORD);

  int end_time = millis() + timeout_in_secs * 1000;

  int i = 1;
  while (WiFi.status() != WL_CONNECTED) {
    Log.noticeln("Attempt #%d", i);
    i++;

    if (millis() > end_time) {
      Log.noticeln("Unable to connect to Wifi");
      return false;
    }
    delay(500);
  }

  Log.noticeln("Connected to Wifi. IP address: %s", WiFi.localIP());

  return true;
}

/*
  Get the time server today's date.
*/
void getTodaysDate() {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo)) {
    Log.noticeln("Failed to obtain time");
    return;
  }
  int year = timeinfo.tm_year + 1900;
  int month = timeinfo.tm_mon + 1;
  int day = timeinfo.tm_mday;
  snprintf(today, sizeof(today), "/%04d.%02d.%02d.csv", year, month, day);
}

/*
  Get the time server yesterday's date.
*/
void getYesterdaysDate() {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo)) {
    Serial.println("Failed to obtain time");
    return;
  }
  int year = timeinfo.tm_year + 1900;
  int month = timeinfo.tm_mon + 1;
  int day = timeinfo.tm_mday - 1;
  snprintf(yesterday, sizeof(yesterday), "/%04d.%02d.%02d.csv", year, month,
           day);
}

/*
  Writes a file in the SD card at the specified path. Puts in the specified
  message. Writes in the serial consol error if it doesn't succeed.
*/
void writeFile(const char *path, const char *message, const char *mode) {
  if (!SD.begin(SS_PIN)) {
    Log.noticeln("SD card initialization failed!");
    return;
  }

  // open the file. note that only one file can be open at a time,
  myFile = SD.open(path, mode);

  if (myFile) {
    myFile.println(message);
    myFile.close();
  } else {
    Log.errorln("Error saving file %s to SD card", path);
  }
}

/*
  Writes a clean file header for csv file.
*/
void writeFileHeader(char *file_name) {
  Serial.print(F("Writing heading..."));
  Serial.println(FILE_WRITE);
  writeFile(file_name, "time (ms), reading 1, reading 2, reading 3",
            FILE_WRITE);
}

/*
  Acquire the data and save it immediately to the SD card
*/
void saveData() {
  getTodaysDate();

  if (!SD.exists(today)) {
    configTime(GMT_OFFSET_SEC, DAYLIGHT_OFFSET_SEC, NTP_SERVER);

    getTodaysDate();  // This is to make sure we update the time correctly and
                      // we don't write into tomorrows file accidentally because
                      // Arduino's time might drift.

    if (!SD.exists(today)) {
      writeFileHeader(today);
    }
  }

  float weight1 = controller.get_weight(1);
  float weight2 = controller.get_weight(2);
  float weight3 = controller.get_weight(3);

  String fileLine = "";

  fileLine +=
    String(millis(), DEC) + "," + weight1 + "," + weight2 + "," + weight3;

  writeFile(today, fileLine.c_str(), FILE_APPEND);
}

/*
  Initializes console, connects to the wifi, sets the local time
  and calibrates or reads calibration coefficients from memory
*/
void setup() {
  Serial.begin(115200);
  while (!Serial && !Serial.available()) {}
  Log.setPrefix(printPrefix);  // set prefix similar to NLog
  Log.setSuffix(printSuffix);  // set suffix
  Log.begin(LOG_LEVEL_VERBOSE, &Serial);
  Log.setShowLevel(false);  // Do not show loglevel, we will do this in the prefix

  if (connectToWifi(5)) {
    webServer.begin();
  }

  configTime(GMT_OFFSET_SEC, DAYLIGHT_OFFSET_SEC, NTP_SERVER);

  controller.add_loadcell(loadCell1, 27,
                          SCK1_PIN);  // loadcell number, dout, sck
  controller.add_loadcell(loadCell2, 9,
                          SCK2_PIN);  // loadcell number, dout, sck
  controller.add_loadcell(loadCell3, 5,
                          SCK3_PIN);  // loadcell number, dout, sck
  controller.set_all_loadcells_scale_coeff_n_readings(50);
  controller.set_all_loadcells_tare_n_readings(2);
  controller.set_all_loadcells_weight_n_readings(1);

  /*
    The mode is either: read calibration from memory or re-calibrate

    Default is LOW, which is READ_FROM_MEMORY
  */
  pinMode(MODE_PIN, INPUT_PULLDOWN);

  if (digitalRead(MODE_PIN) == READ_CALIBRATION_FROM_MEMORY) {
    Log.noticeln("Starting in auto mode");
    controller.tare_all_loadcells(false);
    controller.read_all_scale_coeff_from_persistent_memory();
  } else {
    Log.noticeln("Starting in manual calibration mode");
    controller.tare_all_loadcells();
    controller.calibrate_all_loadcells();
  }
}

/*

The Arduino main loop: the program does two things:

1. read the scale data continuously from all load cells (typically 3)
2. check to see if someone is requesting the data via the WebServer, then send it.

  When there is a web client, reads the connection data, then sends either yesterday's
  data or today's. Sends today's if the REFRESH_CODE is present in the connection
  data.
*/
void loop() {
  unsigned long currentMillis = millis();
  long long saveTimeDelta = currentMillis - saveTimestamp;

  if (abs(saveTimeDelta) >= SAVE_DATA_INTERVAL) {
    saveTimestamp = currentMillis;
    saveData();
  }

  long long reconnectTimeDelta = currentMillis - reconnectTimestamp;

  if (abs(reconnectTimeDelta) >= RECONNECT_WIFI_INTERVAL) {
    reconnectTimestamp = currentMillis;
    connectToWifi(5);
  }

  WiFiClient client = webServer.available();  // listen for incoming client

  if (client) {
    String clientData = "";
    while (client.connected()) {
      if (client.available()) {  // if there's bytes to read from the client,
        char c = client.read();  // read a byte, then
        clientData += c;
      } else {
        if (!SD.begin(SS_PIN)) {
          Log.errorln("Card Mount Failed");
          return;
        }

        uint8_t cardType = SD.cardType();

        if (cardType == CARD_NONE) {
          Log.errorln("No SD card attached");
          return;
        }

        String httpReason = "OK";

        int csvIndex = clientData.indexOf(CSV_FILE_EXTENSION);

        if (clientData.indexOf(REFRESH_CODE) >= 0) {
          getTodaysDate();  // If the refresh code is passed, give the client
                            // the newest data
          myFile = SD.open(
            today);  // This would be the 'today' file not yet completed.
          httpReason = "REFRESHED TODAY";
        } else if (csvIndex >= 0) {
          myFile = SD.open(clientData.substring(csvIndex - 11, csvIndex + 4));
          httpReason = "CUSTOM DATE";
        } else {
          getYesterdaysDate();
          if (SD.exists(yesterday)) {
            myFile = SD.open(yesterday);
            httpReason = "DEFAULT YESTERDAY";
          } else {
            Log.errorln("yesterdays file doesn't exist!");
            myFile = SD.open(today);
            httpReason =
              "YESTERDAY MISSING FILE";  // This case is specifically for if
                                         // we start the cage close after
                                         // midnight but before the python
                                         // code tried to fetch yesterday's
                                         // data.
          }
        }

        if (!myFile) {
          Log.errorln("Failed to open file for reading");
          return;
        }

        client.println("HTTP/1.1 200 " + httpReason);
        client.println("Content-type:text/html");
        client.println();
        client.println(myFile.name());
        client.write(myFile);

        myFile.close();

        // The HTTP response ends with another blank line:
        client.println();
        // break out of the while loop:
        break;
      }
    }
    // close the connection:
    client.stop();
  }
}
