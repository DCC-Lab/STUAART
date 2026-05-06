#include "LoadCell.h"
#include "LoadCellController.h"
#include <WiFi.h>
#include <SD.h>
#include <SPI.h>
#include <Wire.h>
#include "RTClib.h"
#include <time.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>  // Install via Library Manager

RTC_PCF8523 rtc; // Create an RTC object for the PCF8523

LoadCell loadCell1;
LoadCell loadCell2;
LoadCell loadCell3;
LoadCellController controller;

const int pinLED1 = 10;
const int pinLED2 = 2;
const int pinLED3 = 14;
const int pinLED4 = 15;

const int MODE_PIN = 13; //Switch pin allowing to put in setup mode.

File myFile;           // initialize the file
const int SS_PIN = 5; // seule pin de carte SD à spécifier

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
const unsigned long WIFI_CONNECT_TIMEOUT_MS = 15000;
bool wifiConnected = false;
bool sdInitialized = false;
bool streamOn = false;                  // CSV stream to Serial : OFF by default
const size_t CMD_BUF_SIZE = 64;
char cmdBuf[CMD_BUF_SIZE];              // accumulates one line of user input
size_t cmdLen = 0;
char pendingCmd[CMD_BUF_SIZE] = "";     // command awaiting y/n confirmation

const int BUFFER_SIZE = 1000;
const int LINE_LENGTH = 50;
char buffer[BUFFER_SIZE][LINE_LENGTH];
int head = 0;
int tail = 0;
bool bufferFull = false;

//Buffer chars for saving files
static char today[16];
static char yesterday[16];

/**
 * @brief Try to connect to WiFi using the hardcoded SSID and PASSWORD.
 *
 * Retries every 500 ms until the chip reports `WL_CONNECTED` or the
 * configured `WIFI_CONNECT_TIMEOUT_MS` (15 s) elapses, whichever comes
 * first. On success, sets the global `wifiConnected = true`, starts the
 * HTTP `server`, and blinks `pinLED2` three times. On timeout, sets
 * `wifiConnected = false` and continues without network ; the firmware
 * keeps logging to SD and (if enabled) Serial.
 *
 * Called once from @ref setup and again on a 1-hour interval from
 * @ref loop, so a transient outage recovers automatically.
 */
void connectToWifi()
{
  Serial.print("Connecting to ");
  Serial.println(SSID);
  WiFi.begin(SSID, PASSWORD);
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && (millis() - start) < WIFI_CONNECT_TIMEOUT_MS)
  {
    delay(500);
    Serial.print(".");
  }
  Serial.println("");
  if (WiFi.status() == WL_CONNECTED) {
    wifiConnected = true;
    Serial.println("WiFi connected.");
    Serial.println("IP address: ");
    Serial.println(WiFi.localIP());
    server.begin();
    for (int i = 0; i < 3; i++) {
      digitalWrite(pinLED2, HIGH); delay(100);
      digitalWrite(pinLED2, LOW);  delay(100);
    }
  } else {
    wifiConnected = false;
    Serial.println("WiFi unavailable, continuing without network.");
  }
}



/**
 * @brief Fetch the current local time from timeapi.io over HTTPS.
 *
 * Issues a GET to `https://timeapi.io/api/Time/current/zone?timeZone=America/Toronto`,
 * parses the JSON response with ArduinoJson, and reads the `datetime`
 * field. Currently the result is not pushed to the RTC (the JSON is
 * extracted but the assignment is commented out) ; this function is a
 * stub for future synchronization.
 *
 * Requires WiFi to be connected. Logs an error otherwise.
 */
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



/**
 * @brief Initialize the PCF8523 real-time clock and seed it with the
 * compile-time date and time.
 *
 * Halts the firmware in an infinite loop if `rtc.begin()` fails (no
 * RTC found on the I2C bus). On success, calls `rtc.adjust()` with
 * the `__DATE__`/`__TIME__` macros so the clock is at least roughly
 * correct after a flash, and `rtc.start()` to clear any STOP bit.
 *
 * The compile-time seed is a coarse fallback ; for accurate time use
 * the `time YYYY-MM-DD HH:MM:SS` serial command after boot.
 */
void startRealTimeClock(){
  // Wait for serial port to connect. Needed for native USB port only
  #ifndef ESP8266
    while (!Serial); 
  #endif
  if (! rtc.begin()) { // Attempt to initialize the RTC
    Serial.println("Couldn't find RTC");
    Serial.flush();
    while (1) delay(10);
  }

  else {
    Serial.println("RTC setup succeeded");
  }
  rtc.adjust(DateTime(F(__DATE__), F(__TIME__))); 
  rtc.start(); // Ensure the RTC is running (clears the STOP bit if necessary)
}

