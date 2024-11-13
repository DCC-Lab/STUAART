# Smart Cage - Maxime Tousignant-Tremblay

On this project, mass variation < 0.1 g are considered negligeable.

## Brainstorming

Possible deffective components in the system, check the following components:

- Microcontroller board
- Load cell
- HX711 module
- SD card module

A first look at the electronic schematic (latest version designed on 2024/06 by Ludovic Gagnon) reveals that the SD card and HX711 modules, both communicating through SPI protocol, are not using the same clock on the microcontroller board. Normally, SPI communication devices should all be connected to a dedicated SPI clock pin on boards, usually called SCK. In this case, the SD card module use the SCK pin and the HX711 modules are using LRCK clock pin (I2S protocol's dedicated clock pin). Original designers logs suggested that using only the SCK pin caused issues, which were solved by using the LRCK pin. Further investigation is required.

### Microcontroller board

Generic Arduino boards (different brands) are known to produce many unexpected issues over time. A simple, yet effective solution is to use original Arduino boards. From now on, all tests are going to be using an original arduino board. The FireBeetle ESP32 board, chosen for it's WiFi capabilities and low cost, will be replace by the Arduino Nano ESP32. Both boards have the same specs and characteristics, suggesting that the FireBeetle might be a generic copy of the Arduino Nano ESP32.

### Load cell & HX711 modules

For the time being, individual tests are going to be conduct to confirm that they are working as they should. If experiments shows that one of these components might be faulty, new ones will be use. If it becomes clear that the overall design quality might be an issue, new candidates will be suggested.

### PCB design & components placement

The PCB design will have to be double check for common sources of issues such has ground, trace width, trace spacing, via hole sizes, etc. The latest PCB design does not have GND connected polygon pours on both sides. Since this PCB is fully digital, there are no critical needs to spend time on decoupling, trace length and analog filtering. Analog boards are incredibly sensitive and attention to details is mandatory. This is obviously not the case here. There is however one analog part on this circuit that might be worth improving **if time allows it** : the connection between the load cell and the HX711 modules. These cables carry analog signals sensitive to cable length. They are small in diameter and lightly connected. Methods to reduce cable length, reduce cable movements during cage handling/operation and improve connection strength with the PCB could help making a more robust system.

### Dignostic steps & procedure

The diagnostic of hardware issues requires individual testing of each subsystem, starting from the most basic elements. The details, data and results of each test sessions are in folders, sorted by date, in the "./Sessions" folder.

### PlateformIO

From now, Arduino sketches are going to be written and uploaded via VSCode PlateformIO extension (free). This will remove the need to use Arduino IDE. The PlateformIO environnement for this project is located in the "./SmartCage_PlateformIO" folder. A more detailed README file is located in this folder.
