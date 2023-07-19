#ifndef Loadcell_controller_h
#define Loadcell_controller_h
#include <Arduino.h>
#include "HX711.h"
#include "Loadcell.h"

class Loadcell_controller {
protected:
        Loadcell* loadcells[10];
        int n_loadcell = 0;

public: 
        Loadcell_controller();

        void add_loadcell(Loadcell &loadcell);

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

        void easy_calibration_with_params(
                                        byte loadcell_num,
                                        bool cal_tare,
                                        bool cal_scale
                                        );

        void easy_save_to_eeprom_with_params(
                                byte loadcell_num,
                                bool save_offset,
                                bool save_scale
                                );

        void easy_read_from_eeprom_with_params(byte loadcell_num, bool read_offset_eeprom, bool read_scale_eeprom);

        void easy_start_with_questions(byte loadcell_num, byte dout, byte pd_sck, byte gain=128);

        void easy_calibration_with_questions(byte loadcell_num, bool cal_tare, bool cal_scale);

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

        void save_offset_eeprom(byte loadcell_num);

        void save_scale_eeprom(byte loadcell_num);

        long read_offset_from_eeprom(byte loadcell_num);

        float read_scale_from_eeprom(byte loadcell_num);

        void calibrate_both_params(byte loadcell_num);

        void calibrate_tare_offset(byte loadcell_num);

        void calibrate_scale_coeff(byte loadcell_num);

        float determine_offset(byte loadcell_num);

        float determine_scale_coeff(byte loadcell_num);

        float calculate_scale_coeff(byte loadcell_num, float output, float mass);

        void set_offset_adress(byte loadcell_num, int adress);

        int get_offset_adress(byte loadcell_num);

        void set_scale_adress(byte loadcell_num, int adress);

        int get_scale_adress(byte loadcell_num); 

        float get_offset(byte loadcell_num);
        
        void set_offset(byte loadcell_num, float offset); 

        float get_scale(byte loadcell_num);

        void set_scale(byte loadcell_num, float scale); 

        void set_tare_n_readings(byte loadcell_num, int n_readings);

        byte get_tare_n_readings(byte loadcell_num);

        void set_scale_coeff_n_readings(byte loadcell_num, int n_readings);

        byte get_scale_coeff_n_readings(byte loadcell_num);

        void set_weight_n_readings(byte loadcell_num, int n_readings);

        byte get_weight_n_readings(byte loadcell_num);

        void set_all_loadcells_tare_n_readings(int n_readings);

        void set_all_loadcells_scale_coeff_n_readings(int n_readings);

        void set_all_loadcells_weight_n_readings(int n_readings);

        byte number_of_loadcells();

        bool is_loadcell_num_in_range(byte loadcell_num);

        void clear_eeprom(int start=0, int end=1024);
};
#endif