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

        long read_average();

        long read_tare_average();

        long read_scale_coeff_average();

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
};
#endif