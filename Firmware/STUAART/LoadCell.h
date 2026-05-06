/**
 * @mainpage LoadCell and LoadCellController libraries for Arduino
 *
 * Welcome to the documentation of LoadCell and LoadCellController libraries.
 * This documentation provides complete documentation of the libraries.
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
        * The HX711 can return 0xFFFFFF (raw == -1L after sign extension) when
        * the read sequence is disturbed: interrupt during a SCK pulse making
        * the chip enter power-down, or DOUT line sharing a pin with the flash
        * SPI bus (GPIO 6-11 on ESP32). This method calls read() and, if the
        * value matches that signature, retries up to @p max_retries times,
        * waiting for the chip to be ready between attempts. Returns the last
        * raw value, or -1L if all retries still produced -1L. Callers should
        * treat -1L as invalid.
        */
       long safe_read(byte max_retries = 3);


       /**
        * @brief Read the output of the LoadCell and average @ref weight_n_readings readings.
        *
        * This function does @ref weight_n_readings readings of the raw output of the LoadCell and 
        * calculates their average before returning the average raw output.
        * 
        * @return The raw averaged reading of the LoadCell.
        */
       long read_raw_average();


       /**
        * @brief Read the output of the LoadCell and average @ref tare_n_readings readings.
        *
        * This function does @ref tare_n_readings readings of the raw output of the LoadCell and 
        * calculates their average before returning the average raw output. It is useful inside calibration scripts.
        * 
        * @return The raw averaged reading of the LoadCell for the tare offset caibration.
        */
       long read_tare_average();


       /**
        * @brief Read the output of the LoadCell and average @ref scale_coeff_n_readings readings.
        *
        * This function does @ref scale_coeff_n_readings readings of the raw output of the LoadCell and 
        * calculates their average before returning the average raw output. It is useful inside calibration scripts.
        * 
        * @return The raw averaged reading of the LoadCell for the scale coefficient calibration.
        */
       long read_scale_coeff_average();


       /**
        * @brief Read the raw output of the LoadCell and substracts the offset.
        *
        * This function reads the average of readings of the LoadCell raw output with 
        * @ref read_raw_average() then substracts the offset accessed with @ref get_offset().
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
        * for this member variable -> @ref tare_n_readings ∈ [1, 255].
        * 
        * Anything below 1 will be set to 1 and anything above 255 will be set to 255 to be able to store in a byte.
        * 
        * @param tare_n_readings The number of readings averaged for the determination of the tare offset.
        */
       void set_tare_n_readings(int tare_n_readings);


       /**
        * @brief Get the number of readings averaged for the determination of the tare offset.
        *
        * This function returns the member variable @ref tare_n_readings.
        * 
        * @return The number of readgings averaged for the determination of the tare offset.
        */
       int get_tare_n_readings();


       /**
        * @brief Set the number of readings averaged for the determination of the scale coefficient.
        *
        * This function sets the member variable scale_coeff_n_readings. It also limits the range of value that is possible
        * for this member variable -> @ref scale_coeff_n_readings ∈ [1, 255].
        * 
        * Anything below 1 will be set to 1 and anything above 255 will be set to 255 to be able to store in a byte.
        * 
        * @param scale_coeff_n_readings The number of readings averaged for the determination of the tare offset.
        */
       void set_scale_coeff_n_readings(int scale_coeff_n_readings);


       /**
        * @brief Get the number of readings averaged for the determination of the scale coefficient.
        *
        * This function returns the member variable @ref scale_coeff_n_readings.
        * 
        * @return The number of readgings averaged for the determination of the tare offset.
        */
       int get_scale_coeff_n_readings();


       /**
        * @brief Set the number of readings averaged for a weight reading.
        *
        * This function sets the member variable weight_n_readings. It also limits the range of value that is possible
        * for this member variable -> @ref weight_n_readings ∈ [1, 255].
        * 
        * Anything below 1 will be set to 1 and anything above 255 will be set to 255 to be able to store in a byte.
        * 
        * @param weight_n_readings The number of readings averaged for the determination of the tare offset.
        */
       void set_weight_n_readings(int weight_n_readings);


       /**
        * @brief Get the number of readings averaged for a weight reading.
        *
        * This function returns the member variable @ref scale_coeff_n_readings.
        * 
        * @return The number of readgings averaged for the determination of the tare offset.
        */
       int get_weight_n_readings();
};
#endif