/**
 * @brief Format today's date as a CSV filename in the global `today[]`
 * buffer, e.g. `/2026.05.06.csv`.
 *
 * Reads the current time from the PCF8523 RTC and writes the formatted
 * string into `today[]` via `snprintf`. Used by @ref saveData to pick
 * the destination file on the SD card.
 */
void getTodaysDate(){
  DateTime now = rtc.now(); // Get the current date and time from the RTC
  int year = now.year();
  int month = now.month();
  int day = now.day();

  snprintf(today, sizeof(today), "/%04d.%02d.%02d.csv", year, month, day);
} 


/**
 * @brief Format yesterday's date as a CSV filename in the global
 * `today[]` buffer (sic ; the function reuses the same buffer).
 *
 * @warning Naive implementation : subtracts 1 from `now.day()` without
 * handling month / year roll-over. Fails on the first of any month.
 */
void getYesterdaysDate(){
  DateTime now = rtc.now(); // Get the current date and time from the RTC
  int year = now.year();
  int month = now.month();
  int day = now.day() - 1;

  snprintf(today, sizeof(today), "/%04d.%02d.%02d.csv", year, month, day);
}


/**
 * @brief Buffer one CSV line, flush to SD when the in-memory ring fills.
 *
 * The firmware accumulates up to `BUFFER_SIZE` (1000) lines in RAM
 * via @ref addToBuffer. When the ring becomes full, this function
 * opens the daily file, calls @ref flushBufferToSD to drain the ring,
 * appends the new line, closes the file, and blinks `pinLED1`. This
 * batched write avoids opening the SD card on every sample at 80 Hz.
 *
 * @param path Destination filename on the SD card (e.g. `/2026.05.06.csv`).
 * @param message Null-terminated CSV line, including trailing `\n`.
 * @param mode `FILE_WRITE` (overwrite) or `FILE_APPEND`.
 */
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
      digitalWrite(pinLED1, HIGH);
      delay(50);
      digitalWrite(pinLED1, LOW);
      }
    else
      {
      // if the file didn't open, print an error:
      Serial.println("error opening file");
      }
}
}

/**
 * @brief Create or truncate a file on the SD card and write a single
 * line to it.
 *
 * Used by @ref writeFileHeader to drop the CSV header at the top of a
 * new daily file. No-op if `sdInitialized` is `false`.
 *
 * @param path Destination filename on the SD card.
 * @param message Null-terminated text written via `myFile.println()`
 * (a `\n` is appended automatically).
 * @param mode Typically `FILE_WRITE` (truncates).
 */
void createFile(const char *path, const char *message, const char *mode){
  if (!sdInitialized) return;
  myFile = SD.open(path, mode);
  if (myFile) {
    myFile.println(message);
    myFile.close();
  } else {
    Serial.println("error opening file");
  }
}


/**
 * @brief Append a CSV line to the in-RAM ring buffer.
 *
 * Copies up to `LINE_LENGTH - 1` characters from `message` into
 * `buffer[head]`, ensures null termination, and advances `head` modulo
 * `BUFFER_SIZE`. When `head` catches up to `tail`, sets the
 * `bufferFull` flag so @ref writeFile knows to flush.
 *
 * @param message Null-terminated CSV line (truncated if longer than
 * `LINE_LENGTH - 1` bytes).
 */
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


/**
 * @brief Drain the in-RAM ring buffer to the currently open SD file.
 *
 * Called from @ref writeFile while `myFile` is open. Iterates from
 * `tail` to `head` and writes each buffered line via `myFile.print()`.
 * Resets the `bufferFull` flag and appends a sentinel marker line
 * `--, --, --, --` so a downstream reader can spot a flush boundary.
 *
 * @pre `myFile` must already be open in the caller.
 */
void flushBufferToSD(){
  while (head != tail || bufferFull) {
    myFile.print(buffer[tail]);
    tail = (tail + 1) % BUFFER_SIZE;
    bufferFull = false;
  }
  myFile.print("--, --, --, -- \n");
}



/**
 * @brief Write the 7-column CSV header at the top of a new daily file.
 *
 * Header :
 * `time (ms), reading 1, reading 2, reading 3, raw 1, raw 2, raw 3`
 *
 * The `reading` wording is preserved so existing post-processing scripts
 * that match on those names keep working ; the three `raw` columns are
 * the new signed 24-bit HX711 counts.
 *
 * @param file_name Destination CSV path on the SD card.
 */
