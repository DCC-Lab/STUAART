/**
 * @file LoadCellController.h
 *
 * @class LoadCellController
 * @brief  This library allows to control and manage many load cells with a LoadCellController
 *
 * The LoadCellController library offers many features:
 *
 * - Calibrate load cells, both parameters (offset and scale coefficient)
 *
 *      - Member functions encapsulate the scripts needed for the calibration
 *      for both parameters. The interaction with the user is done inside the
 *      member functions.
 *
 * - Save the calibration parameters to EEPROM (tested on Arduino Uno August 2023)
 *              
 *      - The calibration parameters can be saved on the EEPROM after calibration.
 *      The EEPROM is useful when it comes to saving because the saved values don't
 *      vanish when the power supply of the Arduino is cut. The saved parameters can
 *      be reused at another moment.
 *
 * - Read the calibration parameters from EEPROM (tested on Arduino Uno August 2023)
 *
 *      - The calibration parameters can also be read from EEPROM after being saved.
 *
 * - "Easy" start-up function that will handle everything related to the calibration and manage
 *        the calibration parameters.
 *
 *      - The LoadCellController class offers ready-to-use "easy" functions that simplify the
 *      start-up of a load cell. Many scenarios are possible for the start-up of a load cell when
 *      it comes to calibration and the management of the calibration parameters. 
 *
 *      - A simple function @ref easy_start_with_params() takes in arguments many parameters to
 *      choose the appropriate option. Only a few parameters are needed.
 *              
 *      - This is useful for those who don't want to create their own sketch.
 *
 *      - All the member functions that begin with "easy" are for easy start-up and don't implement any other 
 *      functionalities than the other member functions. They only offer a "all-in-one" option for those
 *      who don't want to code.
 *
 * - The LoadCellController class allows to access the load cells through the controller.
 *
 *      The load cells are added with the member function @ref add_loadcell(). After that, all load cells are under
 *      the control of the LoadCellController and the member functions of the LoadCell class are accesed through
 *      the controller.
 *              
 *      This access to the LoadCells through the LoadCellController requires to specify to LoadCellController
 *      a parameter corresponding to the number identifying the LoadCell concerned (1, 2, ...). Every member
 *      functions that have as input the number of a LoadCell (n_loadcell) will verify if the LoadCell number
 *      is in a coherent range according to the number of LoadCells added to the controller according to the
 *      member variable @ref n_loadcell. If the value is out of the range, the code will be suspended with a
 *      endless while() loop and display on the serial monitor an error message specifying where the problem
 *      occured (in which function). This small if bloc is placed at the beginning
 *      @code
 *      if (is_loadcell_num_in_range(loadcell_num) == false) {
        Serial.println();
        Serial.println();
        Serial.println();
        Serial.print(F("ERROR 1 name_of_the_function(): loadcell number "));
        Serial.print(loadcell_num);
        Serial.println(F(" is out of range."));
        while(1);
        }
 *      @endcode
 *
 * HX711 library: https://github.com/bogde/HX711
 * 
 * LoadCell library: https://github.com/DCC-Lab/IntelligentCage/tree/master/Loadcell/Arduino%20libraries/LoadCellLibrary
 * @author Nathan Bérubé
 * @date August 14, 2023
 * @version 1.0.0
 */

#ifndef LoadCellController_h
#define LoadCellController_h
#include <Arduino.h>
#include "HX711.h"
#include "LoadCell.h"

class LoadCellController {
protected:
        /**
        * @var Loadcell* loadcells
        * @brief Array containing the pointer of the LoadCell controlled by the LoadCellController.
        * 
        * The only moment this variable is modified is  when a LoadCell is added with the
        * @ref add_loadcell() member function. It goes up by one every time @ref add_loadcell()
        * is called.
        */
        LoadCell* loadcells[10];


        /**
        * @var int n_loadcell
        * @brief Member variable used to keep track of the number of LoadCells added.
        * 
        * The only moment this variable is modified is  when a LoadCell is added with the
        * @ref add_loadcell() member function. It goes up by one every time @ref add_loadcell()
        * is called.
        */
        int n_loadcell = 0;


