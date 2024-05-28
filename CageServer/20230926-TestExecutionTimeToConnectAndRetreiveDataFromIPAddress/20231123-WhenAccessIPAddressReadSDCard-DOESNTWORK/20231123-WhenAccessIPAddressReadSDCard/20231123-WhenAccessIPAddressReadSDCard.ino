/*
 WiFi Web Server LED Blink

 A simple web server that lets you blink an LED via the web.
 This sketch will print the IP address of your WiFi Shield (once connected)
 to the Serial monitor. From there, you can open that address in a web browser
 to turn on and off the LED on pin 5.

 If the IP address of your shield is yourAddress:
 http://yourAddress/H turns the LED on
 http://yourAddress/L turns it off

 This example is written for a network using WPA2 encryption. For insecure
 WEP or WPA, change the Wifi.begin() call and use Wifi.setMinSecurity() accordingly.

 Circuit:
 * WiFi shield attached
 * LED attached to pin 5

 created for arduino 25 Nov 2012
 by Tom Igoe

ported for sparkfun esp32 
31.01.2017 by Jan Hendrik Berlin
 
 */

#include <WiFi.h>
#include <SD.h>
#include <SPI.h>
#include <time.h>

File myFile; // initialize the file
const int SS_pin = 6; // seule pin de carte SD à spécifier 
char buf[100];

int reading = 10;

const char* ntpServer = "pool.ntp.org";
const long gmtOffset_sec = -18000;
const int daylightOffset_sec = 3600;

const char* ssid     = "Colloque-CRIUSMQ"; //of the router
const char* password = "29e6c5aac7"; //password of the router
WiFiServer server(80); // créer un serveur qui écoute les clients qui veulent s'y connecter 

char day_of_experiment[] = "2023.10.02";
char today[11];

void connect_to_wifi() {
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



void append_file(fs::FS &fs, const char * path, float message){
  Serial.printf("Appending to file: %s\n", path);

  while (!Serial) {
  ; // wait for serial port to connect. Needed for native USB port only
  }

  if (!SD.begin(SS_pin)) {
  Serial.println("initialization failed!");
  return;
  }

  myFile = fs.open(path, FILE_APPEND);
  if(!myFile){
    Serial.println("Failed to open file for appending");
    return;
  }
  if (myFile) {
    struct tm timeinfo;
    if(!getLocalTime(&timeinfo)){
      Serial.println("Failed to obtain time");
    return;
    }
    Serial.print(("Appending to file..."));
    myFile.print(&timeinfo, "%H:%M:%S");
    myFile.print(",");
    myFile.println(message);
    // close the file:
    myFile.close();
    Serial.println("done.");
  } else {
    Serial.println("Append failed");
  }
  myFile.close();
}



void file_write(fs::FS &fs, const char * path, float message) {

    while (!Serial) {
    ; // wait for serial port to connect. Needed for native USB port only
    }

    Serial.print("Initializing SD card...");

    if (!SD.begin(SS_pin)) {
      Serial.println("initialization failed!");
      return;
    }
    Serial.println("initialization done.");

    // open the file. note that only one file can be open at a time,
    myFile = SD.open(path, FILE_WRITE);

    // if the file opened okay, write to it:
    if (myFile) {
      struct tm timeinfo;
      if(!getLocalTime(&timeinfo)){
        Serial.println("Failed to obtain time");
      return;
      }
      Serial.print(("Writing to file..."));
      myFile.print(&timeinfo, "%H:%M:%S");
      myFile.print(",");
      myFile.println(message);
      // close the file:
      myFile.close();
      Serial.println("done.");
    } else {
      // if the file didn't open, print an error:
      Serial.println("error opening file");
    }
}

void get_todays_date(){
  struct tm timeinfo;
  if(!getLocalTime(&timeinfo)){
    Serial.println("Failed to obtain time");
  return;
  }
  int year = timeinfo.tm_year + 1900;
  int month = timeinfo.tm_mon +1;
  int day = timeinfo.tm_mday;
  snprintf(today, sizeof(today), "%04d.%02d.%02d", year, month, day);

}



void setup()
{
    Serial.begin(115200);
    connect_to_wifi();
    configTime(gmtOffset_sec, daylightOffset_sec, ntpServer);

}

void loop(){
  get_todays_date();

  //if today == day_of_experiment, alors on append dans le fichier
  //else, alors on crée un nouveau fichier avec le nom today, puis day_of_experiment = today
  int comparison = strcmp(today, day_of_experiment);
  if (comparison == 0) {
    char path_of_file[strlen(day_of_experiment)+9];
    snprintf(path_of_file, sizeof(path_of_file), "/%s.csv", day_of_experiment);
    append_file(SD, path_of_file, reading);

  } else {
    int i;
    for (i = 0; i < 11; ++i){
      day_of_experiment[i] = today[i];
    }
    char path_of_file[strlen(day_of_experiment)+9];
    snprintf(path_of_file, sizeof(path_of_file), "/%s.csv", day_of_experiment);
    file_write(SD, path_of_file, reading);
  }

  delay(1000);



 WiFiClient client = server.available();   // listen for incoming client

  if (client) {                             // if you get a client,
    Serial.println("New Client.");           // print a message out the serial port
    String currentLine = "";                // make a String to hold incoming data from the client
    while (client.connected()) {            // loop while the client's connected
      if (client.available()) {             // if there's bytes to read from the client,
        char c = client.read();             // read a byte, then
        Serial.write(c);                    // print it out the serial monitor
        if (c == '\n') {                    // if the byte is a newline character

          // if the current line is blank, you got two newline characters in a row.
          // that's the end of the client HTTP request, so send a response:
          if (currentLine.length() == 0) {
            // HTTP headers always start with a response code (e.g. HTTP/1.1 200 OK)
            // and a content-type so the client knows what's coming, then a blank line:
            client.println("HTTP/1.1 200 OK");
            client.println("Content-type:text/html");
            client.println();

            // the content of the HTTP response follows the header:
            if (!SD.begin(SS_pin)) {
              Serial.println("initialization failed!");
            return;
            }

            myFile = SD.open(path_of_file, FILE_READ);
            if (myFile) {
              int rlen = myFile.available();
              char ch = myFile.read(); // read the first character
              myFile.read(buf, rlen - 1); // read the remaining to buffer
              client.print(ch);
              client.print(buf);
              myFile.close();
            } else {
              Serial.print(F("SD Card: error on opening file"));
              }

            // The HTTP response ends with another blank line:
            client.println();
            // break out of the while loop:
            break;
          } else {    // if you got a newline, then clear currentLine:
            currentLine = "";
          }
        } else if (c != '\r') {  // if you got anything else but a carriage return character,
          currentLine += c;      // add it to the end of the currentLine
        }
      }
    }
    // close the connection:
    client.stop();
    Serial.println("Client Disconnected.");
  }
}