void writeFileHeader(char *file_name) {
  createFile(file_name, "time (ms), reading 1, reading 2, reading 3, raw 1, raw 2, raw 3", FILE_WRITE);
}


/**
 * @brief Sample the 3 load cells once and persist the row.
 *
 * Reads the raw 24-bit count from each cell via `read_raw_average()`
 * and converts each one to grams via `mass_from_raw()`, so the weight
 * and raw on the same line come from the *same* HX711 conversion (no
 * double read). Builds a 7-field CSV line :
 *
 * `time(ms), w1, w2, w3, raw1, raw2, raw3\n`
 *
 * If the SD card is initialised, the line is appended to today's file
 * (creating it with a header if needed). If `streamOn` is true, the
 * same line is mirrored on Serial.
 *
 * Called every iteration of @ref loop ; throughput is bounded by the
 * HX711 conversion rate (~80 Hz on STUAART hardware).
 */
void saveData()
{
  // Read raws once and derive weights from them, so the two values on the
  // same line come from the SAME HX711 conversion (no double read).
  long raw1 = controller.read_raw_average(1);
  long raw2 = controller.read_raw_average(2);
  long raw3 = controller.read_raw_average(3);
  float weight1 = controller.mass_from_raw(1, raw1);
  float weight2 = controller.mass_from_raw(2, raw2);
  float weight3 = controller.mass_from_raw(3, raw3);

  String fileLine = "";
  fileLine += String(millis(), DEC) + ","
            + weight1 + "," + weight2 + "," + weight3 + ","
            + raw1 + "," + raw2 + "," + raw3 + "\n";

  if (sdInitialized) {
    getTodaysDate();
    if (!SD.exists(today)) {
      writeFileHeader(today);
    }
    writeFile(today, fileLine.c_str(), FILE_APPEND);
  }

  if (streamOn) {
    Serial.print(fileLine);
  }
}



/**
 * @page serial_commands STUAART Serial Command Interface
 *
 * @section serial_overview Overview
 *
 * The STUAART firmware exposes an interactive command interface on the
 * USB serial port at 115200 baud. After boot the firmware prints a hint
 * pointing at `help` and waits for input. CSV streaming on Serial is
 * **OFF by default** ; type `stream on` to start it.
 *
 * The line accumulator is non-blocking : the firmware keeps reading the
 * load cells at 80 Hz while you type. Each command is terminated by `\n`
 * or `\r` (Enter). A typed line is echoed back as `> <cmd>` for
 * confirmation.
 *
 * @section destructive Destructive command confirmation
 *
 * Commands that modify state (tare, save, reset) ask a `y/n` confirmation
 * on the next line :
 *
 * @code
 * > tare
 * confirm 'tare' ? (y/n)
 * > y
 * taring all cells
 * offset cell 1 = -1212208.00
 * ...
 * @endcode
 *
 * Any reply other than `y` or `Y` cancels.
 *
 * @section commands Command reference
 *
 * | Command                       | Confirm? | Effect                                                                       |
 * | ---                           | ---      | ---                                                                          |
 * | `help`, `?`                   | no       | List all commands                                                            |
 * | `info`                        | no       | Show WiFi / SD / RTC / streaming / calibration state                         |
 * | `read`                        | no       | One immediate read : weights and raws of all 3 cells                         |
 * | `raw`                         | no       | One immediate read : raw 24-bit signed counts only                           |
 * | `stream on`                   | no       | Start CSV streaming on Serial (`time, w1, w2, w3, raw1, raw2, raw3`)         |
 * | `stream off`, `quiet`         | no       | Stop streaming                                                               |
 * | `tare`                        | yes      | Re-tare all 3 cells (reads current raw as new zero)                          |
 * | `tare <n>`                    | yes      | Re-tare cell `n` (1, 2 or 3) only                                            |
 * | `cal <n> <w>`                 | no       | Place reference weight `w` grams on cell `n`, recompute its scale            |
 * | `set offset <n> <v>`          | no       | Force the offset of cell `n` to `v` (RAM only ; use `save` to persist)       |
 * | `set scale <n> <v>`           | no       | Force the scale of cell `n` to `v` (RAM only ; `v` must be non-zero)         |
 * | `save`                        | yes      | Write all offsets and scales to SPIFFS                                       |
 * | `load`                        | no       | Reload all offsets and scales from SPIFFS                                    |
 * | `wifi`                        | no       | Retry WiFi connection (15 s timeout)                                         |
 * | `time YYYY-MM-DD HH:MM:SS`    | no       | Set the PCF8523 RTC                                                          |
 * | `reset`                       | yes      | Soft reboot the firmware                                                     |
 *
 * @section workflow Typical bench workflow
 *
 * Calibrate cell 1 with a 100 g reference weight :
 *
 * @code
 * > tare
 * confirm 'tare' ? (y/n)
 * > y                          # cells must be empty at this point
 * taring all cells
 * offset cell 1 = -1212208.00
 *
 *                              # place 100 g on cell 1
 * > cal 1 100.0
 * scale cell 1 = -15701.53
 *
 * > save
 * confirm 'save' ? (y/n)
 * > y
 * calibration saved to SPIFFS
 * @endcode
 *
 * Observe live readings :
 *
 * @code
 * > stream on
 * streaming ON
 * 16365,11.22,0.05,-0.02,-2475471,-1212268,-1213545
 * 16372,11.21,0.09, 0.04,-2476234,-1212156,-1213402
 * ...
 * @endcode
 *
 * Reset cell 1 to a known offset and scale (e.g. when boot tare was
 * polluted by GPIO 9 corruption) :
 *
 * @code
 * > set offset 1 -1212208
 * offset cell 1 = -1212208.00
 * > set scale 1 -15701.53
 * scale cell 1 = -15701.53
 * > save
 * @endcode
 *
 * @section impl Implementation notes
 *
 * - `readSerialLine()` accumulates bytes into a 64-byte buffer
 *   `cmdBuf` and returns `true` only when a complete line is received.
 *   Called once per `loop()` iteration.
 * - `executeCommand()` dispatches a finished line. Non-destructive
 *   commands run inline ; destructive ones go through `confirmAndRun()`
 *   which stores the request in `pendingCmd` and prompts for `y/n`.
 * - `runImmediate()` executes a (possibly confirmed) command. Used both
 *   for direct non-destructive commands and after `y` confirmation.
 * - `processSerialInput()` is the main entry point called from `loop()`.
 *
 * @section notes Notes on persistence
 *
 * `set offset` and `set scale` modify only the RAM state. Use `save` to
 * persist the values to SPIFFS. Note that the firmware boot path in auto
 * mode currently re-tares (overwriting any saved offset on the next
 * reboot). The scale survives. Future improvement : read offset from
 * SPIFFS at boot if `controller` has a saved value.
 */