        /**
        * @brief Easy function managing the calibration of a LoadCell.
        *
        * This function is managing the possibilities that come with the calibration of 
        * the tare offset and the scale coefficient. It is meant to be used inside the member
        * function @ref easy_start_with_params(). 
        * 
        * The calibration process of both parameters (offset and scale coefficient) requires a computer
        * to display information on the serial monitor and also to send value through it for the calibration.
        * 
        * @param loadcell_num Number of the LoadCell.
        * @param cal_tare Boolean telling if the offset should be calibrated.
        * @param save_scale Boolean telling if the scale coefficient should be calibrated.
        */
        void easy_calibration_with_params(
                                        byte loadcell_num,
                                        bool cal_tare,
                                        bool cal_scale
                                        );


        /**
        * @brief Easy function managing the saving of calibration parameters to EEPROM.
        *
        * This function is managing the possibilities that come with the saving of the tare offset 
        * and the scale coefficient of a LoadCell. It is meant to be used inside the member function
        * @ref easy_start_with_params().
        * 
        * @param loadcell_num Number of the LoadCell.
        * @param save_offset Boolean telling if the offset should be saved to EEPROM.
        * @param save_scale Boolean telling if the scale coefficient should be saved to EEPROM.
        */
        void easy_save_to_eeprom_with_params(
                                byte loadcell_num,
                                bool save_offset,
                                bool save_scale
                                );


        /**
        * @brief Easy function managing the reading of calibration from EEPROM.
        *
        * This function is managing the possibilities that come with the reading from EEPROM of the tare offset 
        * and the scale coefficient of a LoadCell. It is meant to be used inside the member function
        * @ref easy_start_with_params().
        * 
        * @param loadcell_num Number of the LoadCell.
        * @param read_offset_eeprom Boolean telling if the offset should be read from EEPROM.
        * @param read_scale_eeprom Boolean telling if the scale coefficient should be read from EEPROM.
        */
        void easy_read_from_eeprom_with_params(
                                        byte loadcell_num,
                                        bool read_offset_eeprom,
                                        bool read_scale_eeprom
                                        );


        /**
        * @brief Easy function for start with questions through the serial monitor.
        *
        * This function is managing the possibilities that come with the start-up of a LoadCell with questions
        * that are asked through the serial monitor of the Arduino.
        * 
        * @todo This could be done in the future to simplify the start-up of a LoadCell especially for non-programmers.
        * 
        * @param loadcell_num Number of the LoadCell.
        * @param dout Pin connected to the DOUT output of the HX711.
        * @param pd_sck Pin connected to the SCK output of the HX711.
        * @param gain Gain of the HX711. Default is 128
        * @details The @p gain argument can take the following values: 128, 64 and 32. For a gain of 128 and 64,
        * channel A of the HX711 should be used. For a gain of 32, channel B should be used.
        */
        void easy_start_with_questions(
                                byte loadcell_num,
                                byte dout,
                                byte pd_sck,
                                byte gain=128
                                );


