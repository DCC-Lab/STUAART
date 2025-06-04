#include <cassert>
#include "Logger.h"
#include "LoadCellController.h"

#if defined(ARDUINO_ARCH_ESP32)
#include "FS.h"
#include "SPIFFS.h"
// Verify if the board is based on a Atmega328P chip, like Arduino Uno
#elif defined(__AVR_ATmega328P__)
#include <EEPROM.h>
#endif

#define assert_valid_load_cell_num(x) assert(loadcell_num > 0 && loadcell_num <= number_of_loadcells())

LoadCellController::LoadCellController() {
  set_default_format(Log);
}

void LoadCellController::add_loadcell(LoadCell &loadcell) {
  loadcells[n_loadcell] = &loadcell;
  n_loadcell++;
}

void LoadCellController::add_loadcell(byte dout, byte sck, byte gain) {

    LoadCell* loadcell = new LoadCell(dout, sck, gain);
    if (!loadcell->initialize()) {
        Log.fatalln("The circuit and the HX711 chip(s) should be verified");
    }
    add_loadcell(*loadcell);
}

void LoadCellController::tare_all_loadcells(bool wait_for_user) {
  bool _resume;
  Log.traceln(F("Taring of all loadcells"));

  if (wait_for_user == true) {
    Log.traceln(F("Remove any load applied to the loadcell."));
    Log.infoln(F("Send 't' from serial monitor when ready."));
    _resume = false;
  } else if (wait_for_user == false) {
    _resume = true;
  }

  while (_resume == false) {
    if (Serial.available() > 0) {
      char serial_reading = Serial.read();
      if (serial_reading == 't') {
        Log.traceln(F("Start of taring..."));
        _resume = true;
      }
    }
  }

  for (byte i = 1; i <= number_of_loadcells(); i++) {
    Log.traceln(F("Taring of LoadCell #%d ..."), i);
    tare(i);
    Log.traceln(F("Saving offset [%d] of LoadCell #%d ..."), get_offset(i), i);
    save_offset_to_persistent_memory(i);
  }
}

void LoadCellController::calibrate_all_loadcells() {
  Log.traceln(F("Start of all LoadCells calibration"));

  for (byte i = 1; i <= number_of_loadcells(); i++) {
    calibrate_scale_coeff(i);

    Log.traceln(F("Saving scale coeff of LoadCell #%d ..."), i);
    save_scale_coeff_to_persistent_memory(i);
    Log.traceln("Scale factor [%f]", get_scale(i));
    Log.traceln("done");
  }
  Log.traceln(F("All LoadCells are calibrated"));
}

void LoadCellController::read_all_scale_coeff_from_persistent_memory() {
  Log.traceln(F("Reading all scale coefficients from persistent memory"));

  for (byte i = 1; i <= number_of_loadcells(); i++) {
    Log.traceln(F("Reading scale coeff of LoadCell #%d"), i);
    float scale_coeff = read_scale_coeff_from_persistent_memory(i);
    set_scale(i, scale_coeff);
    Log.traceln("Scale coefficient: [%f]", scale_coeff);
    Log.traceln("done");
  }
}


void LoadCellController::easy_start_with_params(
  byte loadcell_num,
  byte dout,
  byte pd_sck,
  bool calibrate_offset,
  bool calibrate_scale,
  bool read_offset_persistent_memory,
  bool read_scale_persistent_memory,
  bool save_offset_persistent_memory,
  bool save_scale_persistent_memory,
  float tare_offset,
  float scale_coeff,
  byte gain) {
  easy_handle_exceptions(
    loadcell_num,
    calibrate_offset,
    calibrate_scale,
    read_offset_persistent_memory,
    read_scale_persistent_memory,
    save_offset_persistent_memory,
    save_scale_persistent_memory,
    tare_offset,
    scale_coeff);

  LoadCell *loadcell_ptr = loadcells[loadcell_num - 1];

  loadcell_ptr->begin(dout, pd_sck, gain);

  loadcell_ptr->set_offset(tare_offset);
  loadcell_ptr->set_scale(scale_coeff);

  easy_read_from_persistent_memory_with_params(
    loadcell_num,
    read_offset_persistent_memory,
    read_scale_persistent_memory);

  easy_calibration_with_params(
    loadcell_num,
    calibrate_offset,
    calibrate_scale);  // set offset and scale with calibration or with value

  easy_save_to_persistent_memory_with_params(
    loadcell_num,
    save_offset_persistent_memory,
    save_scale_persistent_memory);  // set offset and scale with calibration or with value
  Log.traceln(F("---------***---------"));
}

