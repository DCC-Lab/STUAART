# Smart Cage - Maxime Tousignant-Tremblay (2024/09/18)

Log file for the test session of 2024/09/18

## Dignostic steps & procedure

The diagnostic of hardware issues requires individual testing of each subsystem, starting from the most basic elements. As such, the first attempt will focus on analysing the data obtained from a single loadcell (100 g) and HX711 module connected to an Arduino board. No SD card reader and no WiFi for now. Tests are going to be conducted on a breadboard. The Arduino Nano ESP32 has been ordered, but not yet delivered so tests are going to use an Arduino Uno R3 today. A quick reconfiguration of the Arduino code, create by Nathan Bérubé, will be necessary.

### Code reconfiguration

Nathan's code had to be modified to allow individual testing of the subsystems. Code blocks regarding mode_pin and automatic callibration has been turned off to force the manual configuration mode. Since the code was designed to use an SD card for data saving and transfer, a Python code was written to allow direct data processing on a computer by reading the serial port connected to the Arduino (via PySerial library), bypassing the need for an SD card. The Python code can plot the measured weight [g] with respect to time [s] in real time and save the raw data to a file simultanuously for further analysis. Every code block related to the SD card module could now be turned off.

### PlateformIO configuration

The Arduino sketch used for this testing session is the file named "main.cpp" in this folder. Since PlateformIO is sensitive to directory tree and naming convention, a copy of the main sketch is kept in this folder. To repeat this testing session, replace the "ElectricalComponentsTesting/SmartCage_PlateformIO/src/main.cpp" file by the "main.cpp" file contained in this folder. THE FILE HAS TO BE NAMED "main.cpp" AND PLACED IN "/src".

### Calibration

To accurately callibrate the loadcell, an object of known mass must be use. Callibration code blocks are already provided in Nathan's work and were not changed. The reference object for this test phase was an Arduino Uno R4 WiFi with it's original plastic shield underneat. The measured mass of the Arduino was 33.6 g.

### Testing and results

Today's test aimed to look for artifacts, noise and other unusual response from the loadcell when the reference object is left on it for about 10 min. Results shows a max $\Delta m$ of about 0.04 g over 10 min. This test therefore confirms that, on a breadboard, a single loadcell & HX711 module connected to an Arduino Uno R3 produces a stable output given the variation tolerance (< 0.1 g).
