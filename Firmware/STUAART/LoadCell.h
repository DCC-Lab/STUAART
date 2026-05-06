/**
 * @mainpage LoadCell and LoadCellController libraries for STUAART
 *
 * @section overview Overview
 *
 * Two custom Arduino classes for the STUAART automated mouse weighing
 * system :
 *
 * - @ref LoadCell extends `bogde/HX711` with configurable averaging
 *   counts for the three usage contexts (weight reading, tare
 *   calibration, scale-coefficient calibration) and with a defensive
 *   `safe_read()` that filters out three known HX711 corruption
 *   signatures (`0xFFFFFF`, `0x800000`, `0x7FFFFF`).
 * - @ref LoadCellController manages up to 10 LoadCell instances per
 *   cage, persists calibration to SPIFFS (ESP32) or EEPROM (AVR), and
 *   provides ready-to-use start-up routines.
 *
 * Both classes are compiled directly with the sketch (next to the
 * `.ino`), so cloning the repo and opening `Firmware/STUAART/STUAART.ino`
 * is enough to build the firmware.
 *
 * @section minimal Minimal usage
 *
 * @code
 * #include "LoadCell.h"
 * #include "LoadCellController.h"
 *
 * LoadCell loadcell;
 * LoadCellController controller;
 *
 * void setup() {
 *   Serial.begin(115200);
 *   controller.add_loadcell(loadcell);
 *   controller.easy_start_with_params(
 *       1,     // loadcell number
 *       27,    // DOUT  (avoid GPIO 6-11 on ESP32 : flash bus)
 *       17,    // SCK
 *       true,  // calibrate offset
 *       true,  // calibrate scale
 *       false, // read offset from memory
 *       false, // read scale from memory
 *       true,  // save offset to memory
 *       true,  // save scale to memory
 *       0,     // manual tare offset
 *       0,     // manual scale coeff
 *       128    // gain
 *   );
 * }
 *
 * void loop() {
 *   controller.wait_ready_timeout(1, 1000);
 *   Serial.println(controller.get_weight(1));
 * }
 * @endcode
 *
 * @section corruption HX711 corruption handling
 *
 * The HX711 24-bit ADC can return three values that are physically
 * impossible during normal operation of a strain-gauge load cell :
 *
 * - `-1L` (`0xFFFFFF`) : DOUT was held HIGH during the read,
 *   typically because an interrupt stretched a SCK pulse beyond 60 us
 *   and the chip entered power-down, OR because the DOUT pin shares
 *   a pad with the ESP32 internal flash SPI bus (GPIO 6 to 11).
 * - `-8388608L` (`0x800000`) : 24-bit negative saturation, observed
 *   when the boot tare hits a fully corrupted read on a flash-pin DOUT.
 * - `+8388607L` (`0x7FFFFF`) : 24-bit positive saturation, mirror image.
 *
 * @ref LoadCell::safe_read retries up to three times when any of these
 * appears, and the three averaging methods exclude such samples from
 * the mean rather than averaging garbage in. Callers should treat a
 * returned `-1L` as an invalid reading (returned only if every retry
 * was still corrupt).
 *
 * For the GPIO 9 case, the software workaround is partial : intermediate
 * bit-patterns from the flash bus can still corrupt occasional reads
 * without matching one of the three signatures. The proper fix is a
 * hardware strap that moves the DOUT off the flash pin.
 *
 * @section references References
 *
 * - bogde/HX711 : https://github.com/bogde/HX711
 * - STUAART repo : https://github.com/DCC-Lab/STUAART
 *
 * @author Nathan Bérubé, Valérie Pineau Noël, Daniel C. Côté
 */

/**
 * @file LoadCell.h
 *
 * @class LoadCell
 * @brief  This library extends the functionality of the  HX711 to make it compatible with the LoadCellController library.
 *
 * This Arduino library allows to specify the number of readings averaged 
 * for the three possible situations: 
 *      - Weight reading
 *      - Output reading for offset calibration
 *      - Output reading for scale coefficient calibration
 * 
 * The encapsulation of these parameters requires the rewriting of a few member functions
 * of the HX711 library. They do the same thing but, with the encapsulation of the three paramters
 * listed above, they don't require any arguments.
 * 
 * Most importantly, the encapsulation of these parameters is useful for the LoadCellController library,
 * which will control many LoadCells.
 * 
 * 
 * HX711 library: https://github.com/bogde/HX711
 * 
 * LoadCellController library: https://github.com/DCC-Lab/IntelligentCage/tree/master/Loadcell/Arduino%20libraries/LoadCellControllerlibrary
 *
 * @author Nathan Bérubé
 * @date August 14, 2023
 * @version 1.0.0
 */

#ifndef LoadCell_h
#define LoadCell_h
#include <Arduino.h>
#include "HX711.h"
class LoadCell : public HX711 {

protected:
       /**
        * @var byte tare_n_readings
        * @brief Number of readings averaged to determine the tare offset.
        */
       byte tare_n_readings = 50;


       /**
        * @var scale_coeff_n_readings
        * @brief Number of readings averaged to determine the scale coefficient.
       */
       byte scale_coeff_n_readings = 50;


