#include "LoadCell.h"
#include "LoadCellController.h"
#include <WiFi.h>
#include <Wire.h>
#include <ArduinoJson.h>  // Install via Library Manager
#include <SD.h>
#include <SPI.h>
#include "RTClib.h"
#include <time.h>
#include <HTTPClient.h>

LoadCell loadCell1;
LoadCellController controller;

const int MODE_PIN = 13; //Switch pin allowing to put in setup mode.

// const char *SSID = "TP-Link_37E9"; // of the router
// const char *PASSWORD = "15351210"; // password of the router
const char *SSID = "INTERNET-EQUIPEMENTS";
const char *PASSWORD = "ihe5hj29";
WiFiServer server(80);             // créer un serveur qui écoute les clients qui veulent s'y connecter

File myFile;           // initialize the file
const int SS_PIN = 5; // seule pin de carte SD à spécifier

const char *REFRESH_CODE = "refresh"; // must be the same as in the python code, otherwise they won't be able to recognize one another

unsigned long saveTimestamp = 0;
const int SAVE_DATA_INTERVAL = 0; 

unsigned long reconnectTimestamp = 0;
const int RECONNECT_WIFI_INTERVAL = 3600000;

const int BUFFER_SIZE = 1000;
const int LINE_LENGTH = 50;
char buffer[BUFFER_SIZE][LINE_LENGTH];
int head = 0;
int tail = 0;
bool bufferFull = false;

//Buffer chars for saving files
static char today[16];
static char yesterday[16];


/*
This function tries to connect to the wifi using the SSID and the PASSWORD.
Retries every 500 milliseconds until it succeeds and then prints the local IP.
*/
void connectToWifi()
{
  // We start by connecting to a WiFi network
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

void getTimeHTTP() {
  if ((WiFi.status() == WL_CONNECTED)) {
    HTTPClient http;
    // Make request to worldtimeapi.org for your timezone (or "api/ip" for auto-detect)
    http.begin("https://timeapi.io/api/Time/current/zone?timeZone=America/Toronto");
    int httpCode = http.GET();

    if (httpCode > 0) { // Check for the returning code
      String payload = http.getString();
      // Serial.println("HTTP Response:");
      // Serial.println(payload);
      // Parse JSON
      DynamicJsonDocument doc(4096);
      DeserializationError error = deserializeJson(doc, payload);
      if (!error) {
        const char* datetime;
        datetime = doc["datetime"];  // e.g., "2025-10-02T17:15:30.123456+00:00"
        // Serial.print("Current time: ");
        // Serial.println(datetime);
      } else {
        Serial.print("JSON parse error: ");
        Serial.println(error.c_str());
      }
    } else {
      Serial.print("HTTP GET failed, code: ");
      Serial.println(httpCode);
    }
    http.end();
  } else {
    Serial.println("WiFi not connected");
  }
}

void startRealTimeClock(){
  // Wait for serial port to connect. Needed for native USB port only
  #ifndef ESP8266
    while (!Serial); 
  #endif
  if (! rtc.begin()) { // Attempt to initialize the RTC
    Serial.println("Couldn't find RTC");
    Serial.flush();
    abort(); // Stop if RTC not found
  }
  // Check if the RTC has lost power or is not initialized
  if (! rtc.initialized() || rtc.lostPower()) {
    Serial.println("RTC is NOT initialized or lost power, let's set the time!");
    // Set the RTC to the date & time this sketch was compiled
    rtc.adjust(DateTime(F(__DATE__), F(__TIME__))); 
    // You can also set it to a specific date and time like this:
    // rtc.adjust(DateTime(2024, 1, 21, 3, 0, 0)); // Year, Month, Day, Hour, Minute, Second
  }
  rtc.start(); // Ensure the RTC is running (clears the STOP bit if necessary)
}

/*
Gets through the time server today's date.
*/
void getTodaysDate(){
  DateTime now = rtc.now(); // Get the current date and time from the RTC
  int year = now.year();
  int month = now.month();
  int day = now.day();

  snprintf(today, sizeof(today), "/%04d.%02d.%02d.csv", year, month, day);
} 


void writeFile(const char *path, const char *message, const char *mode){
  if (bufferFull == false){
    addToBuffer(message);
  }
  else
    {
      while (!Serial)
    {
      ; // wait for serial port to connect. Needed for native USB port only
    }
      // open the file. note that only one file can be open at a time,
    myFile = SD.open(path, mode);
    // if the file opened okay, write to it:
    if (myFile)
      {
      // close the file:
      flushBufferToSD();
      myFile.print(message);
      myFile.close();
      digitalWrite(pinLEDblue, HIGH);
      delay(50);
      digitalWrite(pinLEDblue, LOW);
      }
    else
      {
      // if the file didn't open, print an error:
      Serial.println("error opening file");
      }
}
}

void createFile(const char *path, const char *message, const char *mode){
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

void flushBufferToSD(){
  while (head != tail || bufferFull) {
    myFile.print(buffer[tail]);
    tail = (tail + 1) % BUFFER_SIZE;
    bufferFull = false;
  }
  myFile.print("--, --, --, -- \n");
}

void addToBuffer(const char *message){
  strncpy(buffer[head], message, LINE_LENGTH - 1);
  buffer[head][LINE_LENGTH - 1] = '\0';  // ensure null-termination
  head = (head + 1) % BUFFER_SIZE;
    if (head == tail) {
    bufferFull = true;
  }
    if (head >= BUFFER_SIZE) {
    bufferFull = true;
  }
}


void writeFileHeader(char *file_name) {
  createFile(file_name, "time (ms), reading 1, reading 2, reading 3", FILE_WRITE);
}


/*
This method will be where we save the real data. For now it creates fake data.
*/
void saveData()
{
  getTodaysDate();
  if (!SD.exists(today))
  {
    //This is to make sure we update the time correctly and we don't write into tomorrows file accidentally because Arduino's time might drift.
    writeFileHeader(today);
  }
  float weight1 = controller.get_weight(1);
  float weight2 = controller.get_weight(2);
  float weight3 = controller.get_weight(3);

  String fileLine = "";
  fileLine += String(millis(), DEC) + "," + weight1 + "," + weight2 + "," + weight3 + "\n";
  writeFile(today, fileLine.c_str(), FILE_APPEND);
}


/*
Initializes console, connects to the wifi, the local time and creates the initial test data.
*/
void setup()
{
  Serial.begin(115200);

  connectToWifi();

  pinMode(MODE_PIN, INPUT_PULLDOWN);
  controller.add_loadcell(loadCell1, 9, 17); // loadcell number, dout, sck
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
  saveData();
}