        /**
        * @brief Easy function used to handle possible conflicts in @ref easy_start_with_params().
        *
        * This function manages the possible conflicts that can happen between the parameters 
        * passed to the @ref easy_start_with_params() member functions. Since the user is specifying 
        * the starting parameters, it is probable that some are not possible simultaneously. This member
        * function verifies all possible conflicts. If one is detetced, the execution will be stopped with
        * infinite while() loop, since it is not possible to do raise exceptions on Arduino (as I know).
        * It is meant to be used inside the member function @ref easy_start_with_params().
        * 
        * @param loadcell_num Number of the LoadCell.
        * @param calibrate_offset Boolean telling if the offset should be calibrated. Default is false.
        * @param calibrate_scale Boolean telling if the scale coefficient should be calibrated. Default is false.
        * @param read_offset_eeprom Boolean telling if the offset should be read from EEPROM. Default is false.
        * @param read_scale_eeprom Boolean telling if the scale coefficient should be read from EEPROM. Default is false.
        * @param save_offset_eeprom Boolean telling if the offset should be saved to EEPROM. Default is false.
        * @param save_scale_eeprom Boolean telling if the scale coefficient should be saved to EEPROM. Default is false.
        * @param tare_offset Value of the tare offset. Default is 0.
        * @details The @p tare_offset default is 0 and is considered as the absence of a value. If no value wants to be 
        * specified, 0 should be given to the member function.
        * @param scale_coeff Value of the scale coefficient. Default is 0.
        * @details The @p scale_coeff default is 0 and is considered as the absence of a value. If no value wants to be 
        * specified, 0 should be given to the member function.
        */
        void easy_handle_exceptions(
                                byte loadcell_num,
                                bool calibrate_offset=false,
                                bool calibrate_scale=false,
                                bool read_offset_eeprom=false,
                                bool read_scale_eeprom=false,
                                bool save_offset_eeprom=false,
                                bool save_scale_eeprom=false,
                                float tare_offset=0,
                                float scale_coeff=0
                                );

public: 
        /**
        * @brief Construct a LoadCellController object.
        */
        LoadCellController();
        
        /**
        * @brief Add a new LoadCell to the LoadCellController.
        *
        * This function adds a new LoadCell to the controller. It will add the pointer of the LoadCell
        * object to the next index in the @ref loadcells array and increase the value @ref n_loadcell by 1
        * to keep track of the number of LoadCell.
        * 
        * The first added LoadCell will be load cell 1, the second one will be load cell 2 and so on.
        *
        * 
        * @param loadcell LoadCell object added to the LoadCellController.
        */
        void add_loadcell(LoadCell &loadcell);


        /**
        * @brief Easy function managing the start-up of a LoadCell with parameters as input.
        *
        * This function, with only a few parameters as input, controls everything related to the start-up of a LoadCell.
        * The calibration of the offset and the scale coefficient and theire saving/reading to/from the EEPROM.
        * All possible conflicts between parameters are handle by the member function @ref easy_handle_exceptions().
        * 
        * This member function was created to simplify the start-up of a LoadCell, especially for non-programmers. No additonal
        * functionnalities that are not accessible from the other member functions are implemented(not labeled easy_...).
        * 
        * All the following "easy" member functions are used inside @ref easy_start_with_params() to dispatch
        * to handling of all start-up scenarios:
        *       - @ref easy_calibration_with_params()
        *       - @ref easy_save_to_eeprom_with_params()
        *       - @ref easy_read_from_eeprom_with_params()
        *       - @ref easy_handle_exceptions()
        *                               
        * 
        * @param loadcell_num Number of the LoadCell.
        * @param dout Digital pin (or analog) connected to the DOUT output pin of the HX711.
        * @param pd_sck Digital pin (or analog) connected to the SCK output of the HX711.
        * @param calibrate_offset Boolean telling if the offset should be calibrated. Default is false.
        * @param calibrate_scale Boolean telling if the scale coefficient should be calibrated. Default is false.
        * @param read_offset_eeprom Boolean telling if the offset should be read from EEPROM. Default is false.
        * @param read_scale_eeprom Boolean telling if the scale coefficient should be read from EEPROM. Default is false.
        * @param save_offset_eeprom Boolean telling if the offset should be saved to EEPROM. Default is false.
        * @param save_scale_eeprom Boolean telling if the scale coefficient should be saved to EEPROM. Default is false.
        * @param tare_offset Value of the tare offset. Default is 0.
        * @param scale_coeff Value of the scale coefficient. Default is 0.
        * @param gain Gain of the HX711. Default is 128.
        * 
        * @details The tare_offset default is 0 and is considered as the absence of a value. If no value wants to be 
        * specified, 0 should be given to the member function.
        * @details The scale_coeff default is 0 and is considered as the absence of a value. If no value wants to be 
        * specified, 0 should be given to the member function.
        */
        void easy_start_with_params(
                                byte loadcell_num,
                                byte dout,
                                byte pd_sck,
                                bool calibrate_offset=false,
                                bool calibrate_scale=false,
                                bool read_offset_eeprom=false,
                                bool read_scale_eeprom=false,
                                bool save_offset_eeprom=false,
                                bool save_scale_eeprom=false,
                                float tare_offset=0,
                                float scale_coeff=0,
                                byte gain=128
                                );

