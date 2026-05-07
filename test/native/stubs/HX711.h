// Mock HX711 base class for host-side unit tests of LoadCell.
//
// Replaces the real bogde/HX711 (which lives in the Arduino libraries
// folder) for the duration of the test build. The mock is programmable :
// tests inject a scripted sequence of raw values into `mock_sequence` and
// every call to `read()` consumes the next one. This lets us verify
// LoadCell::safe_read retries on corruption signatures, that
// read_raw_average excludes corrupted samples, and that the lifetime
// counters increment correctly — without ever touching real hardware.
#pragma once

#include <cstddef>
#include <vector>

class HX711 {
public:
    // Programmable scripted output. Tests push values, each call to
    // read() pops one from the front. When the queue is empty, returns
    // `default_value` (default 0).
    std::vector<long> mock_sequence;
    size_t mock_idx = 0;
    long   default_value = 0;

    // Track how many times read() was called : useful to assert that
    // safe_read consumed the expected number of HX711 conversions.
    size_t read_calls = 0;

    HX711() {}
    virtual ~HX711() {}

    // The whole point of the mock : make read() virtual + scripted.
    virtual long read() {
        read_calls++;
        if (mock_idx < mock_sequence.size()) {
            return mock_sequence[mock_idx++];
        }
        return default_value;
    }

    // Subset of HX711 API used by LoadCell.cpp / LoadCellController.cpp.
    void  begin(byte, byte, byte = 128) {}
    bool  is_ready()                    { return true; }
    void  wait_ready(unsigned long = 0) {}
    bool  wait_ready_retry(int = 3, unsigned long = 0)        { return true; }
    bool  wait_ready_timeout(unsigned long = 1000, unsigned long = 0) { return true; }
    void  set_gain(byte)                {}

    void  set_offset(long o)            { OFFSET = o; }
    long  get_offset()                  { return OFFSET; }
    void  set_scale(float s)            { SCALE = s; }
    float get_scale()                   { return SCALE; }

    long  read_average(byte times)      {
        long sum = 0;
        for (byte i = 0; i < times; i++) sum += read();
        return sum / times;
    }
    double get_value(byte times = 1)    { return read_average(times) - OFFSET; }
    float  get_units(byte times = 1)    { return get_value(times) / SCALE; }
    void   tare(byte times = 10)        { set_offset(read_average(times)); }

    void  power_down() {}
    void  power_up()   {}

    // Helpers for tests : reset all state between cases.
    void mock_reset() {
        mock_sequence.clear();
        mock_idx = 0;
        default_value = 0;
        read_calls = 0;
        OFFSET = 0;
        SCALE = 1.0f;
    }

    void mock_push(long v)              { mock_sequence.push_back(v); }
    template<class It>
    void mock_push_n(It first, It last) { mock_sequence.insert(mock_sequence.end(), first, last); }

protected:
    long  OFFSET = 0;
    float SCALE  = 1.0f;
};
