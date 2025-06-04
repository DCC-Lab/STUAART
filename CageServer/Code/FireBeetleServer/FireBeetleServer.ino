#include <SD.h>
#include <SPI.h>
#include <WiFi.h>
#include <time.h>
#include <esp_log.h>
#include "Logger.h"

#include "LoadCell.h"
#include "LoadCellController.h"

#include "constants.h"

// #define TEST 1


#ifndef TEST
/*
Instantiate global variables necessary throughout the code
*/

LoadCellController controller;

/* File instance to simplify saving */
File myFile;

/* Web server */
WiFiServer webServer(80);

// Buffers chars
// char today[16];
// char yesterday[16];

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
      return true;
    }
    delay(500);
  }

  Log.noticeln("Connected to Wifi. IP address: %s", WiFi.localIP());

  return false;
}

bool connectSDCardReader() {
  if (!SD.begin(SD_CS)) {
    Log.errorln("SD card reader failed: device not responding");
    return true;
  // } else {
  //   Log.infoln(F("SD card reader initialized on pin %d"), SD_CS);
  }

  uint8_t cardType = SD.cardType();

  if (cardType == CARD_NONE) {
    Log.errorln("No SD card in card reader");
    return true;
  }
  // Log.infoln("cardType : %d", cardType);
  return false;
}

uint64_t secondsSinceBoot() {
  return millis() / 1000ULL;  // `ULL` ensures 64-bit math
}

/*
  Get the time server today's date.
*/
String getTodaysDate() {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo)) {
    uint64_t seconds = secondsSinceBoot();
    Log.noticeln("Failed to obtain time, falling back to time since boot %u", seconds);
    timeinfo.tm_year = 0;
    timeinfo.tm_mon = seconds / (60*60*24*30);
    timeinfo.tm_mday = seconds / (60*60*24);
  }
  return format_timeinfo(timeinfo);
}

/*
  Get the time server yesterday's date.
*/
String getYesterdaysDate() {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo)) {
    Serial.println("Failed to obtain time");
    
    uint64_t seconds = secondsSinceBoot();
    timeinfo.tm_year = 0;
    timeinfo.tm_mon = seconds % (60*60*24*30);
    timeinfo.tm_mday = seconds % (60*60*24);
  }
  timeinfo.tm_mday = timeinfo.tm_mday - 1;
  return format_timeinfo(timeinfo);
}

String format_timeinfo(struct tm timeinfo) {
  int year = timeinfo.tm_year + 1900;
  int month = timeinfo.tm_mon + 1;
  int day = timeinfo.tm_mday;

  // Create and return the formatted date_string as a String
  String date_string = String(year);
  date_string += ".";
  if (month < 10) date_string += "0";
  date_string += String(month);
  date_string += ".";
  if (day < 10) date_string += "0";
  date_string += String(day);
  return date_string;

}

/*
  Writes a file in the SD card at the specified path. Puts in the specified
  message. Writes in the serial consol error if it doesn't succeed.
*/
void writeFile(String path, const char *message, const char *mode) {
  if (connectSDCardReader()) {
    Log.errorln("Card reader unavailable to write data to %s", path);
    return;
  }

  // open the file. note that only one file can be open at a time,
  myFile = SD.open(path.c_str(), mode);

  if (myFile) {
    myFile.println(message);
    Log.infoln("Saved '%s' to %s", message, path.c_str());
    myFile.close();
  } else {
    Log.errorln("Unable to file %s to SD card", path.c_str());
  }
}

/*
  Writes a clean file header for csv file.
*/
void writeFileHeader(String file_name) {
  Serial.print(F("Writing heading..."));
  Serial.println(FILE_WRITE);
  writeFile(file_name, "time (ms), reading 1, reading 2, reading 3",
            FILE_WRITE);
}

/*
  Acquire the data and save it immediately to the SD card
*/
void saveData() {
  String filename = getTodaysDate();
  filename = "/" + filename + ".csv";

  if (!SD.exists(filename.c_str())) {
    configTime(GMT_OFFSET_SEC, DAYLIGHT_OFFSET_SEC, NTP_SERVER);

    filename = getTodaysDate();  // This is to make sure we update the time correctly and
                      // we don't write into tomorrows file accidentally because
                      // Arduino's time might drift.
    filename = "/" + filename + ".csv";

    if (!SD.exists(filename.c_str())) {
      writeFileHeader(filename);
    }
  }

  float weight1 = controller.get_weight(1);
  float weight2 = controller.get_weight(2);
  float weight3 = controller.get_weight(3);

  String fileLine = "";

  fileLine +=
    String(millis(), DEC) + "," + weight1 + "," + weight2 + "," + weight3;

  writeFile(filename, fileLine.c_str(), FILE_APPEND);
}

/*
  Initializes console, connects to the wifi, sets the local time
  and calibrates or reads calibration coefficients from memory
*/
void setup() {
  Serial.begin(115200);
  while (!Serial && !Serial.available()) {}

  /*
    The mode is either: read calibration from memory or re-calibrate

    Default is LOW, which is READ_FROM_MEMORY
  */
  pinMode(MODE_PIN, INPUT_PULLDOWN);
  /*
  The pin for SD card must be output
  */
  pinMode(SD_CS, OUTPUT);


  set_default_format(Log);
  esp_log_level_set("*", ESP_LOG_NONE);  

  if (connectToWifi(5)) {
    Log.errorln("Web server will not be started");
  } else {
    webServer.begin();
  }

  if (connectSDCardReader()) {
    Log.errorln("There will not be any access to SD Card");
  }

  configTime(GMT_OFFSET_SEC, DAYLIGHT_OFFSET_SEC, NTP_SERVER);

  controller.add_loadcell(DOUT1_PIN, SCK1_PIN, GAIN);
  controller.add_loadcell(DOUT2_PIN, SCK2_PIN, GAIN);
  controller.add_loadcell(DOUT3_PIN, SCK3_PIN, GAIN);

  controller.set_all_loadcells_scale_coeff_n_readings(50);
  controller.set_all_loadcells_tare_n_readings(2);
  controller.set_all_loadcells_weight_n_readings(1);

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

        String httpReason = "OK";

        int csvIndex = clientData.indexOf(CSV_FILE_EXTENSION);

        String the_date = getTodaysDate(); 
        if (clientData.indexOf(REFRESH_CODE) >= 0) {
          myFile = SD.open(the_date.c_str());  // This would be the 'today' file not yet completed.
          httpReason = "REFRESHED TODAY";
        } else if (csvIndex >= 0) {
          myFile = SD.open(clientData.substring(csvIndex - 11, csvIndex + 4));
          httpReason = "CUSTOM DATE";
        } else {
          the_date = getYesterdaysDate();
          if (SD.exists(the_date.c_str())) {
            myFile = SD.open(the_date.c_str());
            httpReason = "DEFAULT YESTERDAY";
          } else {
            Log.errorln("yesterdays file doesn't exist!");
            myFile = SD.open(the_date.c_str());
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

#else
#include <AUnit.h>

void setup() {
  delay(1000); // wait for stability on some boards to prevent garbage Serial
  Serial.begin(115200); // ESP8266 default of 74880 not supported on Linux
  while (!Serial); // for the Arduino Leonardo/Micro only

}

void loop() {
  aunit::TestRunner::run();
}

#endif