        /**
        * @brief Save the offset of a given LoadCell to EEPROM.
        *
        * This function saves the offset member variable of a LoadCell, which was added to
        * the controller with the member function @ref add_loadcell(). The EEPROM adress is 
        * obtained with the member function @ref get_offset_adress(). The process of assigning
        * EEPROM adresses to LoadCell is completely hidden from the user to avoid problems.
        * 
        * @param loadcell_num Number of the LoadCell.
        */
        void save_offset_eeprom(byte loadcell_num);

        /**
        * @brief Save the scale coefficient of a given LoadCell to EEPROM.
        *
        * This function saves the scale coefficient member variable of a LoadCell, which was added to
        * the controller with the member function @ref add_loadcell(). The EEPROM adress is 
        * obtained with the member function @ref get_scale_coeff_adress(). The process of assigning
        * EEPROM adresses to LoadCell is completely hidden from the user to avoid problems.
        * 
        * @param loadcell_num Number of the LoadCell.
        */
        void save_scale_coeff_eeprom(byte loadcell_num);

        /**
        * @brief Save the offset of a given LoadCell to EEPROM.
        *
        * This function reads the offset of a LoadCell from EEPROM, which was added to
        * the controller with the member function @ref add_loadcell().
        * 
        * The EEPROM adress is obtained with the member function @ref get_offset_adress().
        * The process of assigning EEPROM adresses to LoadCell is completely hidden from 
        * the user to avoid problems.
        * 
        * @param loadcell_num Number of the LoadCell.
        * @return The offset of the given LoadCell obtained from EEPROM.
        */
        long read_offset_from_eeprom(byte loadcell_num);

        /**
        * @brief Save the scale coefficient of a given LoadCell to EEPROM.
        *
        * This function reads the scale coefficient of a LoadCell from EEPROM, which was added to
        * the controller with the member function @ref add_loadcell().
        * 
        * The EEPROM adress is obtained with the member function @ref get_scale_coeff_adress().
        * The process of assigning EEPROM adresses to LoadCell is completely hidden from 
        * the user to avoid problems.
        * 
        * @param loadcell_num Number of the LoadCell.
        * @return The scale coefficient of the given LoadCell obtained from EEPROM.
        */
        float read_scale_coeff_from_eeprom(byte loadcell_num);

        /**
        * @brief Proceed to the calibration of both parameters and set them for a LoadCell.
        *
        * This function begins the calibration of both offset and scale coefficient by calling
        * the member functions @ref calibrate_offset() and @ref calibrate_scale_coeff() that interact
        * with the user to determine and set both calibration parameters.
        * 
        * @param loadcell_num Number of the LoadCell.
        */
        void calibrate_both_params(byte loadcell_num);

        /**
        * @brief Proceed to the calibration of the offset and set it for a LoadCell.
        *
        * This function use the member function @ref determine_offset() to get the offset from
        * the calibration done by the user. This member function then sets this offset value to
        * the member variable of the LoadCell.
        * 
        * @param loadcell_num Number of the LoadCell.
        */
        void calibrate_tare_offset(byte loadcell_num);

        /**
        * @brief Proceed to the calibration of the scale coefficient and set it for a LoadCell.
        *
        * This function use the member function @ref determine_scale_coeff() to get the scale coefficient from
        * the calibration done by the user. This member function then sets this scale coefficient value to
        * the member variable of the LoadCell.
        * 
        * @param loadcell_num Number of the LoadCell.
        */
        void calibrate_scale_coeff(byte loadcell_num);

