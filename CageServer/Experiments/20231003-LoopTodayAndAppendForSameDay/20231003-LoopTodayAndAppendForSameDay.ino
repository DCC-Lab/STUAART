#include <WiFi.h>
#include <SD.h>
#include <SPI.h>
#include <time.h>

File myFile; // initialize the file
const int SS_pin = 4; // seule pin de carte SD à spécifier 

int data = 1;

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

void append_file(fs::FS &fs, const char * path, int message){
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


void file_write(fs::FS &fs, const char * path, int message) {

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

void acquire_data(){
  data += 1; // produce fake data
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

void setup() {
  Serial.begin(115200);
  connect_to_wifi();
  configTime(gmtOffset_sec, daylightOffset_sec, ntpServer);
}

void loop() {
  acquire_data();
  get_todays_date();

  //if today == day_of_experiment, alors on append dans le fichier
  //else, alors on crée un nouveau fichier avec le nom today, puis day_of_experiment = today
  int comparison = strcmp(today, day_of_experiment);
  if (comparison == 0) {
    char path_of_file[strlen(day_of_experiment)+9];
    snprintf(path_of_file, sizeof(path_of_file), "/%s.csv", day_of_experiment);
    append_file(SD, path_of_file, data);

  } else {
    int i;
    for (i = 0; i < 11; ++i){
      day_of_experiment[i] = today[i];
    }
    char path_of_file[strlen(day_of_experiment)+9];
    snprintf(path_of_file, sizeof(path_of_file), "/%s.csv", day_of_experiment);
    file_write(SD, path_of_file, data);
  }

  delay(3000);
}