void LoadCellController::easy_read_from_persistent_memory_with_params(
  byte loadcell_num,
  bool read_offset,
  bool read_scale) {
  LoadCell *loadcell_ptr = loadcells[loadcell_num - 1];

  if (read_offset && read_scale) {
    loadcell_ptr->set_offset(read_offset_from_persistent_memory(loadcell_num));
    loadcell_ptr->set_scale(read_scale_coeff_from_persistent_memory(loadcell_num));
    Log.traceln(F("Offset and scale coefficient read from memory"));
    Log.trace(F("Offset: %f"), loadcell_ptr->get_offset());
    Log.trace(F("Scale coefficient: %f"), loadcell_ptr->get_scale());
    Log.traceln(F("---------***---------"));
  } else if (read_offset && !read_scale) {
    loadcell_ptr->set_offset(read_offset_from_persistent_memory(loadcell_num));
    Log.traceln(F("---------***---------"));
    Log.traceln(F("Offset read from memory"));
    Log.trace(F("Offset: %f"), loadcell_ptr->get_offset());
  } else if (!read_offset && read_scale) {
    loadcell_ptr->set_scale(read_scale_coeff_from_persistent_memory(loadcell_num));
    Log.traceln(F("---------***---------"));
    Log.traceln(F("Scale coefficient read from memory"));
    Log.trace(F("Scale coefficient: %f"), loadcell_ptr->get_scale());
  }
}

void LoadCellController::easy_calibration_with_params(
  byte loadcell_num,
  bool calibrate_offset,
  bool calibrate_scale) {
  LoadCell *loadcell_ptr = loadcells[loadcell_num - 1];
  if (calibrate_offset && calibrate_scale) {
    calibrate_both_params(loadcell_num);  // set offset and scale
    Log.trace(F("Offset: %f"), loadcell_ptr->get_offset());
    Log.trace(F("Scale coefficient: %f"), loadcell_ptr->get_scale());
  } else if (calibrate_offset && !calibrate_scale) {
    calibrate_tare_offset(loadcell_num);  // set offset
  } else if (!calibrate_offset && calibrate_scale) {
    calibrate_scale_coeff(loadcell_num);  // set scale
  }
}

void LoadCellController::easy_save_to_persistent_memory_with_params(
  byte loadcell_num,
  bool save_offset,
  bool save_scale) {
  LoadCell *loadcell_ptr = loadcells[loadcell_num - 1];

  if (save_offset && save_scale) {
    save_offset_to_persistent_memory(loadcell_num);
    save_scale_coeff_to_persistent_memory(loadcell_num);
    Log.traceln(F("---------***---------"));
    Log.traceln(F("Offset and scale coefficient saved to persistent memory."));
    Log.trace(F("Offset: %f"), loadcell_ptr->get_offset());
    Log.trace(F("Scale coefficient: "), loadcell_ptr->get_scale());
  } else if (save_offset && !save_scale) {
    save_offset_to_persistent_memory(loadcell_num);
    Log.traceln(F("---------***---------"));
    Log.traceln(F("Offset saved to persistent memory."));
    Log.trace(F("Offset: %f"), loadcell_ptr->get_offset());
  } else if (!save_offset && save_scale) {
    save_scale_coeff_to_persistent_memory(loadcell_num);
    Log.traceln(F("---------***---------"));
    Log.traceln(F("Scale coefficient saved to persistent memory."));
    Log.trace(F("Scale coefficient: %f"), loadcell_ptr->get_scale());
  }
}

void LoadCellController::easy_start_with_questions(
  byte loadcell_num,
  byte dout,
  byte pd_sck,
  byte gain) {
  // not implemented
}