        /**
        * @brief Proceed to the calibration of the offset and return the offset value.
        *
        * This function interacts with the user through the serial
        * monitor to get an offset value for a given LoadCell.
        * 
        * This member function asks to the user to remove any object from the load cell and send
        * "t" with the serial monitor when it is done. After that, a output measurement is done
        * with @ref read_tare_average() to get a raw output value. This value is returned.
        * 
        * @param loadcell_num Number of the LoadCell.
        * @return The offset value.
        */
        float determine_offset(byte loadcell_num);

        /**
        * @brief Proceed to the calibration of the scale coefficient and return the scale coefficient value.
        *
        * This function interacts with the user through the serial
        * monitor to get a scale coefficient value for a given LoadCell.
        * 
        * This member function asks the user to specify the number of reference weights that will
        * be used to calibrate the load cell.
        * 
        * After that, the user is asked to put the first
        * reference weight on the loadcell and send the weight value through the serial monitor.
        * A weight measurement is done using the member function @ref read_scale_coeff_average().
        * A couple for our calibration linear function -> output = scale_coeff * mass + offset
        * is obtained (known mass, measured output).
        * The scale coefficient can now be calculated.
        * 
        * The process described above can be repeated for each reference weight to get a scale
        * coefficient value.
        * 
        * The average of all scale coefficients is taken to get the finale value returned by the function.
        * 
        * @note With this simple method, the scale coefficient depends of the offset. Finding both calibration
        * parameters (offset and scale coefficient) at the same time with a curve fit algorithm could be more effective.
        * 
        * @param loadcell_num Number of the LoadCell.
        * @return The scale coefficient value.
        */
        float determine_scale_coeff(byte loadcell_num);


        float calculate_scale_coeff(
                                byte loadcell_num,
                                float output,
                                float mass
                                );


        /**
        * @brief Get the EEPROM address for the offset of a LoadCell.
        *
        * This function returns the EEPROM address for the offset value
        * for a given LoadCell. The EEPROM addresses are determined based on
        * the loadcell number.
        *
        * @param loadcell_num Number of the LoadCell.
        * @return EEPROM address for the offset value.
        *
        * @note The EEPROM addresses are spaced along the EEPROM to prevent overlap
 *       between neighboring values.
        */
        int get_offset_adress(byte loadcell_num);


        /**
        * @brief Get the EEPROM address for the scale coefficient of a LoadCell.
        *
        * This function returns the EEPROM address for the scale coefficient value
        * for a given LoadCell. The EEPROM addresses are determined based on
        * the loadcell number.
         *    
         * @param loadcell_num Number of the LoadCell.
        * @return EEPROM address for the scale coefficient.
        *
        * @note The EEPROM addresses are spaced along the EEPROM to prevent overlap
        * between neighboring values.
        */
        int get_scale_coeff_adress(byte loadcell_num); 


        /**
        * @defgroup LoadCell LoadCell functions for LoadCellController
        * @brief Functions that are the member functions of the LoadCell class for the LoadCellController
        * class. They are duplicated in the LoadCellController class to access the @ref loadcells through the
        * LoadCellController instance.
        * @note LoadCell class member functions can also be accesed through the LoadCell instance.
        * The two possibilities are available.
        * @{
        */

        /**
        * @brief Get the offset value for a given LoadCell.
        *
        * This function gets the offset member variable for a given LoadCell
        * through the controller.
        * 
        * @param loadcell_num Number of the LoadCell.
        * @return Offset value.
        */
        float get_offset(byte loadcell_num);


        /**
        * @brief Set the offset value for a given LoadCell.
        *
        * This function sets the offset member variable for a given LoadCell
        * through the controller.
        * 
        * @param loadcell_num Number of the LoadCell.
        * @param offset Offset value.
        */
        void set_offset(byte loadcell_num, float offset); 


        /**
        * @brief Get the scale coefficient value for a given LoadCell.
        *
        * This function gets the scale coefficient member variable for a given LoadCell
        * through the controller.
        * 
        * @param loadcell_num Number of the LoadCell.
        * @return Scale coefficient value.
        */
        float get_scale(byte loadcell_num);


