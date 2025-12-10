#include "LoadCell.h"
#include "LoadCellController.h"
#include <WiFi.h>
#include <Wire.h>
#include <ArduinoJson.h>  // Install via Library Manager

LoadCell loadCell1;
LoadCellController controller;

const int MODE_PIN = 13; //Switch pin allowing to put in setup mode.

// const char *SSID = "TP-Link_37E9"; // of the router
// const char *PASSWORD = "15351210"; // password of the router
const char *SSID = "INTERNET-EQUIPEMENTS";
const char *PASSWORD = "ihe5hj29";
WiFiServer server(80);             // créer un serveur qui écoute les clients qui veulent s'y connecter

const char *REFRESH_CODE = "refresh"; // must be the same as in the python code, otherwise they won't be able to recognize one another

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
This method will be where we save the real data. For now it creates fake data.
*/
void saveData()
{
  float weight1 = controller.get_weight(1);
  Serial.println(weight1);
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