void LoadCellController::easy_handle_exceptions(
  byte loadcell_num,
  bool calibrate_offset,
  bool calibrate_scale,
  bool read_offset_persistent_memory,
  bool read_scale_persistent_memory,
  bool save_offset_persistent_memory,
  bool save_scale_persistent_memory,
  float tare_offset,
  float scale_coeff) {
  assert_valid_load_cell_num(loadcell_num);

  if (calibrate_offset && read_offset_persistent_memory) {
    Log.traceln(F("ERROR 2 easy_start(): cannot calibrate offset and read it from memory."));
    while (1)
      ;
  }
  if (calibrate_scale && read_scale_persistent_memory) {
    Log.traceln(F("ERROR 3 easy_start(): cannot calibrate scale and read it from memory."));
    while (1)
      ;
  }
  if (read_offset_persistent_memory && save_offset_persistent_memory) {
    Log.traceln(F("ERROR 4 easy_start(): cannot read scale from memory and save it to memory."));
    while (1)
      ;
  }
  if (read_scale_persistent_memory && save_scale_persistent_memory) {
    Log.traceln(F("ERROR 5 easy_start(): cannot calibrate scale and read it from memory."));
    while (1)
      ;
  }
  if (calibrate_offset && tare_offset) {
    Log.traceln(F("ERROR 6 easy_start(): cannot calibrate offset and specify a tare offset."));
    while (1)
      ;
  }
  if (calibrate_scale && scale_coeff) {
    Log.traceln(F("ERROR 7 easy_start(): cannot calibrate scale and specify a scale factor."));
    while (1)
      ;
  }
  if (read_offset_persistent_memory && tare_offset) {
    Log.traceln(F("ERROR 8 easy_start(): cannot read offset from memory and specify a tare offset."));
    while (1)
      ;
  }
  if (read_scale_persistent_memory && scale_coeff) {
    Log.traceln(F("ERROR 9 easy_start(): cannot read scale from memoryand specify a scale coeff."));
    while (1)
      ;
  }
}

#if defined(__AVR_ATmega328P__)
void LoadCellController::save_offset_to_persistent_memory(byte loadcell_num) {
  assert_valid_load_cell_num(loadcell_num);

  LoadCell *loadcell_ptr = loadcells[loadcell_num - 1];
  // since loadcell.get_offset() returns an int, it needs to be converted to long before calling EEPROM.put()
  long offset = loadcell_ptr->get_offset();
  EEPROM.put(get_offset_eeprom_adress(loadcell_num), offset);
}
#elif defined(ARDUINO_ARCH_ESP32)
void LoadCellController::save_offset_to_persistent_memory(byte loadcell_num) {
  assert_valid_load_cell_num(loadcell_num);

  if (!SPIFFS.begin()) {
    Log.traceln(F("SPIFFS Mount Failed"));
    return;
  }
  LoadCell *loadcell_ptr = loadcells[loadcell_num - 1];
  // since loadcell.get_offset() returns an int, it needs to be converted to long before saving to SPIFFS
  long offset = loadcell_ptr->get_offset();
  char buffer[15];
  // Convert offset (long) to char array before saving it
  dtostrf(offset, 6, 0, buffer);
  File file = SPIFFS.open(get_offset_file_name(loadcell_num).c_str(), FILE_WRITE);
  if (!file) {
    Log.traceln(F("failed to open file for writing"));
    return;
  }
  const char *buffer_ptr = buffer;
  if (file.print(buffer_ptr)) {
    Log.traceln(F("offset saved to memory"));
  } else {
    Log.traceln(F("failed to saved offset to memory"));
  }
  file.close();
}
#endif

#if defined(__AVR_ATmega328P__)
void LoadCellController::save_scale_coeff_to_persistent_memory(byte loadcell_num) {
  assert_valid_load_cell_num(loadcell_num);

  LoadCell *loadcell_ptr = loadcells[loadcell_num - 1];
  // since loadcell.get_offset() returns an float, it needs to be converted to double before calling EEPROM.put()
  double scale = loadcell_ptr->get_scale();

  EEPROM.put(get_scale_coeff_eeprom_adress(loadcell_num), scale);
}
#elif defined(ARDUINO_ARCH_ESP32)
void LoadCellController::save_scale_coeff_to_persistent_memory(byte loadcell_num) {
  assert_valid_load_cell_num(loadcell_num);

  if (!SPIFFS.begin()) {
    Log.traceln(F("SPIFFS Mount Failed"));
    return;
  }
  LoadCell *loadcell_ptr = loadcells[loadcell_num - 1];
  // since loadcell.get_offset() returns an float, it needs to be converted to double before calling EEPROM.put()
  double scale = loadcell_ptr->get_scale();

  char buffer[15];
  // Convert offset (long) to char array before saving it
  dtostrf(scale, 6, 2, buffer);

  File file = SPIFFS.open(get_scale_coeff_file_name(loadcell_num).c_str(), FILE_WRITE);
  if (!file) {
    Log.traceln(F("failed to open file for writing"));
    while (1)
      ;
  }
  const char *buffer_ptr = buffer;
  if (file.print(buffer_ptr)) {
    Log.traceln(F("file written"));
  } else {
    Log.traceln(F("failed to save scale coefficient to memory"));
  }
  file.close();
}
#endif

