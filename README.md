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

## Mass time series analysis

Each step of the post-processing analysis can be performed using notebooks run via Google Colaboratory. To begin, the raw mass time series must be uploaded to the user's personal Google Drive. We also recommend that users save a personal copy of each notebook to their own Google Drive by clicking on *File > Save a copy in Drive* once opened via the links below. Users are free to modify their own versions of the notebooks as desired. 

1. **Remove buffer flush indicators from the raw mass time series** : String such as "--, --, --, -- \n" are saved in the raw data to indicate the moments when the buffer flushed its contents onto the SD card. This data can be used to evaluate the time it takes to flush all data and how many times the buffer flushes the data over a given period. For further analysis, these indicators nust be removed. You can do this using this notebook :
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/DCC-Lab/STUAART/blob/master/Remove_buffer_flush_indicators_in_raw_data_Time_from_Real_time_Clock.ipynb)


2. **Correct for baseline shift and remove outliers** : This step is the most computationally intensive. Longitudinal mass time series are affected by mechanical and thermal drifts that alter the value of the initial tare and shift the measured mass by multiple grams, which must be corrected to ensure accuracte evaluation. Additionally, transient spikes can occur and should be filtered out. Users can choose whether to remove outliers and select which baseline correction algorithm best suits their data. Four baseline correction algorithms are provided : density-based spatial clustering of applications with noise (DBSCAN), kernel-density estimation (KDE), Gaussian mixture model (GMM) and a custom rolling-mean filtering. As presented in the main manuscript, the authors achieved optimal results with DBSCAN, while the custom rolling-mean filtering performs well for more stable data sets. We also provide a graphical user interface (GUI) for manual baseline fine-tuning and quick data visualization. We suggest testing different algorithms and using the notebook *Compute_metrics.ipnyb* to evaluate quantitatively the accuracy and precision of the baseline-corrected mass compared to ground-truth mass measurements. If ground-truth data was not acquired, a simple visual inspection of the baseline-corrected mass time series can guide algorithm selection. More information is available in the supplementary information document and within the notebook :
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/DCC-Lab/STUAART/blob/master/Correct_mass_time_series_for_baseline_shift.ipynb)

3. **Display mass time series and compute mass per time bin** : After baseline correction and outlier removal, the users can display the mass time series for visual evaluation. The data can be displayed per scale, for the overall measured mass of the system (summed mass time series per timepoint) and by the relative mass change (where the mass at time = 0 hour is 0%). The users can also obtain the mass per time bin. 
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/DCC-Lab/STUAART/blob/master/Display_mass_data_and_compute_average_mass_One_cage.ipynb)

4. **Compute metrics** : Quantitative evaluation of the mass compared to ground-truth measurements can be obtained via this notebook : 
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/DCC-Lab/STUAART/blob/master/Compute_metrics.ipynb)

5. **Evaluate location, grid-hanging and active state behaviors** : Three additional notebooks are provided to identify and evaluate the spatial occupancy of each scale, the grid-hanging behavior and the active VS inactive states over time. 
   - [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/DCC-Lab/STUAART/blob/master/Identify_location_One_cage.ipynb)
   - [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/DCC-Lab/STUAART/blob/master/Identify_hanging_One_cage.ipynb)
   - [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/DCC-Lab/STUAART/blob/master/Identify_active_VS_inactive_One_cage.ipynb)




