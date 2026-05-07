// Minimal Arduino.h stub for host-side unit tests.
// Provides only what LoadCell.cpp / LoadCellController.cpp need to compile
// without an Arduino target. The runtime functions are no-ops ; the tests
// drive behaviour through the HX711 stub instead.
#pragma once

#include <cstdint>
#include <cstring>
#include <cstdio>
#include <cstdlib>

typedef uint8_t  byte;
typedef uint16_t word;
typedef bool     boolean;

#define HIGH        1
#define LOW         0
#define INPUT       0
#define OUTPUT      1
#define INPUT_PULLUP 2
#define INPUT_PULLDOWN 3
#define LSBFIRST    0
#define MSBFIRST    1

inline void delay(unsigned long)             {}
inline void delayMicroseconds(unsigned int)  {}
inline unsigned long millis()                { return 0; }
inline unsigned long micros()                { return 0; }
inline void pinMode(int, int)                {}
inline void digitalWrite(int, int)           {}
inline int  digitalRead(int)                 { return 0; }
inline uint8_t shiftIn(int, int, int)        { return 0; }

// String stub : just enough for CSV concatenation tests if we add them later.
// LoadCell.cpp / LoadCellController.cpp don't actually use Arduino String,
// so a no-op stub is fine.
class String {
public:
    String() {}
    String(const char*) {}
    String(long, int = 10) {}
    String(float) {}
    String operator+(const String&) const { return String(); }
};

#define F(s) (s)

// Stubs for Print / Stream just to satisfy any stray include.
class Print {
public:
    void print(const char*) {}
    void println(const char* = "") {}
    void print(int) {}
    void println(int) {}
    void print(long) {}
    void println(long) {}
    void print(float) {}
    void println(float) {}
};

class Stream : public Print {
public:
    int   available()  { return 0; }
    int   read()       { return -1; }
    long  parseInt()   { return 0;  }
    float parseFloat() { return 0.f; }
};

// Mock Serial just so LoadCellController error paths compile if a test
// inadvertently triggers them (the test suite avoids those code paths).
extern class _MockSerial : public Stream {
public:
    void begin(unsigned long) {}
    void flush() {}
} Serial;