        /**
        * @brief Set the scale coefficient value for a given LoadCell.
        *
        * This function sets the scale coefficient member variable for a given LoadCell
        * through the controller.
        * 
        * @param loadcell_num Number of the LoadCell.
        * @param scale Scale coefficient value.
        */
        void set_scale(byte loadcell_num, float scale); 


        /**
        * @brief Set the number of readings averaged for calibration of offset for a given LoadCell.
        *
        * This function sets the number of readings averaged for calibration 
        * of offset for a given LoadCell through the controller.
        * 
        * @param loadcell_num Number of the LoadCell.
        * @param n_readings Number of readings.
        */
        void set_tare_n_readings(byte loadcell_num, int n_readings);


        /**
        * @brief Get the number of readings averaged for calibration of offset for a given LoadCell.
        *
        * This function sets the number of readings averaged for calibration 
        * of offset for a given LoadCell through the controller.
        * 
        * @param loadcell_num Number of the LoadCell.
        * @return Number of readings averaged for offset calibration.
        */
        byte get_tare_n_readings(byte loadcell_num);


        /**
        * @brief Set the number of readings averaged for calibration of scale coefficient for a given LoadCell.
        *
        * This function sets the number of readings averaged for calibration 
        * of scale coefficient for a given LoadCell through the controller.
        * 
        * @param loadcell_num Number of the LoadCell.
        * @param n_readings Number of readings.
        */
        void set_scale_coeff_n_readings(byte loadcell_num, int n_readings);


        /**
        * @brief Get the number of readings averaged for calibration of scale calibration for a given LoadCell.
        *
        * This function sets the number of readings averaged for calibration 
        * of offset for a given LoadCell through the controller.
        * 
        * @param loadcell_num Number of the LoadCell.
        * @return Number of readings averaged for scale coefficient calibration.
        */
        byte get_scale_coeff_n_readings(byte loadcell_num);


        /**
        * @brief Set the number of readings averaged for weight measurements for a given LoadCell.
        *
        * This function sets the number of readings to be averaged for weight measurements
        * for  a given LoadCell through the controller.
        *
        * @param loadcell_num Number of the LoadCell.
        * @param n_readings Number of reading averaged for a weight measurements.
        */
        void set_weight_n_readings(byte loadcell_num, int n_readings);


        /**
        * @brief Get the number of readings averaged for measurements of a given LoadCell's weight.
        *
        * This function retrieves the number of readings that are averaged for measurements
        * of a given LoadCell's weight.
        *
        * @param loadcell_num loadcell_num Number of the LoadCell.
        * @return Number of reading averaged for a weight measurements.
        */
        byte get_weight_n_readings(byte loadcell_num);


        /**
        * @brief Set the number of readings averaged for calibration of offset for all LoadCells.
        *
        * This function sets the number of readings to be averaged for calibration
        * of offset for all LoadCells.
        *
        * @param n_readings Number of readings averaged for calibration of offset.
        */
        void set_all_loadcells_tare_n_readings(int n_readings);


        /**
        * @brief Set the number of readings averaged for calibration of scale coefficient for all LoadCells.
        *
        * This function sets the number of readings to be averaged for calibration
        * of scale coefficient for all LoadCells.
        *
        * @param n_readings Number of readings averaged for calibration of scale coefficient.
        */
        void set_all_loadcells_scale_coeff_n_readings(int n_readings);


        /**
        * @brief Set the number of readings averaged for weight measurements for all LoadCells.
        *
        * This function sets the number of readings to be averaged for weight measurements
        * for all LoadCells.
        *
        * @param n_readings Number of readings averaged for weight measurements.
        */
        void set_all_loadcells_weight_n_readings(int n_readings);


        /**
        * @brief Read the output of the LoadCell and average @ref weight_n_readings readings.
        *
        * This function does @ref weight_n_readings readings of the raw output of the LoadCell and 
        * calculates their average before returning the average raw output.
        * 
        * @param loadcell_num Number of the LoadCell.
        * 
        * @return The raw averaged reading of the LoadCell.
        */
        long read_raw_average(byte loadcell_num);