/**
 * @brief Print the list of supported serial commands and a one-line
 * description of each.
 */
void printHelp() {
  Serial.println(F("--- STUAART serial commands ---"));
  Serial.println(F("help, ?         this list"));
  Serial.println(F("info            WiFi, SD, RTC, calibration state"));
  Serial.println(F("read            one immediate read (weights + raws) of all 3 cells"));
  Serial.println(F("raw             one immediate read of raw counts only"));
  Serial.println(F("stream on       start CSV streaming on Serial"));
  Serial.println(F("stream off      stop streaming (alias: quiet)"));
  Serial.println(F("tare            re-tare all 3 cells (asks confirmation)"));
  Serial.println(F("tare <n>        re-tare cell n=1..3 (asks confirmation)"));
  Serial.println(F("cal <n> <w>     reference weight w grams on cell n -> recompute scale"));
  Serial.println(F("set offset <n> <v>   force the offset of cell n to value v"));
  Serial.println(F("set scale <n> <v>    force the scale of cell n to value v"));
  Serial.println(F("save            write offsets+scales to SPIFFS (asks confirmation)"));
  Serial.println(F("load            reload offsets+scales from SPIFFS"));
  Serial.println(F("wifi            retry WiFi connection (15 s timeout)"));
  Serial.println(F("time YYYY-MM-DD HH:MM:SS    set RTC"));
  Serial.println(F("reset           soft reboot (asks confirmation)"));
}

/**
 * @brief Print a status summary on Serial : WiFi state and IP, SD card
 * presence, streaming state, mode-pin state, and per-cell offsets and
 * scales.
 */
