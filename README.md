# This branch shouldn't be merged with master, it doesn't bring anything useful, it was simply created to debug the origin of the outliers.

Turns out it came from having one clock for multiple loadcells. The firebeetle would send through the clock the signal to start transmitting data to all the loadcells simultaneously even though some of them weren't ready. The firebeetle didn't know because it was only listening to one loadcell at a time, and so would only wait for the current loadcell to be ready. This caused a problem where the loadcell would receive the signal to send the second bit, but since it missed the first one because it wasn't ready, it would send it's first. So when it would be it's time, it would be missaligned by one bit and give out an outlier.

# Tutorial
To run the test code, you need to :

1) Push the file : https://github.com/DCC-Lab/STUAART/blob/firebeetle-clock-spikes-tests/CageServer/Code/FireBeetleSpikes/FireBeetleSpikes.ino
    on the Firebeetle. You should use the breadboard system with the same pins plugged in.

<p float="left">
  <img width="500" src="https://github.com/user-attachments/assets/22d1be5d-7ec2-4c8e-8164-a5f6b8df750b">
  <img width="500" src="https://github.com/user-attachments/assets/f652b5b3-1727-4039-969f-007792a51449">
  <img width="500" src="https://github.com/user-attachments/assets/99b592bc-c1f8-4089-a574-b8ddce60f919">
</p>


2) Run https://github.com/DCC-Lab/STUAART/blob/firebeetle-clock-spikes-tests/CageServer/Code/PlotAndSaveSerialData.py
This Python file will paste to the terminal everything sent through Serial by the firebeetle.
You will need to calibrate the loadcells and everything as usual before it starts measuring the weight.
It will also save a file with the current date and time as the title with all the data in it (ex: 202412041005_FireBeetleClock.txt) in the SpikesData folder (https://github.com/DCC-Lab/STUAART/tree/firebeetle-clock-spikes-tests/CageServer/Code/SpikesData).

![image](https://github.com/user-attachments/assets/2261dfe3-48c4-44b9-9aa4-5676a705b68b)

3) You can use my QuickPlot.py file to visualize the data. (https://github.com/DCC-Lab/STUAART/blob/firebeetle-clock-spikes-tests/CageServer/Code/QuickPlot.py)
You just need to modify the variable fileName to what your file is called or you can copy paste your data in the running.txt file.
   
   ![image](https://github.com/user-attachments/assets/c30ce49e-7d4b-4785-b5af-c240fea6fc0d)


# IntelligentCage


Repo of the intelligent cage project, created July 12 2023, Nathan Bérubé



## CAD files on fusion 360:

Mireille has access to all the CAD files of the different components. Ask her to be added to the Fusion360 team.

There are also two .stl [files](CAD) of the load cell platforms as example for 3D printing. It is important to print with a high infill density to maximize the stifness of the platforms to reduce creep.



## Arduino LoadCell library and LoadCellController library:

### Documentation
They are based on the following library that can be found [here](https://github.com/bogde/HX711)

There is a pdf of the documentation in the repo: [Documentation.pdf](Loadcell/ArduinoLibraries/Documentation.pdf)

This pdf was generated from the latex folder with Doxygen: [latex](Loadcell/ArduinoLibraries/latex)


There is also an html file that can be opened on your web browser to have a web page of the documentation
Copy the repo and then open the [index.html](Loadcell/ArduinoLibraries/html/index.html) file.

### How to install the libraries

Copy the repo on your computer and indentify the [LoadCellLibrary](Loadcell/ArduinoLibraries/LoadCellLibrary) and the [LoadCellControllerLibrary](Loadcell/ArduinoLibraries/LoadCellControllerLibrary). Move these folders to your Arduino/libraries folder on your computer.


You can now use the libraries in your skectch by including them this way.
```c++
#include "LoadCell.h"
#include "LoadCellController.h"
```

### Sketch examples
Many useful sketches are saved in this folder. Find it in Loadcell > ArduinoLibraries > SketchExamples. 


## Load cell drift test
Many tests were done to characterize the drift of a load cell. All the Arduino [sketches](Loadcell/LoadcellDriftTest/ArduinoSketch) used for different tests are listed by date in the repo. The small data files are also [here](Loadcell/LoadcellDriftTest/Data).


## Lab notes:
Lot of tests were done to characterize the drift behavior of a loadcell. Every test is detailled in the following document along with
with the main conclusions about it.

Document: [Lab notes](https://www.overleaf.com/read/vvxvjbdjmgmg)


## Capacitive sensor:
An Arduino sketch [example](CapacitiveSensor/CapacitiveSensorSketchExample/CapacitiveSensorSketchExample.ino) is available to get started

A short [guide](CapacitiveSensor/GuideCapacitiveSensorWithArduino.pdf) is also available to understand everything about capacitive sensors. It also contains all to links to the Arduino library for installation and the documentation.

## Code for a quick start with one loadcell
```
#include "LoadCell.h"
#include "LoadCellController.h"
#include <SPI.h>

LoadCell loadcell; // name the loadcell
LoadCellController loadcell_controller; // create the loadcell controller, one per cage with many loadcells 

void setup() {
  // 1. Set the serial communication.
  // 2. Add the loadcells individually.
  // 3. Easy start 
  // possibility to saves variables on the EEPROM. The loadcell #1 always has the slot #1 on the EEPROM. 

Serial.begin(9600);
  loadcell_controller.add_loadcell(loadcell); // add individual loadcells. One add_loadcell and easy_start per loadcell
  soleil_controller.easy_start_with_params(
                                    1,         // loadcell_number
                                    8,         // dout pin
                                    9,         // sck pin
                                    true,      // calibrate offset
                                    true,      // calibrate scale
                                    false,     // read offset to memory
                                    false,     // read scale to memory
                                    true,      // save offset to memory
                                    true,      // save scale to memory
                                    0,         // tare offset manually, no specification if 0
                                    0,         // scale coeff manually, no specification if 0
                                    128        // gain, don't change! 
                                    );                                   
}

void loop() {
  loadcell_controller.wait_ready_timeout(1, 1000); // reads if something is measured by the loadcell. If not, takes a measure every 1 second (1000 ms). 1 = loadcell number
  float reading = loadcell_controller.get_weight(1); // 1 = loadcell number
  Serial.println(reading);
}
```

## How to generate documentation with Doxygen

First of all, you need to download Doxygen and LaTex on your computer.

After that, you need to open a terminal where your code is stored to generate a Doxyfile. Run the following command
```console
doxygen -g
```
Next, you can open the generated Doxyfile in your folder to change the RECURSIVE parameter. Set it to YES. This way dpxygen will search are code files that are inside the current repository to generate your documentation.
Alternatively, you can also specify sub-folders path at the INPUT parameter in the Doxyfile.

Now, with the Doxyfile, you can generate html and latex folders with the following command
```console
doxygen Doxyfile
```
You will see the html and latex folders appear in the folder where the Doxyfile is. If you open the index.html file in the html folder, you'll be accessible to see the documentation on your web browser.
You can also generate a pdf of the documentation using the latex folder. Open a new terminal in this folder and run the following command
```console
pdflatex refman.tex
```
This will generate a file named refman.pdf in the latex folder, it is the documentation. You can rename and move this file.
