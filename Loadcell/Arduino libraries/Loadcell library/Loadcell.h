#ifndef Loadcell_h
#define Loadcell_h
#include <Arduino.h>
#include "HX711.h"
class Loadcell : public HX711 {

protected:
        byte tare_n_readings = 50; // number of readings to determine tare_offset, byte type limits value to 255
        byte scale_coeff_n_readings = 50; // number of readings to determine scale_coeff, byte type limits value to 255
        byte weight_n_readings = 5;    // number of readings to perform for a weight measurements, byte type limits value to 255
public:
        Loadcell();
        
        // //launch calibration process of the tare offset and scale coefficient
        // void calibrate_all();

        // // launch calibration process of the tare offset
        // void calibrate_tare_offset();
        
        // //launch calibration process of the scale coefficient
        // void calibrate_scale_coeff();

        // double determine_tare_offset();

        // double determine_scale_coeff();
        // // calculate the scale coefficient from a raw output reading and the tare offset
        // float calculate_scale_coeff(float output, float mass);

        // // Initialize library with data output pin, clock input pin and gain factor.
	// // Channel selection is made by passing the appropriate gain:
	// //      - With a gain factor of 64 or 128, channel A is selected
	// //      - With a gain factor of 32, channel B is selected
	// //              The library default is "128" (Channel A).
        // // Set the calibration value
        // //      The library default is true
        // void start(byte dout, byte pd_sck, byte gain = 128, bool calibrate = true);

        // // Easy start for calibration and sqving calibration values(tare, scale) to EEPROM all in one function.
        // //
        // // Initialize library with data output pin, clock input pin and gain factor.
	// // Channel selection is made by passing the appropriate gain:
	// //      - With a gain factor of 64 or 128, channel A is selected
	// //      - With a gain factor of 32, channel B is selected
	// //              The library default is "128" (Channel A).
        // // Set the calibration value
        // //      The library default is true
        // void easy_start(byte dout, byte pd_sck, byte gain, bool calibrate_tare, bool calibrate_scale);
        

        long read_average();

        double get_value();

        float get_weight();

        void tare();

        // setter for the number of readings averaged for the determination of the tare offset
        void set_tare_n_readings(int tare_n_readings);

        // getter for the number of readings averaged for the determination of the tare offset
        int get_tare_n_readings();

        // setter for the number of readings averaged for the determination of the scale coefficient
        void set_scale_coeff_n_readings(int scale_coeff_n_readings);

        // getter for the number of readings averaged for the determination of the scale coefficient
        int get_scale_coeff_n_readings();

        // setter for the number of readings averaged for a reading
        void set_weight_n_readings(int weight_n_readings);

        // getter for the number of readings averaged for a reading
        int get_weight_n_readings();

        void power_off(int PD_SCK);
};
#endif