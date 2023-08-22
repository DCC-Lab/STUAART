# IntelligentCage

Repo of the intelligent cage project, created July 12 2023, Nathan Bérubé



## CAD files on fusion 360:

Mireille has access to all the CAD files of the different components. Ask her to be added to the Fusion360 team.

Thereb are also two .stl [files]()



## Arduino LoadCell library and LoadCellController library:

### Documentation

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


## Load cell drift test
Many tests were done to characterize the drift of a load cell. All the Arduino [sketches](Loadcell/LoadcellDriftTest/ArduinoSketch) used for different tests are listed by date in the repo. The small data files are also [here](Loadcell/LoadcellDriftTest/Data).


## Lab notes:
Lot of tests were done to characterize the drift behavior of a loadcell. Every test is detailled in the following document along with
with the main conclusions about it.

Document: [Lab notes](https://www.overleaf.com/read/vvxvjbdjmgmg)


## Capacitive sensor:
An Arduino sketch [example](CapacitiveSensor/CapacitiveSensorSketchExample/CapacitiveSensorSketchExample.ino) is available to get started

A short [guide](CapacitiveSensor/GuideCapacitiveSensorWithArduino.pdf) is also available to understand everything about capacitive sensors. It also contains all to links to the Arduino library for installation and the documentation.