void printInfo() {
  Serial.println(F("--- STUAART status ---"));
  Serial.print(F("WiFi      : "));
  Serial.println(wifiConnected ? "connected" : "disconnected");
  if (wifiConnected) {
    Serial.print(F("IP        : "));
    Serial.println(WiFi.localIP());
  }
  Serial.print(F("SD card   : "));
  Serial.println(sdInitialized ? "ready" : "not found");
  Serial.print(F("Streaming : "));
  Serial.println(streamOn ? "ON" : "OFF");
  Serial.print(F("Mode pin  : "));
  Serial.println(digitalRead(MODE_PIN) == LOW ? "auto" : "manual cal");
  for (byte i = 1; i <= 3; i++) {
    Serial.print(F("cell ")); Serial.print(i);
    Serial.print(F(" : offset=")); Serial.print(controller.get_offset(i));
    Serial.print(F("  scale=")); Serial.println(controller.get_scale(i));
  }
}

/**
 * @brief Read all 3 cells once and print both the calibrated weights
 * (in grams) and the underlying raw 24-bit signed counts. The weight
 * and raw on the same line come from the same HX711 conversion, so
 * the user can verify the calibration formula directly :
 * `weight = (raw - offset) / scale`.
 */
void readOnce() {
  long r1 = controller.read_raw_average(1);
  long r2 = controller.read_raw_average(2);
  long r3 = controller.read_raw_average(3);
  Serial.print(F("weights : "));
  Serial.print(controller.mass_from_raw(1, r1)); Serial.print(F(", "));
  Serial.print(controller.mass_from_raw(2, r2)); Serial.print(F(", "));
  Serial.println(controller.mass_from_raw(3, r3));
  Serial.print(F("raws    : "));
  Serial.print(r1); Serial.print(F(", "));
  Serial.print(r2); Serial.print(F(", "));
  Serial.println(r3);
}

/**
 * @brief Read all 3 cells once and print only the raw 24-bit signed
 * counts (no calibration applied). Useful for diagnosing HX711
 * corruption signatures by eye : `0xFFFFFF` (-1) means the read was
 * corrupted by flash bus contention or by an interrupt.
 */
void readRaw() {
  Serial.print(F("raws    : "));
  Serial.print(controller.read_raw_average(1)); Serial.print(F(", "));
  Serial.print(controller.read_raw_average(2)); Serial.print(F(", "));
  Serial.println(controller.read_raw_average(3));
}

/**
 * @brief Execute a command immediately, without further prompting.
 *
 * Called both for direct non-destructive commands (cal, set offset,
 * set scale, load, time) and from `processSerialInput()` once the
 * user has confirmed a destructive command with `y`.
 *
 * Recognised commands : `tare [n]`, `cal <n> <w>`, `set offset <n> <v>`,
 * `set scale <n> <v>`, `save`, `load`, `time YYYY-MM-DD HH:MM:SS`,
 * `reset`. See @ref serial_commands for the user-facing reference.
 *
 * @param cmd Null-terminated command line, without trailing newline.
 */
void runImmediate(const char* cmd) {
  if (strncmp(cmd, "tare", 4) == 0) {
    int n = 0;
    if (sscanf(cmd, "tare %d", &n) == 1 && n >= 1 && n <= 3) {
      Serial.print(F("taring cell ")); Serial.println(n);
      controller.tare(n);
      Serial.print(F("offset cell ")); Serial.print(n);
      Serial.print(F(" = ")); Serial.println(controller.get_offset(n));
    } else {
      Serial.println(F("taring all cells"));
      controller.tare_all_loadcells(false);
      for (byte i = 1; i <= 3; i++) {
        Serial.print(F("offset cell ")); Serial.print(i);
        Serial.print(F(" = ")); Serial.println(controller.get_offset(i));
      }
    }
  } else if (strncmp(cmd, "cal ", 4) == 0) {
    int n; float w;
    if (sscanf(cmd, "cal %d %f", &n, &w) == 2 && n >= 1 && n <= 3 && w > 0) {
      long raw = controller.read_scale_coeff_average(n);
      float offset = controller.get_offset(n);
      float scale = (raw - offset) / w;
      controller.set_scale(n, scale);
      Serial.print(F("scale cell ")); Serial.print(n);
      Serial.print(F(" = ")); Serial.println(scale);
    } else {
      Serial.println(F("usage: cal <cell 1..3> <weight_g>"));
    }
  } else if (strncmp(cmd, "set offset ", 11) == 0) {
    int n; float v;
    if (sscanf(cmd, "set offset %d %f", &n, &v) == 2 && n >= 1 && n <= 3) {
      controller.set_offset(n, v);
      Serial.print(F("offset cell ")); Serial.print(n);
      Serial.print(F(" = ")); Serial.println(controller.get_offset(n));
    } else {
      Serial.println(F("usage: set offset <cell 1..3> <value>"));
    }
  } else if (strncmp(cmd, "set scale ", 10) == 0) {
    int n; float v;
    if (sscanf(cmd, "set scale %d %f", &n, &v) == 2 && n >= 1 && n <= 3 && v != 0.0f) {
      controller.set_scale(n, v);
      Serial.print(F("scale cell ")); Serial.print(n);
      Serial.print(F(" = ")); Serial.println(controller.get_scale(n));
    } else {
      Serial.println(F("usage: set scale <cell 1..3> <non-zero value>"));
    }
  } else if (strcmp(cmd, "save") == 0) {
    for (byte i = 1; i <= 3; i++) {
      controller.save_offset_to_persistent_memory(i);
      controller.save_scale_coeff_to_persistent_memory(i);
    }
    Serial.println(F("calibration saved to SPIFFS"));
  } else if (strcmp(cmd, "load") == 0) {
    for (byte i = 1; i <= 3; i++) {
      controller.set_offset(i, controller.read_offset_from_persistent_memory(i));
    }
    controller.read_all_scale_coeff_from_persistent_memory();
    Serial.println(F("calibration loaded from SPIFFS"));
  } else if (strncmp(cmd, "time ", 5) == 0) {
    int yr, mo, dy, hr, mn, sc;
    if (sscanf(cmd, "time %d-%d-%d %d:%d:%d", &yr, &mo, &dy, &hr, &mn, &sc) == 6) {
      rtc.adjust(DateTime(yr, mo, dy, hr, mn, sc));
      Serial.println(F("RTC adjusted"));
    } else {
      Serial.println(F("usage: time YYYY-MM-DD HH:MM:SS"));
    }
  } else if (strcmp(cmd, "reset") == 0) {
    Serial.println(F("rebooting..."));
    delay(100);
    ESP.restart();
  }
}