#if defined(__AVR_ATmega328P__)
long LoadCellController::read_offset_from_persistent_memory(byte loadcell_num) {
  assert_valid_load_cell_num(loadcell_num);

  long offset;
  EEPROM.get(get_offset_eeprom_adress(loadcell_num), offset);
  return offset;
}
#elif defined(ARDUINO_ARCH_ESP32)
long LoadCellController::read_offset_from_persistent_memory(byte loadcell_num) {
  assert_valid_load_cell_num(loadcell_num);

  if (!SPIFFS.begin()) {
    Log.traceln(F("SPIFFS Mount Failed"));
    while (1)
      ;
  }
  File file = SPIFFS.open(get_offset_file_name(loadcell_num).c_str());
  if (!file || file.isDirectory()) {
    Log.traceln(F("failed to read offset from memory"));
    while (1)
      ;
  }
  long offset;
  // Log.traceln("- read from file:");
  while (file.available()) {
    offset = file.readStringUntil('\n').toInt();
  }
  file.close();
  return offset;
}
#endif

#if defined(__AVR_ATmega328P__)
float LoadCellController::read_scale_coeff_from_persistent_memory(byte loadcell_num) {
  assert_valid_load_cell_num(loadcell_num);

  float scale;
  EEPROM.get(get_scale_coeff_eeprom_adress(loadcell_num), scale);
  return scale;
}
#elif defined(ARDUINO_ARCH_ESP32)
float LoadCellController::read_scale_coeff_from_persistent_memory(byte loadcell_num) {
  assert_valid_load_cell_num(loadcell_num);

  if (!SPIFFS.begin()) {
    Log.traceln(F("SPIFFS Mount Failed"));
    while (1)
      ;
  }

  File file = SPIFFS.open(get_scale_coeff_file_name(loadcell_num).c_str());
  if (!file || file.isDirectory()) {
    Log.traceln(F("failed to read scale coefficient from memory"));
    while (1)
      ;
  }
  float scale;
  // Log.traceln("- read from file:");
  while (file.available()) {
    scale = file.readStringUntil('\n').toFloat();
  }
  file.close();
  return scale;
}
#endif

void LoadCellController::calibrate_both_params(byte loadcell_num) {
  assert_valid_load_cell_num(loadcell_num);

  Log.traceln(F("***"));
  Log.trace(F("Start calibration of loadcell #%d :"), loadcell_num);
  calibrate_tare_offset(loadcell_num);
  delay(500);
  calibrate_scale_coeff(loadcell_num);
  delay(500);
}

void LoadCellController::calibrate_tare_offset(byte loadcell_num) {
  assert_valid_load_cell_num(loadcell_num);

  LoadCell *loadcell_ptr = loadcells[loadcell_num - 1];
  float tare_offset = determine_offset(loadcell_num);
  loadcell_ptr->set_offset(tare_offset);
}

void LoadCellController::calibrate_scale_coeff(byte loadcell_num) {
  assert_valid_load_cell_num(loadcell_num);

  LoadCell *loadcell_ptr = loadcells[loadcell_num - 1];
  float scale_coeff = determine_scale_coeff(loadcell_num);
  loadcell_ptr->set_scale(scale_coeff);
}

float LoadCellController::determine_offset(byte loadcell_num) {
  assert_valid_load_cell_num(loadcell_num);

  LoadCell *loadcell_ptr = loadcells[loadcell_num - 1];
  long tare_offset;

  Log.traceln(F("---------***---------"));
  Log.trace(F("Determination of the tare offset of loadcell #%d"), loadcell_num);
  Log.traceln(F("Remove any load applied to the loadcell."));
  Log.traceln(F("Send 't' from serial monitor to set the tare offset."));
  delay(3000);  // delay to allow stabilization of the output before tare
  bool _resume = false;
  while (_resume == false) {
    if (Serial.available() > 0) {
      char serial_reading = Serial.read();
      if (serial_reading == 't') {
        Log.traceln(F("Reading..."));
        tare_offset = loadcell_ptr->read_tare_average();
        Log.trace(F("Offset: %f "), tare_offset);
        _resume = true;
      }
    }
  }
  return tare_offset;
}

