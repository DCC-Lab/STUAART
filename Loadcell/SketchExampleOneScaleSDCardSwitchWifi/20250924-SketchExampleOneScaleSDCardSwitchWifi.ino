// This script was used by VPN to test the new metal scales, that's all. 
#include "LoadCell.h"
#include "LoadCellController.h"
#include <WiFi.h>
#include <SD.h>
#include <SPI.h>
#include <time.h>

LoadCell loadCell1;
LoadCellController controller;
const int SCK_PIN = 17; //clock des loadcell/HX711

const int MODE_PIN = 13; //Switch pin allowing to put in setup mode.

File myFile;           // initialize the file
const int SS_PIN = 21; // seule pin de carte SD à spécifier

// const char *SSID = "TP-Link_37E9"; // of the router
// const char *PASSWORD = "15351210"; // password of the router
const char *SSID = "INTERNET-EQUIPEMENTS"; // This network only works for the firebeetle with the red dot
const char *PASSWORD = "ihe5hj29";
WiFiServer server(80);             // créer un serveur qui écoute les clients qui veulent s'y connecter

const char *REFRESH_CODE = "refresh"; // must be the same as in the python code, otherwise they won't be able to recognize one another

//Infos of the time provider server
const char *NTP_SERVER = "pool.ntp.org";
const long GMT_OFFSET_SEC = -18000;
const int DAYLIGHT_OFFSET_SEC = 3600;

//Buffer chars for saving files
char today[16];
char yesterday[16];

unsigned long saveTimestamp = 0;
const int SAVE_DATA_INTERVAL = 0; 

unsigned long reconnectTimestamp = 0;
const int RECONNECT_WIFI_INTERVAL = 3600000;

/*
This function tries to connect to the wifi using the SSID and the PASSWORD.
Retries every 500 milliseconds until it succeeds and then prints the local IP.
*/
void connectToWifi()
{
  // We start by connecting to a WiFi network
  Serial.println();
  Serial.println();
  Serial.print("Connecting to ");
  Serial.println(SSID);
  WiFi.begin(SSID, PASSWORD);
  while (WiFi.status() != WL_CONNECTED)
  {
    delay(500);
    Serial.print(".");
  }
  Serial.println("");
  Serial.println("WiFi connected.");
  Serial.println("IP address: ");
  Serial.println(WiFi.localIP());
  server.begin();
}


/*
Gets through the time server today's date.
*/
void getTodaysDate(){
  struct tm timeinfo;
  if(!getLocalTime(&timeinfo)){
    Serial.println("Failed to obtain time");
    return;
  }
  int year = timeinfo.tm_year + 1900;
  int month = timeinfo.tm_mon +1;
  int day = timeinfo.tm_mday;
  snprintf(today, sizeof(today), "/%04d.%02d.%02d.csv", year, month, day);
}


/*
Gets through the time server yesterday's date.
*/
void getYesterdaysDate(){
  struct tm timeinfo;
  if(!getLocalTime(&timeinfo)){
    Serial.println("Failed to obtain time");
    return;
  }
  int year = timeinfo.tm_year + 1900;
  int month = timeinfo.tm_mon +1;
  int day = timeinfo.tm_mday-1;
  snprintf(yesterday, sizeof(yesterday), "/%04d.%02d.%02d.csv", year, month, day);
}


/*
Writes a file in the SD card at the specified path. Puts in the specified message.
Writes in the serial consol error if it doesn't succeed.
*/
void writeFile(const char *path, const char *message, const char *mode)
{
  while (!Serial)
  {
    ; // wait for serial port to connect. Needed for native USB port only
  }

  if (!SD.begin(SS_PIN))
  {
    Serial.println("initialization failed!");
    return;
  }

  // open the file. note that only one file can be open at a time,
  myFile = SD.open(path, mode);

  // if the file opened okay, write to it:
  if (myFile)
  {
    myFile.println(message);
    // close the file:
    myFile.close();
  }
  else
  {
    // if the file didn't open, print an error:
    Serial.println("error opening file");
  }
}


/*
Writes a clean file header for csv file.
*/
void writeFileHeader(char *file_name) {
  Serial.print(F("Writing heading..."));
  Serial.println(FILE_WRITE);
  writeFile(file_name, "time (ms), reading 1", FILE_WRITE);
}


/*
This method will be where we save the real data. For now it creates fake data.
*/
void saveData()
{
  getTodaysDate();

  if (!SD.exists(today))
  {
    configTime(GMT_OFFSET_SEC, DAYLIGHT_OFFSET_SEC, NTP_SERVER);

    getTodaysDate();//This is to make sure we update the time correctly and we don't write into tomorrows file accidentally because Arduino's time might drift.

    if (!SD.exists(today))
    {
      writeFileHeader(today);
    }
  }

  float weight1 = controller.get_weight(1);
  Serial.print(weight1);
  Serial.println();


  String fileLine = "";
  
  fileLine += String(millis(), DEC) + "," + weight1;

  writeFile(today, fileLine.c_str(), FILE_APPEND);
}


/*
Initializes console, connects to the wifi, the local time and creates the initial test data.
*/
void setup()
{
  Serial.begin(115200);

  // connectToWifi();

  configTime(GMT_OFFSET_SEC, DAYLIGHT_OFFSET_SEC, NTP_SERVER);

  pinMode(MODE_PIN, INPUT_PULLDOWN);
  controller.add_loadcell(loadCell1, 9, SCK_PIN); // loadcell number, dout, sck
  controller.set_all_loadcells_scale_coeff_n_readings(50);
  controller.set_all_loadcells_tare_n_readings(2);
  controller.set_all_loadcells_weight_n_readings(1);

  if (digitalRead(MODE_PIN) == LOW)
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
}


/*
Loops, waiting for a client connection.
When there is a client, reads the connection data, then sends either yesterday's data or today's.
Sends today's if the REFRESH_CODE is present in the connection data.
*/
void loop()
{
  unsigned long currentMillis = millis();
  long long saveTimeDelta = currentMillis - saveTimestamp;

  if (abs(saveTimeDelta) >= SAVE_DATA_INTERVAL)
  {
    saveTimestamp = currentMillis;
    saveData();
  }

  long long reconnectTimeDelta = currentMillis - reconnectTimestamp;

  if (abs(reconnectTimeDelta) >= RECONNECT_WIFI_INTERVAL)
  {
    reconnectTimestamp = currentMillis;
  }

  if (!SD.begin(SS_PIN))
  {
    Serial.println("Card Mount Failed");
    return;
  }

  uint8_t cardType = SD.cardType();
  if (cardType == CARD_NONE)
  {
    Serial.println("No SD card attached");
    return;
  }   
}
