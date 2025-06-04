#pragma once

/*
  All constants related to the circuit, the network or the file management are
  defined here:

  We have three load cells, with their clock pin and data out pins
*/

const byte SCK1_PIN = 4;
const byte SCK2_PIN = 16;
const byte SCK3_PIN = 17;

const byte DOUT1_PIN = 27;
const byte DOUT2_PIN = 9;
const byte DOUT3_PIN = 5;

const byte GAIN = 128;

/*
  Pin to put in setup mode.
*/
const int MODE_PIN = 13;

const int READ_CALIBRATION_FROM_MEMORY = LOW;
const int RECALIBRATE = HIGH;
/*
  Pin where the SD card reader is connected
*/
const int SS_PIN = D8;

/*
  The Firebeetle connects to WiFi and offers a web server to allow the user
  to retrieve the data.

  SSID: the name of the wifi network
  PASSWORD: the password
*/

// const char *SSID = "TP-Link_37E9";
// const char *PASSWORD = "15351210";
inline constexpr const char *SSID = "BELL018";
inline constexpr const char *PASSWORD = "445C2A6CFEE1";

// must be the same as in the python code, otherwise they won't be able to recognize one another
inline constexpr const char *REFRESH_CODE = "refresh";

inline constexpr const char *CSV_FILE_EXTENSION = ".csv";

/*
  Infos of the time provider server
*/
inline constexpr const char *NTP_SERVER = "pool.ntp.org";
const long GMT_OFFSET_SEC = -18000;
const int DAYLIGHT_OFFSET_SEC = 3600;

const int SAVE_DATA_INTERVAL = 0;
const int RECONNECT_WIFI_INTERVAL = 3600000;

/************* END CONSTANTS *************/
