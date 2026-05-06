#include "FS.h"
#include "SPIFFS.h"

#define FORMAT_SPIFFS_IF_FAILED true

void setup(){
    Serial.begin(115200);
    if(!SPIFFS.begin(FORMAT_SPIFFS_IF_FAILED)){
        Serial.println("SPIFFS Mount Failed");
        return;
    }
    Serial.println("**** SPIFFS is ready to use ****");
}

void loop() {
  // put your main code here, to run repeatedly:

}