float LoadCellController::determine_scale_coeff(byte loadcell_num) {
  assert_valid_load_cell_num(loadcell_num);

  LoadCell *loadcell_ptr = loadcells[loadcell_num - 1];

  Log.traceln(F("---------***---------"));
  Log.trace(F("Determination of the scale coeff of loadcell #%d"), loadcell_num);
  Log.traceln(F("How many weights will be used to calibrate the loadcell ?"));
  int num_weights = 0;
  bool _resume = false;
  while (_resume == false) {
    if (Serial.available() > 0) {
      num_weights = Serial.parseInt();
      if (num_weights != 0) {
        Log.traceln(F("%d calibration weight(s) will be used to determine scale coeff."), num_weights);
        _resume = true;
      }
    }
  }
  float scale_coeff_sum = 0;
  for (int i = 1; i < (num_weights + 1); i++) {
    Log.trace(F("Place weight #%d n the loadcell."), i);
    Log.traceln(F("Then send its weight from serial monitor."));
    float known_mass = 0;
    _resume = false;
    while (_resume == false) {
      if (Serial.available() > 0) {
        known_mass = Serial.parseFloat();
        if (known_mass != 0) {
          Log.trace(F("Known mass is: %f"), known_mass);
          _resume = true;
        }
      }
    }
    delay(2000);  // delay before beginning readings for stabilization of the output
    // byte times = loadcell_ptr->get_scale_coeff_n_readings();
    Log.traceln(F("Reading..."));
    float known_output = loadcell_ptr->read_scale_coeff_average();
    float mass_scale_coeff = calculate_scale_coeff(loadcell_num, known_output, known_mass);
    Log.trace(F("The scale coefficient for this mass is %f"), mass_scale_coeff);
    scale_coeff_sum += mass_scale_coeff;
  }
  float scale_coeff = scale_coeff_sum / num_weights;
  Log.trace(F("Scale coefficient: %f"), scale_coeff);
  return scale_coeff;
}

float LoadCellController::calculate_scale_coeff(
  byte loadcell_num,
  float output,
  float mass) {
  assert_valid_load_cell_num(loadcell_num);

  LoadCell *loadcell_ptr = loadcells[loadcell_num - 1];
  return (output - loadcell_ptr->get_offset()) / mass;
}

int LoadCellController::get_offset_eeprom_adress(byte loadcell_num) {
  assert_valid_load_cell_num(loadcell_num);

  return 8 * (loadcell_num - 1);
}

int LoadCellController::get_scale_coeff_eeprom_adress(byte loadcell_num) {
  assert_valid_load_cell_num(loadcell_num);

  return 8 * (loadcell_num - 1) + 4;
}

String LoadCellController::get_offset_file_name(byte loadcell_num) {
  char fileName[30];
  snprintf(fileName, 30, "/offset%i.txt", loadcell_num);
  return String(fileName);
}

String LoadCellController::get_scale_coeff_file_name(byte loadcell_num) {
  char fileName[30];
  snprintf(fileName, 30, "/scale_coeff%i.txt", loadcell_num);
  return String(fileName);
}

long LoadCellController::get_offset(byte loadcell_num) {
  assert_valid_load_cell_num(loadcell_num);

  LoadCell *loadcell_ptr = loadcells[loadcell_num - 1];
  return loadcell_ptr->get_offset();
}

void LoadCellController::set_offset(byte loadcell_num, float offset) {
  assert_valid_load_cell_num(loadcell_num);

  LoadCell *loadcell_ptr = loadcells[loadcell_num - 1];
  loadcell_ptr->set_offset(offset);
}

float LoadCellController::get_scale(byte loadcell_num) {
  assert_valid_load_cell_num(loadcell_num);

  LoadCell *loadcell_ptr = loadcells[loadcell_num - 1];
  return loadcell_ptr->get_scale();
}

