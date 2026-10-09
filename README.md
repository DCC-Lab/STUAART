# STUAART

Repository of the STUAART project. 
Authors of this README : Valérie Pineau Noël, Nathan Bérubé and Daniel C. Côté (DCC/M-lab, CERVO brain research center, Université Laval)

## Overview

STUAART is an automated weighing system for mice that tracks individual weights over weeks. Each cage holds three independent scales ; each scale is a load cell (Wheatstone bridge) read by an HX711 24-bit amplifier connected via a 2-pin protocol (DOUT, SCK) to a DFRobot FireBeetle ESP32 V1 microcontroller. The microcontroller logs every measurement to a microSD card and exposes a small HTTP server so a host can pull today's CSV over Wi-Fi.

## Repository layout

| Folder | What's there |
|---|---|
| `Arduino/` | Custom libraries and scripts to run the STUAART. |
| `KiCAD/` | PCB schematic and design mde on KiCAD (version 10.0.7). |
| `CAD/` | Mechanical 3D files for the scale platforms. Print the top platform with high infill density to keep stiffness and reduce creep. |
| `FlaskServer/` | Python script used to catch the data and save on a local NAS. |
| `Notebooks/` | Notebooks that users can run in Google Colaboratory for data post-processing. |


## Getting started with the firmware

1. Install Arduino IDE 2.x or `arduino-cli`.
2. Add the Espressif boards URL in Preferences and install the `esp32` core (board package). 
3. Copy and save files in folder `Arduino` on your computer. 
4. Copy and save the Python script in `FlaskServer` in your local NAS and run it. 
5. If you are using a new Firebeetle ESP-32 board, run `Arduino/FormatSPIFFS/FormatSPIFFS.ino` (prevent error `SPIFFS Mount Failed`). Otherwise, go to the next step. 
6. Open `Arduino/STUAART/STUAART.ino`.
7. Download third-party libraries in the Arduino IDE. See section *Required third-party libraries*.
8. In the Arduino IDE, pick board `FireBeetle-ESP32` (`esp32:esp32:firebeetle32`) in  Tools -> Port, pick the USB serial port, then Verify and Upload.



## Required third-party libraries

Install these via Arduino IDE Library Manager (Sketch -> Include Library -> Manage Libraries):

| Library | Author | Tested version |
|---|---|---|
| HX711 | Bogdan Necula (bogde) | 0.7.5 |
| RTClib | Adafruit | 2.1.4 |
| ArduinoJson | Benoit Blanchon | 7.0.4 |

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

## Error management 

- `Unable to verify flash chip connection` : the default upload speed of 921600 baud is too fast for the CH340 USB-serial chip on the FireBeetle. Set 115200. 

- `SPIFFS Mount Failed` : Run the script in `Arduino/FormatSPIFFS/FormatSPIFFS.ino`. 

- The "GPIO 9 = flash" issue on cell 1 is the root cause of corrupted readings (raw == 0xFFFFFF returned as -160.68 g). A defensive software patch in `LoadCell.cpp` rejects this signature, but the long-term fix is to reroute that DOUT to GPIO 25 or 26 (silkscreen D2 or D3).



