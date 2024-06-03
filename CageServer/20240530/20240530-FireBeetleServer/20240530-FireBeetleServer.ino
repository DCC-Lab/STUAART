#include <WiFi.h>
#include <SD.h>
#include <SPI.h>
#include <time.h>

File myFile;           // initialize the file
const int SS_PIN = 21; // seule pin de carte SD à spécifier

const char *SSID = "TP-Link_37E9"; // of the router
const char *PASSWORD = "15351210"; // password of the router
WiFiServer server(80);             // créer un serveur qui écoute les clients qui veulent s'y connecter

const char *REFRESH_CODE = "refresh"; // must be the same as in the python code, otherwise they won't be able to recognize one another

//Infos of the time provider server
const char *NTP_SERVER = "pool.ntp.org";
const long GMT_OFFSET_SEC = -18000;
const int DAYLIGHT_OFFSET_SEC = 3600;

//Buffer chars for saving files
char today[16];
char yesterday[16];

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
  int minute = timeinfo.tm_min;//TODO: remove minute, this is to test the behaviour is OK.
  snprintf(today, sizeof(today), "/%04d.%02d.%02d.csv", year, month, minute);
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
  int minute = timeinfo.tm_min-1;//TODO: remove minute, this is to test the behaviour is OK.
  snprintf(yesterday, sizeof(yesterday), "/%04d.%02d.%02d.csv", year, month, minute);
}


/*
Writes a file in the SD card at the specified path. Puts in the specified message.
Writes in the serial consol error if it doesn't succeed.
*/
void writeFile(const char *path, char *message, char *mode)
{
  while (!Serial)
  {
    ; // wait for serial port to connect. Needed for native USB port only
  }

  Serial.print("Initializing SD card...");

  if (!SD.begin(SS_PIN))
  {
    Serial.println("initialization failed!");
    return;
  }
  Serial.println("initialization done.");

  // open the file. note that only one file can be open at a time,
  myFile = SD.open(path, mode);

  // if the file opened okay, write to it:
  if (myFile)
  {
    Serial.print(("Writing to file..."));
    myFile.println(message);
    // close the file:
    myFile.close();
    Serial.println("done.");
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
    writeFile(file_name, "time (ms), reading 1, reading 2\n", FILE_WRITE);
}


/*
This method will be where we save the real data. For now it creates fake data.
*/
void saveData()
{
  getTodaysDate();

  if (!SD.exists(today))
  {
    writeFileHeader(today);
  }
  else
  {//Commented out for now for testing
    // writeFile(today, "\n 1", FILE_APPEND);
  }
}


/*
Initializes console, connects to the wifi, the local time and creates the initial test data.
*/
void setup()
{
  Serial.begin(115200);

  connectToWifi();

  configTime(GMT_OFFSET_SEC, DAYLIGHT_OFFSET_SEC, NTP_SERVER);
}


/*
Loops, waiting for a client connection.
When there is a client, reads the connection data, then sends either yesterday's data or today's.
Sends today's if the REFRESH_CODE is present in the connection data.
*/
void loop()
{
  saveData();

  WiFiClient client = server.available(); // listen for incoming client

  if (client)
  {                                // if you get a client,
    Serial.println("New Client."); // print a message out the serial port
    String clientData = "";        // make a String to hold incoming data from the client
    char c = 'v';
    char oldC = ' ';
    while (client.connected())
    { // loop while the client's connected
      if (client.available())
      {                    // if there's bytes to read from the client,
        c = client.read(); // read a byte, then
        Serial.write(c);   // print it out the serial monitor
        clientData += c;
      }
      else
      {
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

        if (clientData.indexOf(REFRESH_CODE) >= 0)
        {             
          getTodaysDate();       // If the refresh code is passed, give the client the newest data
          myFile = SD.open(today); // This would be the 'today' file not yet completed.
        }
        else
        {
          getYesterdaysDate();
          if (SD.exists(yesterday))
          {
            myFile = SD.open(yesterday);
          }
          else
          {
            Serial.println("yesterdays file doesnt exist!");
            myFile = SD.open(today);
          }
        }

        if (!myFile)
        {
          Serial.println("Failed to open file for reading");
          return;
        }

        Serial.println("Read from file : ");
        
        client.println("HTTP/1.1 200 OK");
        client.println("Content-type:text/html");
        client.println();
        client.println(myFile.name());
        while (myFile.available())
        {
          char c = myFile.read();
          Serial.print(c);
          client.print(c); // ICI : print in decimal
        }
        myFile.close();

        // The HTTP response ends with another blank line:
        client.println();
        // break out of the while loop:
        break;
      }
      oldC = c;
    }
    // close the connection:
    client.stop();
    Serial.println("Client Disconnected.");
  }
}
