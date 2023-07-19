#ifndef Loadcell_controller_h
#define Loadcell_controller_h
#include <Arduino.h>
#include "HX711.h"
#include "Loadcell.h"

class Loadcell_controller {
protected:
        Loadcell* loadcells[10];
        int n_loadcell = 0;

        void easy_calibration_with_params(
                                        byte loadcell_num,
                                        bool cal_tare,
                                        bool cal_scale
                                        );

        // According to the parameters passed to easy_start_with_params(),
        // this function saves to EEPROM the offset and scale coeff resulting
        // from calibration or directly given to easy_start function
        void easy_save_to_eeprom_with_params(
                                byte loadcell_num,
                                bool save_offset,
                                bool save_scale
                                );

        // According to the parameters passed to easy_start_with_params(),
        // this function reads offset and scale coeff from EEPROM and set them
        // to the Loadcell object attributs
        void easy_read_from_eeprom_with_params(
                                        byte loadcell_num,
                                        bool read_offset_eeprom,
                                        bool read_scale_eeprom
                                        );

        // not implemented 
        void easy_start_with_questions(
                                byte loadcell_num,
                                byte dout,
                                byte pd_sck,
                                byte gain=128
                                );

        // not implemented 
        void easy_calibration_with_questions(
                                        byte loadcell_num,
                                        bool cal_tare,
                                        bool cal_scale
                                        );

        // verify if there is any conflicts between parameters passed to
        //easy_start_with_params() will stop code if a conflict is found
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
        Loadcell_controller();
        
        // add a loadcell to the controller
        void add_loadcell(Loadcell &loadcell);

        // all-in-one function that manages everything related
        // to the initialization of a loadcell, its calibration and
        // management of the two calibration parameters (offset and scale coefficient)
        int easy_start_with_params(
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

        // save offset on EEPROM of a given loadcell
        void save_offset_eeprom(byte loadcell_num);

        // save scale coefficient on EEPROM of a given loadcell
        void save_scale_coeff_eeprom(byte loadcell_num);

        // read offset from EEPROM for a given loadcell
        long read_offset_from_eeprom(byte loadcell_num);

        // read scale_coeff from EEPROM for a given loadcell
        float read_scale_coeff_from_eeprom(byte loadcell_num);

        // begin calibration process for offset and scale coefficient
        // and set the values of both
        void calibrate_both_params(byte loadcell_num);

        // begin calibration process for offset and set the value
        void calibrate_tare_offset(byte loadcell_num);

        // begin calibration process for cale coefficient and set the value
        void calibrate_scale_coeff(byte loadcell_num);

        // begin calibration process for offset and return offset value
        float determine_offset(byte loadcell_num);

        // begin calibration process for scale coeff and return value
        float determine_scale_coeff(byte loadcell_num);

        // calculate scale coeff from a known offset
        // and a couple (known weight, loadcell outpu)
        float calculate_scale_coeff(
                                byte loadcell_num,
                                float output,
                                float mass
                                );

        // not implemented
        void set_offset_adress(byte loadcell_num, int adress);

        // return offset adress for a given loadcell
        int get_offset_adress(byte loadcell_num);

        // not implemented
        void set_scale_adress(byte loadcell_num, int adress);

        // return scale coeff adress for a given loadcell
        int get_scale_coeff_adress(byte loadcell_num); 

        // getter for offset value of a given loadcell
        float get_offset(byte loadcell_num);

        // setter for offset value of a given loadcell
        void set_offset(byte loadcell_num, float offset); 

        // gette for scale coeff for a given loadcell
        float get_scale(byte loadcell_num);

        // setter for scale coeff of a given loadcell
        void set_scale(byte loadcell_num, float scale); 

        // setter for the number of readings averaged for calibration
        // of offset for a given loadcell
        void set_tare_n_readings(byte loadcell_num, int n_readings);

        // getter for the number of readings averaged for calibration
        // of offset for a given loadcell
        byte get_tare_n_readings(byte loadcell_num);

        // setter for the number of readings averaged for calibration
        // of scale coefficient for a given loadcell
        void set_scale_coeff_n_readings(byte loadcell_num, int n_readings);

        // getter for the number of readings averaged for calibration
        // of scale coefficient for a given loadcell
        byte get_scale_coeff_n_readings(byte loadcell_num);

        // setter for the number of readings averaged for a measurements
        // for a given loadcell
        void set_weight_n_readings(byte loadcell_num, int n_readings);

        // getter for the number of readings averaged for a measurement
        // for a given loadcell
        byte get_weight_n_readings(byte loadcell_num);

        // set number of readings averaged for calibration of tare
        // for all loadcells
        void set_all_loadcells_tare_n_readings(int n_readings);

        // set number of readings averaged for calibration of scale coeff
        // for all loadcells
        void set_all_loadcells_scale_coeff_n_readings(int n_readings);

        // set number of readings averaged for a measurements
        // for all loadcells
        void set_all_loadcells_weight_n_readings(int n_readings);

        // return number of loadcells
        byte number_of_loadcells();

        // verifies if loadcell number is coherent with the number
        // of loadcells controlled by the controller
        bool is_loadcell_num_in_range(byte loadcell_num);

        // put 0 in every EEPROM position in a specific intervall of index
        void clear_eeprom(int start=0, int end=1024);
};
#endif