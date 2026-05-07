# Loadcell

Historical material for the load cell side of STUAART : characterization data, test sketches, and analysis scripts. The production firmware (sketch + custom libraries) lives in `../Firmware/STUAART/`, not here.

## Contents

| Folder | What it is |
|---|---|
| **`LoadcellDriftTest/`** | Drift tests of a load cell over hours/days, with raw CSV data and the Arduino sketches used to record them. Dates from 2023-06 to 2023-07. The lab-notes Overleaf document referenced in the top-level README explains each test. ~9 MB of CSV. |
| **`LoadCellLinearityTest/`** | Linearity test : a Python script (`LoadCellLinearity.py`) and one CSV (`testlinearityloadcelldata.csv`) measuring response vs. known reference weights. |
| **`300gLoadCell/`** | Drift test of a 300 g load cell (vs the 1 kg cells used in production) with a wheel mounted on top. One Python script + CSV. |
| **`SketchExperimentsWithMouse/`** | Two early Arduino sketches used during real mouse measurements (2024-02-01 and 2024-04-07). |
| **`SketchExamples/`** | Ready-to-flash example sketches : reading a single HX711, reading two HX711s simultaneously, formatting the SPIFFS partition on a Firebeetle, managing files on the SD card, and two recalibration patterns (with mode switching, and standalone). Use these to debug a single subsystem in isolation. |
| **`OutliersFilteringInPython/`** | One Python script (`20240214_outliersfiltering.py`) demonstrating how to detect and remove HX711 corruption outliers from a CSV. |
| `LoadCellCircuit.png` | Schematic image of the load cell wiring (Wheatstone bridge + HX711). |

## Note on the example sketches

The sketches in `SketchExamples/` and `SketchExperimentsWithMouse/` use `#include "LoadCell.h"` and `#include "LoadCellController.h"`. Those headers now live in `../Firmware/STUAART/`. To compile any of these old sketches, copy the four files (`LoadCell.{h,cpp}` and `LoadCellController.{h,cpp}`) from `../Firmware/STUAART/` into the sketch folder beside the `.ino`, or set up the example as a standalone sketch with its own copy of the libs.

## API documentation

The Doxygen-generated PDF documenting the public API of `LoadCell` and `LoadCellController` has been moved to `../Firmware/docs/LoadCell-API-V2.02.pdf`. The original `Doxyfile` has been removed since it referenced library paths that no longer exist; regenerate it from scratch in `../Firmware/STUAART/` if newer docs are needed.
