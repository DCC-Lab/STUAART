#include <SD.h>
#include <AUnit.h>
#include "constants.h"
#include "LoadCell.h"
#include "logger.h"

test(init_load_cell) {
  LoadCell lc = LoadCell(DOUT1_PIN, SCK1_PIN, GAIN);
  assertTrue(lc.initialize());
}

test(looking_for_sd_pin) {
  int i = 0;
  for (i=0; i<40; i++) {
    Serial.print(i);
    Serial.print(" = ");
    Serial.println(SD.begin(i));
  }
}

