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
const int SS_pin = 2; // seule pin de carte SD à spécifier 

int reading = 10;

const char* SSID     = "Colloque-CRIUSMQ"; //of the router
const char* PASSWORD = "29e6c5aac7"; //password of the router
WiFiServer server(80); // créer un serveur qui écoute les clients qui veulent s'y connecter 

const char* REFRESH_CODE = "refresh";

char today[11];

void connect_to_wifi() {
      // We start by connecting to a WiFi network
    Serial.println();
    Serial.println();
    Serial.print("Connecting to ");
    Serial.println(SSID);
    WiFi.begin(SSID, PASSWORD);
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


void setup()
{
    Serial.begin(115200);
    connect_to_wifi();
}

void loop(){

 WiFiClient client = server.available();   // listen for incoming client

  if (client) {                             // if you get a client,
    Serial.println("New Client.");           // print a message out the serial port
    String clientData = "";                // make a String to hold incoming data from the client
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

            if(!SD.begin(SS_pin)){
              Serial.println("Card Mount Failed");
              return;
              }
              
            uint8_t cardType = SD.cardType();
            
            if(cardType == CARD_NONE){
              Serial.println("No SD card attached");
              return;
            }

            if (clientData.indexOf(REFRESH_CODE) >= 0) { // If the refresh code is passed, give the client the newest data
              myFile = SD.open("/test_2.csv"); // This would be the 'today' file not yet completed.
            }
            else {
              myFile = SD.open("/test_1.csv");
            }
            
            if(!myFile) {
              Serial.println("Failed to open file for reading");
              return;
            }

            Serial.println("Read from file : ");
            while(myFile.available()) {
              client.println(myFile.read()); // ICI : print in decimal
            }
            myFile.close();

            // The HTTP response ends with another blank line:
            client.println();
            // break out of the while loop:
            break;
          }
        } else {
          clientData += c;
        }
      }
    }
    // close the connection:
    client.stop();
    Serial.println("Client Disconnected.");
  }
}
