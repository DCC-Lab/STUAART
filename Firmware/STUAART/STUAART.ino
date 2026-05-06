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
    Serial.println("WiFi unavailable, continuing without network. Data will go to Serial.");
  }
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
    while (1) delay(10);
  }

  else {
    Serial.println("RTC setup succeeded");
  }
  rtc.adjust(DateTime(F(__DATE__), F(__TIME__))); 
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


/*
Gets through the time server yesterday's date.
*/
void getYesterdaysDate(){
  DateTime now = rtc.now(); // Get the current date and time from the RTC
  int year = now.year();
  int month = now.month();
  int day = now.day() - 1;

  snprintf(today, sizeof(today), "/%04d.%02d.%02d.csv", year, month, day);
}


/*
Writes a file in the SD card at the specified path. Puts in the specified message.
Writes in the serial consol error if it doesn't succeed.
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


void flushBufferToSD(){
  while (head != tail || bufferFull) {
    myFile.print(buffer[tail]);
    tail = (tail + 1) % BUFFER_SIZE;
    bufferFull = false;
  }
  myFile.print("--, --, --, -- \n");
}



/*
Writes a clean file header for csv file.
*/
void writeFileHeader(char *file_name) {
  createFile(file_name, "time (ms), reading 1, reading 2, reading 3", FILE_WRITE);
}


/*
This method will be where we save the real data. For now it creates fake data.
*/
void saveData()
{
  float weight1 = controller.get_weight(1);
  float weight2 = controller.get_weight(2);
  float weight3 = controller.get_weight(3);

  String fileLine = "";
  fileLine += String(millis(), DEC) + "," + weight1 + "," + weight2 + "," + weight3 + "\n";

  if (sdInitialized) {
    getTodaysDate();
    if (!SD.exists(today)) {
      writeFileHeader(today);
    }
    writeFile(today, fileLine.c_str(), FILE_APPEND);
  }

  if (!wifiConnected) {
    Serial.print(fileLine);
  }
}



/*
Initializes console, connects to the wifi, the local time and creates the initial test data.
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

}


/*
Loops, waiting for a client connection.
When there is a client, reads the connection data, then sends either yesterday's data or today's.
Sends today's if the REFRESH_CODE is present in the connection data.
*/
void loop() {
  unsigned long currentMillis = millis();

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