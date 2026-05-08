# Xtensa LX6 performance counter probe (incomplete)

Attempt to read the ESP32 instruction-cache miss counter (`XTPERF_CNT_ICACHE_MISSES = 0x8005`) over the window of a HX711 read on cell 1, in order to discard reads that overlap with flash bus activity instead of relying on the post-hoc retry-on-corruption strategy in `safe_read`.

## Status : did not work in this Arduino ESP32 build

The `xtensa_perfmon_*` API from `tools/esp32-libs/3.3.8/include/perfmon/` links and reports `ESP_OK` at init, but the counter stays at 0 even when called with the simplest `XTPERF_CNT_CYCLES` event. The global PMG enable bit is presumably not getting set, OR the FreeRTOS context switch on the Arduino ESP32 framework does not save/restore the perfmon registers, OR the kernel-mode privilege is required for these special registers.

Investigating further would require :

- access to `wsr.pmg` / `rsr.pm0` etc. via raw special-register numbers in inline assembly (the `.pm0` mnemonic is not recognised by the toolchain shipped with arduino-cli 1.4.1)
- or recompiling ESP-IDF with the perfmon component explicitly enabled, which the Arduino ESP32 core does not expose
- or porting the firmware to PlatformIO/ESP-IDF rather than the Arduino IDE wrapper

None of these are worth the effort given that :

1. the existing `safe_read` filter catches the dominant corruption signatures (`0xFFFFFF`, `0x800000`, `0x7FFFFF`) with 100 % recovery in the bench hunter test
2. the `cycles count` proxy in `STUAART_flash_correlate` already exposes 2/3 of the corruptions via abnormally short read durations
3. the proper fix is the hardware strap (cell 1 DOUT off GPIO 9), which trumps any software workaround

## What this sketch does (when the API works)

1. configures PM0 to count instruction-cache miss penalty cycles
2. reads PROGMEM data sequentially as a "thrash" routine to provoke flash bus activity
3. snapshots the counter immediately before and after each `HX711::read()` on cell 1
4. correlates the per-read miss count with whether the value matched a corruption signature
5. prints a histogram so we can see if corrupt reads concentrate at high miss counts

## How to dust this off later

If someone wants to get the perfmon working :

- start by writing a minimal sketch that does just `xtensa_perfmon_init(0, 0, 1, 1, -1)` (CYCLES event) and `xtensa_perfmon_start()`, then dumps `xtensa_perfmon_value(0)` in a loop
- if it stays at 0, the fundamental issue is the global enable. Look at ESP-IDF's `xtensa_perfmon_exec()` source to see what additional setup it does (this is what works in IDF-native builds)
- the simplest way to access the underlying registers is to take that source code and inline it into our sketch