/**
 * @brief Stage a destructive command and prompt for `y/n` confirmation.
 *
 * Stores the command in the global `pendingCmd[]` buffer and prints
 * the prompt. The next line received by `processSerialInput()` is
 * interpreted as the confirmation : `y` or `Y` runs the staged command
 * via `runImmediate()`, anything else cancels.
 *
 * @param cmd The command to stage. Copied into `pendingCmd[]`.
 */
void confirmAndRun(const char* cmd) {
  strncpy(pendingCmd, cmd, CMD_BUF_SIZE - 1);
  pendingCmd[CMD_BUF_SIZE - 1] = '\0';
  Serial.print(F("confirm '")); Serial.print(cmd); Serial.println(F("' ? (y/n)"));
}

/**
 * @brief Dispatch a finished command line.
 *
 * Pure routing : recognises the leading token and either runs the
 * command directly via `runImmediate()` (or inline for the
 * non-state-changing commands `help`, `info`, `read`, `raw`,
 * `stream on/off`, `wifi`) or stages it for confirmation via
 * `confirmAndRun()` (`tare`, `save`, `reset`).
 *
 * Unknown commands trigger an error message pointing at `help`.
 *
 * @param cmd Null-terminated command line, without trailing newline.
 */
void executeCommand(const char* cmd) {
  if (strcmp(cmd, "help") == 0 || strcmp(cmd, "?") == 0)              printHelp();
  else if (strcmp(cmd, "info") == 0)                                   printInfo();
  else if (strcmp(cmd, "read") == 0)                                   readOnce();
  else if (strcmp(cmd, "raw") == 0)                                    readRaw();
  else if (strcmp(cmd, "stream on") == 0)                              { streamOn = true;  Serial.println(F("streaming ON")); }
  else if (strcmp(cmd, "stream off") == 0 || strcmp(cmd, "quiet") == 0) { streamOn = false; Serial.println(F("streaming OFF")); }
  else if (strncmp(cmd, "cal ", 4) == 0)                               runImmediate(cmd);
  else if (strncmp(cmd, "set offset ", 11) == 0)                       runImmediate(cmd);
  else if (strncmp(cmd, "set scale ", 10) == 0)                        runImmediate(cmd);
  else if (strncmp(cmd, "tare", 4) == 0)                               confirmAndRun(cmd);
  else if (strcmp(cmd, "save") == 0)                                   confirmAndRun(cmd);
  else if (strcmp(cmd, "load") == 0)                                   runImmediate(cmd);
  else if (strcmp(cmd, "wifi") == 0)                                   connectToWifi();
  else if (strncmp(cmd, "time ", 5) == 0)                              runImmediate(cmd);
  else if (strcmp(cmd, "reset") == 0)                                  confirmAndRun(cmd);
  else {
    Serial.print(F("unknown command: ")); Serial.println(cmd);
    Serial.println(F("type 'help' for the list"));
  }
}

