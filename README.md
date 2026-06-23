# STUAART

Repo of the STUAART project, created July 12 2023 by Nathan Bérubé. Continued by Valérie Pineau Noël and Daniel C. Côté (DCC/M Lab, Université Laval / CERVO).

## Overview

STUAART is an automated weighing system for mice that tracks individual weights over weeks. Each cage holds three independent scales ; each scale is a load cell (Wheatstone bridge) read by an HX711 24-bit amplifier connected via a 2-pin protocol (DOUT, SCK) to a DFRobot FireBeetle ESP32 V1 microcontroller. The microcontroller logs every measurement to a microSD card and exposes a small HTTP server so a host can pull today's CSV over Wi-Fi.

## Repository layout

| Folder | What's there |
|---|---|
| **`Firmware/`** | The production firmware : sketch + custom libraries, a docs folder with the Doxygen-generated PDF, and a README that explains compile/upload. **Start here.** |
| `Loadcell/` | Historical drift / linearity / mouse-experiment material, plus standalone example sketches. See `Loadcell/README.md`. |
| `KiCAD/` | Three PCB revisions : `Version1/`, `V2/` (currently in production), `V3/` (newer revision, not deployed). |
| `CAD/` | Mechanical 3D files for the scale platforms (Mireille manages the Fusion360 team for the rest). Print with high infill density to keep stiffness and reduce creep. |
| `CapacitiveSensor/` | Example sketch and a guide PDF for the capacitive sensor used to detect mouse presence. |
| `CageServer/` | Code for a host-side server (separate from the microcontroller HTTP server). |
| `PostProcessingCode/` | Python scripts used after data collection. |
| `Presentations/` | Talk slides on the project. |

## Getting started with the firmware

See [Firmware/README.md](Firmware/README.md) for the full procedure. Summary :

1. Install Arduino IDE 2.x or `arduino-cli`.
2. Add the Espressif boards URL in Preferences and install the `esp32` core (board package).
3. Library Manager : install **HX711 by Bogde**, **RTClib by Adafruit**, and **ArduinoJson by bblanchon**. Tested versions are listed in `Firmware/README.md`.
4. Open `Firmware/STUAART/STUAART.ino`. The custom libraries (`LoadCell.{h,cpp}` and `LoadCellController.{h,cpp}`) sit beside the `.ino` and compile automatically as part of the sketch — no copying to `~/Documents/Arduino/libraries/`.
5. Pick board `FireBeetle-ESP32` (`esp32:esp32:firebeetle32`), pick the USB serial port, then Verify and Upload.

If `arduino-cli` complains during upload with *Unable to verify flash chip connection*, the default upload speed of 921600 baud is too fast for the CH340 USB-serial chip on the FireBeetle. Force 115200 :

```sh
arduino-cli upload --fqbn esp32:esp32:firebeetle32 \
  -p /dev/cu.usbserial-XX --upload-property upload.speed=115200 \
  Firmware/STUAART
```

`SPIFFS Mount Failed` on a brand-new FireBeetle : run `Loadcell/SketchExamples/FormatSPIFFS/FormatSPIFFS.ino` once on the new board.

If the **link** step fails with garbled errors like `DWARF error: could not find abbrev number`, `bad reloc symbol index`, or `orphan section ''` (often referencing `LoadCell.cpp.o`), the sketch did **not** change — the Arduino build cache is stale or corrupt. This commonly happens after switching git branches or changing the selected board, because the IDE reuses object files that no longer match. It is not a code error. Fix it by forcing a clean rebuild :

```sh
arduino-cli cache clean
arduino-cli compile --clean --fqbn esp32:esp32:firebeetle32 Firmware/STUAART
```

In the Arduino IDE 2.x, the equivalent is to quit, delete `~/Library/Caches/arduino/sketches/` (macOS) / `%LOCALAPPDATA%\Temp\arduino\sketches\` (Windows), then Verify again. After the cache is cleared the firmware builds cleanly every time.

## A minimal load cell read

```cpp
#include "LoadCell.h"
#include "LoadCellController.h"

LoadCell loadcell;
LoadCellController controller;

void setup() {
  Serial.begin(115200);
  controller.add_loadcell(loadcell);
  controller.easy_start_with_params(
      1,        // loadcell number
      27,       // DOUT pin (avoid GPIO 6-11, those are the flash bus)
      17,       // SCK pin
      true,     // calibrate offset
      true,     // calibrate scale
      false,    // read offset from memory
      false,    // read scale from memory
      true,     // save offset to memory
      true,     // save scale to memory
      0,        // manual tare offset (0 = not specified)
      0,        // manual scale coeff (0 = not specified)
      128       // gain, do not change
  );
}

void loop() {
  controller.wait_ready_timeout(1, 1000);
  float reading = controller.get_weight(1);
  Serial.println(reading);
}
```

## Known hardware issue : GPIO 9 / flash conflict on PCB V2

On the production PCB (V2), cell 1 DOUT is routed to FireBeetle pin **D5 (GPIO 9)**. On the ESP32-D0WD chip used in this FireBeetle revision, GPIO 9 is bonded to the external flash SPI bus (data line SD2). The flash controller drives this line continuously while code executes, so the HX711 output and the flash bus collide on the same wire — cell 1 readings on V2 are intermittently corrupted (most of the time the chip returns 0xFFFFFF, which after offset scaling shows up as a constant ~−160 g spike).

The firmware has a defensive patch in `LoadCell::safe_read()` that detects and retries the most common corruption signatures (raw == −1, 0x800000, 0x7FFFFF), but software cannot fully compensate for the bus contention. **The proper fix is mechanical** : lift D5 from the FireBeetle socket (or cut the trace) and add a strap from the U1-DAT pad to a free GPIO. **D2 (GPIO 25)** and **D3 (GPIO 26)** are unconnected on PCB V2 and ideal for this rework. Then change `controller.add_loadcell(loadCell1, 9, 17)` to `controller.add_loadcell(loadCell1, 25, 17)` (or `26`).

## Lab notes

Drift, linearity and outlier characterization are documented in the lab-notes Overleaf document : <https://www.overleaf.com/read/vvxvjbdjmgmg>.

## Documentation

The Doxygen-generated PDF for `LoadCell` and `LoadCellController` is at [`Firmware/docs/LoadCell-API-V2.02.pdf`](Firmware/docs/LoadCell-API-V2.02.pdf).

To regenerate it from current sources :

```sh
cd Firmware/STUAART
doxygen -g                                  # creates a Doxyfile
# edit Doxyfile : set RECURSIVE = YES
doxygen Doxyfile                             # produces html/ and latex/
cd latex && pdflatex refman.tex              # produces refman.pdf
```
