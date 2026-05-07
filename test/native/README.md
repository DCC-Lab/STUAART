# Host-side unit tests for STUAART firmware

Unit tests for the `LoadCell` class that compile and run on the host (no Arduino flashing required). The production sketch in `Firmware/STUAART/` is unchanged ; the tests inject a programmable mock `HX711` via the include path so they can script every read.

## Run

```sh
cd test/native
make             # builds and runs
make clean       # removes build/
```

Expected output :

```
LoadCell host-side unit tests
=============================

35 passed, 0 failed
```

## What is covered

- `safe_read` returns the first read when clean
- `safe_read` retries on `0xFFFFFF`, `0x800000`, `0x7FFFFF` and returns the recovered value
- `safe_read` gives up after `max_retries` (default 3) and returns `-1L`
- `read_raw_average` excludes corrupted samples and divides by the count of GOOD reads
- `read_raw_average` returns `-1L` when every sample fails
- The lifetime counters (`total_reads`, `corrupted_neg1`, `corrupted_negsat`, `corrupted_possat`) increment correctly
- `reset_stats` zeros all four counters
- The `set_*_n_readings` setters clamp to `[1, 255]`
- `get_weight` correctly applies offset and scale (positive and negative scales)

## How it works

```
test/native/
├── Makefile                 # builds with clang++/g++
├── stubs/
│   ├── Arduino.h            # minimal byte typedef, no-op pinMode/delay/...
│   ├── HX711.h              # programmable mock with virtual read()
│   ├── SPI.h                # empty
│   └── stubs.cpp            # extern Serial instance
├── test_loadcell.cpp        # tests + tiny zero-deps assertion macros
└── README.md
```

The Makefile compiles `Firmware/STUAART/LoadCell.cpp` with `-Istubs` listed BEFORE `-IFirmware/STUAART/`, so the `#include "HX711.h"` inside `LoadCell.h` resolves to the mock instead of the real Bogde HX711 library. The test file pushes scripted values into `mock_sequence` and verifies that `safe_read` and the averaging methods react correctly.

## Adding a test

1. Write a `TEST(my_test_name)` block in `test_loadcell.cpp` using `ASSERT_EQ` / `ASSERT_TRUE` / `ASSERT_FALSE`.
2. Call `run_my_test_name()` from `main()`.
3. `make` to run.

## Limitations

- These tests cover **logic only**. Hardware-dependent behaviour (HX711 SCK timing, SD writes, SPIFFS persistence, RTC, WiFi) needs **on-device tests** with AUnit on the Firebeetle.
- The mock `HX711` does not simulate the timing constraints of the real chip ; it just plays back scripted values.
- The `LoadCellController` class is not yet covered ; same approach (mock the underlying `LoadCell`) would work but the controller has many more methods.

## Why no PlatformIO / Catch2 / GoogleTest ?

Kept dependency-free on purpose : a Makefile and clang++ are enough. Adding Catch2 or PlatformIO would buy fancier output and parameterized tests, but at the cost of a bigger setup cost for new contributors. Move to one of those if and when the test suite grows past ~50 cases.