/**
 * @brief Non-blocking line accumulator.
 *
 * Reads whatever bytes are currently available on `Serial` and appends
 * them to `cmdBuf[]` (capped at `CMD_BUF_SIZE - 1` to leave room for
 * the null terminator). Returns `true` only when a complete line has
 * been received (terminated by `\n` or `\r`). Empty lines are ignored.
 *
 * Designed to be called once per `loop()` iteration so the firmware
 * can keep sampling the load cells while the user types.
 *
 * @return `true` if a full line is now in `cmdBuf` and ready for
 * dispatch ; `false` otherwise.
 */
bool readSerialLine() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (cmdLen == 0) continue;
      cmdBuf[cmdLen] = '\0';
      cmdLen = 0;
      return true;
    }
    if (cmdLen < CMD_BUF_SIZE - 1) {
      cmdBuf[cmdLen++] = c;
    }
  }
  return false;
}

/**
 * @brief Main entry point of the serial command interface, called once
 * per `loop()` iteration.
 *
 * If `readSerialLine()` has not yet accumulated a full line, returns
 * immediately. Otherwise echoes the line (`> <cmd>`) and routes :
 *
 * - if a destructive command is currently staged in `pendingCmd[]`,
 *   the line is interpreted as a `y/n` confirmation : `y` or `Y` runs
 *   it via `runImmediate()`, anything else cancels.
 * - otherwise, the line is dispatched via `executeCommand()`.
 */
void processSerialInput() {
  if (!readSerialLine()) return;
  Serial.print(F("> ")); Serial.println(cmdBuf);
  if (pendingCmd[0] != '\0') {
    if (cmdBuf[0] == 'y' || cmdBuf[0] == 'Y') {
      runImmediate(pendingCmd);
    } else {
      Serial.println(F("cancelled."));
    }
    pendingCmd[0] = '\0';
  } else {
    executeCommand(cmdBuf);
  }
}

/**
 * @brief Arduino entry point : initialize peripherals and choose mode.
 *
 * Order :
 * 1. Open Serial at 115200 baud.
 * 2. Configure the four LED pins as outputs.
 * 3. Initialize the SD card (`SD.begin`) once. Set `sdInitialized` to
 *    track success ; subsequent SD operations no-op gracefully if it
 *    failed.
 * 4. Try WiFi via @ref connectToWifi (15 s timeout).
 * 5. Configure the mode pin (`MODE_PIN`, GPIO 13) as `INPUT_PULLDOWN`
 *    and register the three load cells with the controller.
 * 6. Branch on `MODE_PIN` :
 *    - LOW (SW1 OFF) : auto mode. Tare all cells live (compensates
 *      drift) and load scale coefficients from SPIFFS.
 *    - HIGH (SW1 ON) : manual calibration mode. Interactive tare and
 *      scale calibration via the legacy LoadCellController prompts on
 *      Serial.
 * 7. Start the PCF8523 RTC.
 * 8. Print a hint pointing at `help` and exit to @ref loop.
 *
 * @note In auto mode, the boot tare overwrites any offset previously
 * persisted to SPIFFS. To force a known offset, use
 * `set offset <n> <v>` then `save` *after* boot.
 */
void setup()
{
  Serial.begin(115200);
  pinMode(pinLED1, OUTPUT);
  pinMode(pinLED2, OUTPUT);
  pinMode(pinLED3, OUTPUT);
  pinMode(pinLED4, OUTPUT);

  if (SD.begin(SS_PIN)) {
    sdInitialized = true;
    Serial.println("SD card initialized");
  } else {
    sdInitialized = false;
    Serial.println("SD card not found, data goes to Serial only");
  }

  connectToWifi();

  pinMode(MODE_PIN, INPUT_PULLDOWN);
  controller.add_loadcell(loadCell1, 9, 17); // loadcell number, dout, sck
  controller.add_loadcell(loadCell2, 27, 26); // loadcell number, dout, sck
  controller.add_loadcell(loadCell3, 16, 25); // loadcell number, dout, sck
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

  startRealTimeClock();

  Serial.println();
  Serial.println(F("Type 'help' for the list of serial commands."));
  Serial.println(F("Streaming is OFF; type 'stream on' to see live readings."));
}


