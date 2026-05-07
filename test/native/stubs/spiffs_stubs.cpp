// Stub implementations for the four SPIFFS-/EEPROM-dependent methods of
// LoadCellController. The production .cpp wraps them in
// `#if defined(ARDUINO_ARCH_ESP32) ... #elif defined(__AVR_ATmega328P__)`,
// so on the host neither is defined, the methods have no implementation,
// and any caller (e.g. `tare_all_loadcells` calling
// `save_offset_to_persistent_memory`) breaks the link.
//
// These stubs let the tests link cleanly even when the production .cpp
// calls these methods transitively. Tests deliberately do NOT exercise
// the persistence paths : that is left for AUnit on a real Firebeetle.
#include "LoadCellController.h"

void  LoadCellController::save_offset_to_persistent_memory(byte)             {}
void  LoadCellController::save_scale_coeff_to_persistent_memory(byte)        {}
long  LoadCellController::read_offset_from_persistent_memory(byte)           { return 0L; }
float LoadCellController::read_scale_coeff_from_persistent_memory(byte)      { return 1.0f; }
