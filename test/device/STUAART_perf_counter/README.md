# Real-time flash-bus activity probe (experimental, not merged)

Goal of this branch : detect ESP32 flash-bus activity **in real time** so a
HX711 read on cell 1 can be *skipped while the bus is busy*, instead of the
post-hoc detect-and-retry strategy in `safe_read`. Cell 1's DOUT shares
GPIO 9 with the flash interface, so any flash transaction overlapping a read
can corrupt it.

Two real-time probes were tried. Neither shipped — the production fix is the
hardware strap (cell 1 DOUT off GPIO 9) plus the `safe_read` signature filter.

## Attempt 1 : Xtensa LX6 performance counter (FAILED, abandoned)

Used the ESP-IDF `xtensa_perfmon_*` API to count instruction-cache miss
penalty cycles (`XTPERF_CNT_ICACHE_MISSES = 0x8005`) over each read window.

The API links and `xtensa_perfmon_init` returns `ESP_OK`, but **the counter
stays at 0** even for the trivial `XTPERF_CNT_CYCLES` event. Likely causes :
the Arduino ESP32 core never sets the global PMG enable bit, or it does not
save/restore the perfmon special registers across FreeRTOS context switches,
or kernel-mode privilege is required for those SRs. The raw-SR fallback is
also blocked : the `.pm0` / `wsr.pmg` mnemonics are not recognised by the
toolchain shipped with arduino-cli 1.4.1.

Reviving it would require recompiling ESP-IDF with the perfmon component
enabled (the Arduino core does not expose it) or porting to PlatformIO/
ESP-IDF native. Judged not worth the effort — this path is a dead end under
the Arduino framework.

## Attempt 2 : SPI0 flash state-machine register (what the current sketch does)

`STUAART_perf_counter.ino` polls the SPI0 controller's `EXT2` register
(offset `0xF8` from SPI0 base `0x3FF43000`). Its low 3 bits are the
`SPI_ST` state field : `0` when the flash bus is idle, non-zero during a
transaction. SPI1 (`0x3FF42000`) is sampled in parallel as a control.

If this register actually tracks cache-miss / PROGMEM-fetch activity, it
gives a direct "flash bus busy" signal that can be polled just before each
HX711 SCK pulse — no perfmon counter needed.

What the sketch does :

1. `raw_snapshot()` — dump the raw EXT2 registers over 1 ms with no stress,
   to confirm the field even moves on its own.
2. `probe()` — sample `SPI_ST` 100k times under three stress patterns
   (`idle`, `ram`, `progmem`) and tally the state distribution plus a
   busy-percentage for SPI0 and SPI1.
3. Expectation : a high non-zero `SPI0_busy` % under PROGMEM stress and a low
   one under RAM/IRAM stress would confirm the register is a useful indicator.

This is the more promising direction and is where the code was left. It was
not driven to a conclusion (no merge, no production wiring).

## Why none of this shipped

1. `safe_read` rejects the dominant corruption signatures (`0xFFFFFF`,
   `0x800000`, `0x7FFFFF`) with 100 % recovery in the bench hunter test.
2. The `cycles count` duration proxy in `STUAART_flash_correlate` already
   exposes ~2/3 of corruptions via abnormally short read durations.
3. The proper fix is the hardware strap (cell 1 DOUT off GPIO 9), which
   trumps any software workaround. The GPIO-9 software mitigation that *did*
   land on master (IRAM read + critical section, gated by
   `STUAART_v5_CORRUPTED_GPIO9`) covers the un-strapped boards.

## How to dust this off later

- For the SPI-state-machine path : run the sketch on a corrupted-GPIO-9 board
  and check whether `SPI0_busy` % rises under PROGMEM stress. If it does,
  wire a `while (spi0_st() != 0) {}` guard just before the HX711 SCK pulses
  in `LoadCell::read()` and re-run the bench hunter test.
- For the perfmon path : don't, unless moving to ESP-IDF native — see above.