       /**
        * @var byte weight_n_readings
        * @brief Number of readings averaged for a weight reading.
        */
       byte weight_n_readings = 5;
public:
       /**
        * @brief Construct a LoadCell object.
        */
       LoadCell();


       /**
        * @brief Read the HX711 with corruption detection and retry.
        *
        * Rejects three known corruption signatures and retries up to
        * @p max_retries times: 0xFFFFFF (-1, DOUT held HIGH by interrupt or
        * flash bus contention on GPIO 6-11), 0x800000 (-8388608, negative
        * saturation), and 0x7FFFFF (+8388607, positive saturation). None of
        * these can occur during normal operation of a mouse-scale load cell.
        * Returns the last raw value; callers should treat -1L as invalid
        * (returned only if every retry was still corrupt).
        */
       long safe_read(byte max_retries = 3);


       /**
        * @brief Read the output of the LoadCell and average `weight_n_readings` readings.
        *
        * This function does `weight_n_readings` readings of the raw output of the LoadCell and 
        * calculates their average before returning the average raw output.
        * 
        * @return The raw averaged reading of the LoadCell.
        */
       long read_raw_average();


       /**
        * @brief Read the output of the LoadCell and average `tare_n_readings` readings.
        *
        * This function does `tare_n_readings` readings of the raw output of the LoadCell and 
        * calculates their average before returning the average raw output. It is useful inside calibration scripts.
        * 
        * @return The raw averaged reading of the LoadCell for the tare offset caibration.
        */
       long read_tare_average();


       /**
        * @brief Read the output of the LoadCell and average `scale_coeff_n_readings` readings.
        *
        * This function does `scale_coeff_n_readings` readings of the raw output of the LoadCell and 
        * calculates their average before returning the average raw output. It is useful inside calibration scripts.
        * 
        * @return The raw averaged reading of the LoadCell for the scale coefficient calibration.
        */
       long read_scale_coeff_average();


       /**
        * @brief Read the raw output of the LoadCell and substracts the offset.
        *
        * This function reads the average of readings of the LoadCell raw output with 
        * @ref read_raw_average() then substracts the offset accessed with `HX711::get_offset()`.
        * 
        * @return The raw averaged reading of the LoadCell difference with the offset.
        */
       double get_raw_value();


       /**
        * @brief Read the weight of the object currently on the LoadCell.
        *
        * This function reads the average of readings of the LoadCell raw output with 
        * @ref read_raw_average() before converting this average of raw output to a mass value 
        * using the calibration function -> output = scale_coeff * mass + offset.
        * 
        * @return The averaged mass of the object on the LoadCell.
        */
       float get_weight();


       /**
        * @brief Read the raw output of the LoadCell and set this value to the offset
        *
        * This function does tare_n_reading readings to get the average for the offset. 
        * It then sets this value to the member varibale OFFSET that is private. 
        * 
        */
       void tare();


       /**
        * @brief Set the number of readings averaged for the determination of the tare offset.
        *
        * This function sets the member variable tare_n_readings. It also limits the range of value that is possible
        * for this member variable -> `tare_n_readings` ∈ [1, 255].
        * 
        * Anything below 1 will be set to 1 and anything above 255 will be set to 255 to be able to store in a byte.
        * 
        * @param tare_n_readings The number of readings averaged for the determination of the tare offset.
        */
       void set_tare_n_readings(int tare_n_readings);


       /**
        * @brief Get the number of readings averaged for the determination of the tare offset.
        *
        * This function returns the member variable `tare_n_readings`.
        * 
        * @return The number of readgings averaged for the determination of the tare offset.
        */
       int get_tare_n_readings();


       /**
        * @brief Set the number of readings averaged for the determination of the scale coefficient.
        *
        * This function sets the member variable scale_coeff_n_readings. It also limits the range of value that is possible
        * for this member variable -> `scale_coeff_n_readings` ∈ [1, 255].
        * 
        * Anything below 1 will be set to 1 and anything above 255 will be set to 255 to be able to store in a byte.
        * 
        * @param scale_coeff_n_readings The number of readings averaged for the determination of the tare offset.
        */
       void set_scale_coeff_n_readings(int scale_coeff_n_readings);


       /**
        * @brief Get the number of readings averaged for the determination of the scale coefficient.
        *
        * This function returns the member variable `scale_coeff_n_readings`.
        * 
        * @return The number of readgings averaged for the determination of the tare offset.
        */
       int get_scale_coeff_n_readings();


       /**
        * @brief Set the number of readings averaged for a weight reading.
        *
        * This function sets the member variable weight_n_readings. It also limits the range of value that is possible
        * for this member variable -> `weight_n_readings` ∈ [1, 255].
        * 
        * Anything below 1 will be set to 1 and anything above 255 will be set to 255 to be able to store in a byte.
        * 
        * @param weight_n_readings The number of readings averaged for the determination of the tare offset.
        */
       void set_weight_n_readings(int weight_n_readings);


       /**
        * @brief Get the number of readings averaged for a weight reading.
        *
        * This function returns the member variable `scale_coeff_n_readings`.
        * 
        * @return The number of readgings averaged for the determination of the tare offset.
        */
       int get_weight_n_readings();
};
#endif