void LoadCellController::set_scale(byte loadcell_num, float scale) {
  assert_valid_load_cell_num(loadcell_num);

  LoadCell *loadcell_ptr = loadcells[loadcell_num - 1];
  loadcell_ptr->set_scale(scale);
}

void LoadCellController::set_tare_n_readings(byte loadcell_num, int n_readings) {
  assert_valid_load_cell_num(loadcell_num);

  LoadCell *loadcell_ptr = loadcells[loadcell_num - 1];
  loadcell_ptr->set_tare_n_readings(n_readings);
}

byte LoadCellController::get_tare_n_readings(byte loadcell_num) {
  assert_valid_load_cell_num(loadcell_num);

  LoadCell *loadcell_ptr = loadcells[loadcell_num - 1];
  return loadcell_ptr->get_tare_n_readings();
}

void LoadCellController::set_scale_coeff_n_readings(byte loadcell_num, int n_readings) {
  assert_valid_load_cell_num(loadcell_num);

  LoadCell *loadcell_ptr = loadcells[loadcell_num - 1];
  loadcell_ptr->set_scale_coeff_n_readings(n_readings);
}

byte LoadCellController::get_scale_coeff_n_readings(byte loadcell_num) {
  assert_valid_load_cell_num(loadcell_num);

  LoadCell *loadcell_ptr = loadcells[loadcell_num - 1];
  return loadcell_ptr->get_scale_coeff_n_readings();
}

void LoadCellController::set_weight_n_readings(byte loadcell_num, int n_readings) {
  assert_valid_load_cell_num(loadcell_num);

  LoadCell *loadcell_ptr = loadcells[loadcell_num - 1];
  loadcell_ptr->set_weight_n_readings(n_readings);
}

byte LoadCellController::get_weight_n_readings(byte loadcell_num) {
  assert_valid_load_cell_num(loadcell_num);

  LoadCell *loadcell_ptr = loadcells[loadcell_num - 1];
  return loadcell_ptr->get_weight_n_readings();
}

void LoadCellController::set_all_loadcells_tare_n_readings(int n_readings) {
  for (byte i = 1; i <= n_loadcell; i++) {
    set_tare_n_readings(i, n_readings);
  }
}

void LoadCellController::set_mouse_weight(float weight) {
  if (weight > 0) {
    mouse_weight = weight;
  }
}

float LoadCellController::get_mouse_weight() {
  return mouse_weight;
}

void LoadCellController::set_all_loadcells_scale_coeff_n_readings(int n_readings) {
  for (byte i = 1; i <= n_loadcell; i++) {
    set_scale_coeff_n_readings(i, n_readings);
  }
}

void LoadCellController::set_all_loadcells_weight_n_readings(int n_readings) {
  for (byte i = 1; i <= n_loadcell; i++) {
    set_weight_n_readings(i, n_readings);
  }
}

long LoadCellController::read_raw_average(byte loadcell_num) {
  assert_valid_load_cell_num(loadcell_num);

  LoadCell *loadcell_ptr = loadcells[loadcell_num - 1];

  return loadcell_ptr->read_raw_average();
}

long LoadCellController::read_tare_average(byte loadcell_num) {
  assert_valid_load_cell_num(loadcell_num);

  LoadCell *loadcell_ptr = loadcells[loadcell_num - 1];

  return loadcell_ptr->read_tare_average();
}

long LoadCellController::read_scale_coeff_average(byte loadcell_num) {
  assert_valid_load_cell_num(loadcell_num);

  LoadCell *loadcell_ptr = loadcells[loadcell_num - 1];

  return loadcell_ptr->read_scale_coeff_average();
}

double LoadCellController::get_raw_value(byte loadcell_num) {
  assert_valid_load_cell_num(loadcell_num);

  LoadCell *loadcell_ptr = loadcells[loadcell_num - 1];

  return loadcell_ptr->get_raw_value();
}

float LoadCellController::get_weight(byte loadcell_num) {
  assert_valid_load_cell_num(loadcell_num);

  LoadCell *loadcell_ptr = loadcells[loadcell_num - 1];

  return loadcell_ptr->get_weight();
}