        /**
        * @brief Read the output of the LoadCell and average @ref tare_n_readings readings.
        *
        * This function does @ref tare_n_readings readings of the raw output of the LoadCell and 
        * calculates their average before returning the average raw output. It is useful inside calibration scripts.
        * 
        * @param loadcell_num Number of the LoadCell.
        * 
        * @return The raw averaged reading of the LoadCell for the tare offset caibration.
        */
        long read_tare_average(byte loadcell_num);

        /**
        * @brief Read the output of the LoadCell and average @ref scale_coeff_n_readings readings.
        *
        * This function does @ref scale_coeff_n_readings readings of the raw output of the LoadCell and 
        * calculates their average before returning the average raw output. It is useful inside calibration scripts.
        * 
        * @param loadcell_num Number of the LoadCell.
        * 
        * @return The raw averaged reading of the LoadCell for the scale coefficient calibration.
        */
        long read_scale_coeff_average(byte loadcell_num);


        /**
        * @brief Read the raw output of the LoadCell and substracts the offset.
        *
        * This function reads the average of readings of the LoadCell raw output with 
        * @ref read_raw_average() then substracts the offset accessed with @ref get_offset().
        * 
        * @param loadcell_num Number of the LoadCell.
        * 
        * @return The raw averaged reading of the LoadCell difference with the offset.
        */
        double get_raw_value(byte loadcell_num);


        /**
        * @brief Read the weight of the object currently on the LoadCell.
        *
        * This function reads the average of readings of the LoadCell raw output with 
        * @ref read_raw_average() before converting this average value to a mass value 
        * using the calibration function -> output = scale_coeff * mass + offset.
        * 
        * @param loadcell_num Number of the LoadCell.
        * 
        * @return The averaged mass of the object on the LoadCell.
        */
        float get_weight(byte loadcell_num);


        /**
        * @brief Read the raw output of the LoadCell and set this value to the offset
        *
        * This function does tare_n_reading readings to get the average for the offset. 
        * It then sets this value to the member varibale @ref OFFSET. 
        * 
        * @param loadcell_num Number of the LoadCell.
        */
        void tare(byte loadcell_num);


        /**
        * @brief Begin the communication with the HX711 for a given LoadCell.
        *
        * This function begins the communication with the HX711 that is performing a voltage
        * reading of the Wheatstone bridge on the load cell to convert it in a 24-bits digital
        * raw output. This function needs to be called before performing measurements of weight. 
        * 
        * @param loadcell_num Number of the LoadCell.
        * @param dout Digital pin (or analog) connected to the DOUT output pin of the HX711.
        * @param pd_sck Digital pin (or analog) connected to the SCK output of the HX711.
        * @param gain Gain of the HX711. Default is 128.
        * @details The @p gain argument can take the following values: 128, 64 and 32. For a gain of 128 and 64,
        * channel A of the HX711 should be used. For a gain of 32, channel B should be used.
        */
	void begin(
                byte loadcell_num,
                byte dout,
                byte pd_sck,
                byte gain = 128
                );



        /**
        * @brief Verify if the HX711 is ready for a reading.
        *
        * This function verifies if the HX711 is ready for retrieval the next reading. According to
        * the datasheet of the HX711, when output data is not ready for retrieval,
        * digital output pin DOUT is high. Serial clock input PD_SCK should be low. 
        * When DOUT goes to low, it indicates data is ready for retrieval. The latter condition is
        * verified in this member function.
        * 
        * @param loadcell_num Number of the LoadCell.
        * @return Boolean showing if the HX711 is ready for retrieval.
        */
	bool is_ready(byte loadcell_num);