/**
 * @brief Arduino main loop : sample the cells and service the IO interfaces.
 *
 * Each iteration runs four steps :
 *
 * 1. **Serial command interface** (@ref processSerialInput) : checks
 *    Serial for a finished command line and dispatches it.
 * 2. **Local data save** (@ref saveData) : reads the 3 cells once and
 *    writes the row to SD (and Serial if `streamOn`). The pacing
 *    `if (currentMillis - saveTimestamp >= SAVE_DATA_INTERVAL)` is
 *    effectively unbounded since `SAVE_DATA_INTERVAL = 0` ; throughput
 *    is bounded by the HX711 80 Hz conversion rate.
 * 3. **WiFi reconnection** : on a 1-hour interval
 *    (`RECONNECT_WIFI_INTERVAL = 3600000`), retry @ref connectToWifi
 *    so a transient network outage recovers automatically.
 * 4. **HTTP server** : if a client is connected, parse the GET line,
 *    open the requested CSV from SD (default = today's), and stream
 *    it back over the socket in 128-byte chunks. The client uses this
 *    to pull data without a USB connection.
 */
void loop() {
  unsigned long currentMillis = millis();

  // --- 0. Serial command interface ---
  processSerialInput();

  // --- 1. Gestion de la sauvegarde locale (SD) ---
  if (abs((long)(currentMillis - saveTimestamp)) >= SAVE_DATA_INTERVAL) {
    saveTimestamp = currentMillis;
    saveData();
  }

  // --- 2. Gestion de la reconnexion WiFi ---
  if (abs((long)(currentMillis - reconnectTimestamp)) >= RECONNECT_WIFI_INTERVAL) {
    reconnectTimestamp = currentMillis;
    connectToWifi();
  }

  // --- 3. Serveur Web (Réponse au script Python) ---
  WiFiClient client = server.available(); 

  if (client) {
    Serial.println("\n[Serveur] Nouvelle requête reçue !");
    String clientData = "";
    
    while (client.connected()) {
      if (client.available()) {
        char c = client.read();
        clientData += c;

        // On analyse la requête dès la fin de la première ligne (le GET)
        if (c == '\n') {
          Serial.print("[Serveur] Ligne reçue : "); Serial.print(clientData);

          String fileNameToOpen = "";
          
          // Extraction du nom du fichier
          if (clientData.indexOf("GET /") >= 0) {
            int startPos = clientData.indexOf("/") + 1; // On saute le premier slash
            int endPos = clientData.indexOf(" HTTP");
            if (endPos > startPos) {
              fileNameToOpen = clientData.substring(startPos, endPos);
              fileNameToOpen.trim();
            }
          }

          // Si l'URL est vide ou juste "/", on donne le fichier d'aujourd'hui
          if (fileNameToOpen == "" || fileNameToOpen == "/") {
            getTodaysDate();
            fileNameToOpen = today; 
          }

          // Nettoyage de sécurité : on s'assure d'avoir UN SEUL slash au début pour la SD
          if (!fileNameToOpen.startsWith("/")) {
            fileNameToOpen = "/" + fileNameToOpen;
          }
          // Si on a accidentellement un double slash "//", on le réduit à un seul
          fileNameToOpen.replace("//", "/");

          myFile = SD.open(fileNameToOpen, FILE_READ);

          if (myFile) {
            Serial.print("[Serveur] Envoi du fichier : "); Serial.println(fileNameToOpen);
            
            // En-têtes HTTP
            client.println("HTTP/1.1 200 OK");
            client.println("Content-Type: text/csv");
            client.println("Connection: close");
            client.println(); // Ligne vide cruciale
            
            // On envoie le nom du fichier (sans le slash pour Python)
            String nameForPython = fileNameToOpen;
            if (nameForPython.startsWith("/")) nameForPython.remove(0, 1);
            client.println(nameForPython);

            // Transfert par blocs
            uint8_t buffer_wifi[128];
            while (myFile.available()) {
              int bytesRead = myFile.read(buffer_wifi, sizeof(buffer_wifi));
              client.write(buffer_wifi, bytesRead);
            }
            myFile.close();
            Serial.println("[Serveur] Transfert terminé avec succès.");
          } 
          else {
            Serial.print("[Serveur] Erreur 404 : Fichier introuvable -> "); Serial.println(fileNameToOpen);
            client.println("HTTP/1.1 404 Not Found");
            client.println();
            client.println("File Not Found on SD");
          }

          // --- CRUCIAL : On vide le reste du buffer (les headers Python) ---
          while(client.available()) {
            client.read(); 
          }
          break; 
        }
      }
    }
    
    delay(15);
    client.stop();
    Serial.println("[Serveur] Connexion fermée.\n");
  }
}