float LoadCellController::get_weight_with_auto_recalibration(byte loadcell_num, float threshold) {
  assert_valid_load_cell_num(loadcell_num);

  LoadCell *loadcell_ptr = loadcells[loadcell_num - 1];

  while (!loadcell_ptr->is_ready())
    ;

  long reading;
  byte i = 0;
  long reading_sum = 0;
  bool tare = true;
  float weight;

  // average tare_n_readings for mesurements of new tare offset
  for (i; i < loadcell_ptr->get_tare_n_readings(); i++) {
    reading = loadcell_ptr->read();

    if (abs(mass_from_raw(loadcell_num, reading)) > (get_mouse_weight() * threshold)) {
      tare = false;
      break;
    }
    reading_sum += reading;
  }

  // if no mouse came on the scale, we set the new offset to the average value
  if (tare) {
    // Log.trace(F("*** TARE LoadCell #"));
    // Log.trace(loadcell_num);
    // Log.traceln(F(" ***"));
    loadcell_ptr->set_offset(reading_sum / loadcell_ptr->get_tare_n_readings());
    weight = mass_from_raw(loadcell_num, reading_sum / loadcell_ptr->get_tare_n_readings());
  }

  // if a mouse came, we perform a reading of its weight relative to the previous offset
  else {
    weight = loadcell_ptr->get_weight();
  }

  return weight;
}

float LoadCellController::mass_from_raw(byte loadcell_num, long raw) {
  LoadCell *loadcell_ptr = loadcells[loadcell_num - 1];

  return (raw - loadcell_ptr->get_offset()) / loadcell_ptr->get_scale();
}

void LoadCellController::tare(byte loadcell_num) {
  assert_valid_load_cell_num(loadcell_num);

  LoadCell *loadcell_ptr = loadcells[loadcell_num - 1];

  loadcell_ptr->tare();
}

void LoadCellController::begin(
  byte loadcell_num,
  byte dout,
  byte pd_sck,
  byte gain) {
  assert_valid_load_cell_num(loadcell_num);

  LoadCell *loadcell_ptr = loadcells[loadcell_num - 1];

  loadcell_ptr->begin(dout, pd_sck, gain);
}

bool LoadCellController::is_ready(byte loadcell_num) {
  assert_valid_load_cell_num(loadcell_num);

  LoadCell *loadcell_ptr = loadcells[loadcell_num - 1];

  return loadcell_ptr->is_ready();
}

void LoadCellController::wait_ready(
  byte loadcell_num,
  unsigned long delay_ms) {
  assert_valid_load_cell_num(loadcell_num);

  LoadCell *loadcell_ptr = loadcells[loadcell_num - 1];

  loadcell_ptr->wait_ready(delay_ms);
}

bool LoadCellController::wait_ready_retry(
  byte loadcell_num,
  int retries,
  unsigned long delay_ms) {
  assert_valid_load_cell_num(loadcell_num);

  LoadCell *loadcell_ptr = loadcells[loadcell_num - 1];

  return loadcell_ptr->wait_ready_retry(retries, delay_ms);
}

bool LoadCellController::wait_ready_timeout(
  byte loadcell_num,
  unsigned long timeout,
  unsigned long delay_ms) {

  assert_valid_load_cell_num(loadcell_num);

  LoadCell *loadcell_ptr = loadcells[loadcell_num - 1];

  return loadcell_ptr->wait_ready_timeout(timeout, delay_ms);
}

void LoadCellController::power_up(byte loadcell_num) {
  assert_valid_load_cell_num(loadcell_num);

  LoadCell *loadcell_ptr = loadcells[loadcell_num - 1];

  loadcell_ptr->power_up();
}

void LoadCellController::power_down(byte loadcell_num) {
  assert_valid_load_cell_num(loadcell_num);

  LoadCell *loadcell_ptr = loadcells[loadcell_num - 1];

  loadcell_ptr->power_down();
}

byte LoadCellController::number_of_loadcells() {
  return n_loadcell;
}

bool LoadCellController::is_loadcell_num_in_range(byte loadcell_num) {
  if (loadcell_num > 0 && loadcell_num <= number_of_loadcells()) {
    Log.errorln(F("%s: loadcell number %d is out of range"), __func__, loadcell_num);
    return false;
  }
  return true;
}

#if defined(__AVR_ATmega328P__)
void LoadCellController::clear_eeprom(int start, int end) {
  for (int i = start; i < end; i++) {
    EEPROM.write(i, 0);
  }
}
#endif