	/**
        * @brief Suspend the execution of the code until the HX711 becomes ready.
        *
        * This function supends the execution of the code with a while loop
        * relying on the @ref is_ready() condition. When called, this function will
        * stop temporarily the code execution until the HX711 becomes ready.
        * 
        * @warning Using this function can completely stop the code execution if a technical problem
        * happens with a HX711. It is safer to handle the retrieval of a reading with @ref wait_ready_retry()
        * or @ref wait_ready_timeout()
        * 
        * @param loadcell_num Number of the LoadCell.
        */
	void wait_ready(
                        byte loadcell_num,
                        unsigned long delay_ms = 0
                        );


        /**
        * @brief Suspend the execution of the code until the HX711 becomes ready 
        * or for a given number of retries.
        *
        * This function supends the execution of the code with a while loop
        * relying on the @ref is_ready() condition. When called, this function will
        * stop temporarily the code execution until the HX711 becomes ready or for a given 
        * number of retries. This prevents from a endless suspension of the code.
        * 
        * @param loadcell_num Number of the LoadCell.
        * @param retries Number of retries to verify the "readiness state" of the HX711. Default is 3.
        * @param delay_ms Delay between two verification of the "readiness state" of the HX711. Default is 0.
        */
	bool wait_ready_retry(
                        byte loadcell_num,
                        int retries = 3,
                        unsigned long delay_ms = 0
                        );


        /**
        * @brief Suspend the execution of the code until the HX711 becomes ready 
        * or for a given timeout.
        *
        * This function supends the execution of the code with a while loop
        * relying on the @ref is_ready() condition. When called, this function will
        * stop temporarily the code execution until the HX711 becomes ready or for a given timeout.
        * If after the timeout the HX711 is not ready for retrieval, the code execution will continue.
        * This prevents from a endless suspension of the code.
        * 
        * @param loadcell_num Number of the LoadCell.
        * @param timeout Timeout of the suspension of execution of the code in milliseconds. Default is 1000 ms.
        * @param delay_ms Delay between two verification of the "readiness state" of the HX711 in milliseconds. Default is 0.
        */
	bool wait_ready_timeout(
                                byte loadcell_num,
                                unsigned long timeout = 1000,
                                unsigned long delay_ms = 0
                                );


        /**
        * @brief Wake up the chip after power down mode.
        *
        * This function powers up the HX711 after calling @ref power_down() member function.
        * 
        * 
        * @param loadcell_num Number of the LoadCell.
        */
	void power_up(byte loadcell_num);


        /**
        * @brief Wake up the chip after power down mode.
        *
        * This function powers down the HX711 after calling @ref power_up() member function.
        * 
        * @note This function doesn't stop the alimentation of the Wheatstone on the load cell,
        * only suspend the HX711.
        * 
        * @param loadcell_num Number of the LoadCell.
        */
	void power_down(byte loadcell_num);

        /** @} */ // End of LoadCell functions for LoadCellController group


        /**
        * @brief Get the number of LoadCell of the LoadCellController.
        *
        * This function returns the number of LoadCell that were added to the LoadCellController
        * with the @ref add_loadcell() member function since the @ref n_loadcell member variabke is
        * kept protected.
        * 
        * 
        * @return Number of LoadCell.
        */
        byte number_of_loadcells();


        /**
        * @brief Verify if a LoadCell number is in the range of the LoadCellController.
        *
        * This function returns boolean teeling whether a number of a LoadCell is in the range
        * of the possible number of LoadCell for a LoadCellController according to his member
        * variable @ref n_loadcell. This function is useful inside all member functions that
        * loadcell_num as parameters to suspend the code execution if necessary.
        * 
        * @return Boolean telling if a LoadCell number is coherent for the LoadCellController.
        */
        bool is_loadcell_num_in_range(byte loadcell_num);

        /**
        * @brief Clear the EEPROM with 0 value.
        *
        * This function writes a 0 at all index on the EEPROM for a given range.
        * 
        * @note The @p end parameters has a defaukt value of 1024 since it is the size 
        * of the Arduino Uno EEPROM. It might not be the case with other microcontroller.
        * 
        * @param start First index to clear. Default is 0
        * @param end Last index to clear. Default is 1024
        */
        void clear_eeprom(int start=0, int end=1024);
};
#endif