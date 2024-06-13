#include <WiFi.h>
#include <SD.h>
#include <SPI.h>
#include <time.h>

File myFile; // initialize the file
const int SS_pin = 4; // seule pin de carte SD à spécifier 

int value = 10;

const char* ntpServer = "pool.ntp.org";
const long gmtOffset_sec = -18000;
const int daylightOffset_sec = 3600;

const char* ssid     = "Colloque-CRIUSMQ"; //of the router
const char* password = "29e6c5aac7"; //password of the router
WiFiServer server(80); // créer un serveur qui écoute les clients qui veulent s'y connecter 


void file_write(int reading) {
    struct tm timeinfo;

    if(!getLocalTime(&timeinfo)){
      Serial.println("Failed to obtain time");
    return;
    }

     while (!Serial) {
     ; // wait for serial port to connect. Needed for native USB port only
     }

    Serial.print("Initializing SD card...");

    if (!SD.begin(SS_pin)) {
      Serial.println("initialization failed!");
      return;
    }
    Serial.println("initialization done.");
    
    char file[25];
    int year = timeinfo.tm_year + 1900;
    int month = timeinfo.tm_mon +1;
    int day = timeinfo.tm_mday;

    snprintf(file, sizeof(file), "/%04d.%02d.%02d.csv", year, month, day);
    // strftime(file, 25, "/%Y.%B.%d.csv", &timeinfo);
    Serial.println(file);

    // open the file. note that only one file can be open at a time,
    myFile = SD.open(file, FILE_WRITE);

    // if the file opened okay, write to it:
    if (myFile) {
      Serial.print(("Writing to file..."));
      myFile.print(&timeinfo, "%H:%M:%S");
      myFile.print(",");
      myFile.println(reading);
      // close the file:
      myFile.close();
      Serial.println("done.");
    } else {
      // if the file didn't open, print an error:
      Serial.println("error opening file");
    }
}

void connect_to_wifi(){
      // We start by connecting to a WiFi network
    Serial.println();
    Serial.println();
    Serial.print("Connecting to ");
    Serial.println(ssid);
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println("");
    Serial.println("WiFi connected.");
    Serial.println("IP address: ");
    Serial.println(WiFi.localIP());
    server.begin();
}

void setup(){
    Serial.begin(115200);

    connect_to_wifi();

    configTime(gmtOffset_sec, daylightOffset_sec, ntpServer);

    file_write(value, path);
}


void loop(){
}



