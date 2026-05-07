# STUAART Firmware

Production firmware for the STUAART automated mouse weighing system. Targets the DFRobot FireBeetle ESP32 (DFR0478) with three HX711 load cell amplifiers, an SD card, and a PCF8523 RTC.

## Repository layout

```
Firmware/
└── STUAART/
    ├── STUAART.ino              Main sketch
    ├── LoadCell.{h,cpp}         Custom: extends bogde/HX711
    └── LoadCellController.{h,cpp}  Custom: manages multiple LoadCells
```

The custom `LoadCell` and `LoadCellController` files live next to the sketch on purpose: Arduino IDE compiles them automatically as part of the sketch, no library installation needed for the custom code. They are the heart of the firmware and version-controlled here.

## Required third-party libraries

Install these via Arduino IDE Library Manager (Sketch -> Include Library -> Manage Libraries):

| Library | Author | Tested version |
|---|---|---|
| HX711 | Bogdan Necula (bogde) | 0.7.5 |
| RTClib | Adafruit | 2.1.4 |
| ArduinoJson | Benoit Blanchon | 7.0.4 |

`RTClib` will pull `Adafruit BusIO` as a dependency.

## Board setup

1. Install Arduino IDE 2.x or `arduino-cli`.
2. Add the ESP32 boards URL in Preferences:
   `https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json`
3. Boards Manager: install `esp32 by Espressif Systems` (tested with 2.0.x and 3.0.x).
4. Select board: `FireBeetle-ESP32` (or `DFRobot FireBeetle 2 ESP32-E` depending on your hardware).

## Compile and upload

### Arduino IDE
1. Open `Firmware/STUAART/STUAART.ino`.
2. Tools -> Port: pick the USB-serial device (typically `/dev/cu.usbserial-XXX` on macOS).
3. Sketch -> Verify, then Upload.

### arduino-cli
From the repo root:
```sh
arduino-cli compile --fqbn esp32:esp32:firebeetle32 Firmware/STUAART
arduino-cli upload  --fqbn esp32:esp32:firebeetle32 -p /dev/cu.usbserial-10 Firmware/STUAART
```

## Wiring (FireBeetle V1, PCB V2 in production)

| Function | FireBeetle silkscreen | GPIO |
|---|---|---|
| Cell 1 DOUT | D5 | 9 (currently flash-pin, source of corruption: see issue) |
| Cell 1 SCK | LRCK (shared) | 17 |
| Cell 2 DOUT | D5 alias on PCB | 27 |
| Cell 2 SCK | LRCK (shared) | 17 |
| Cell 3 DOUT | D8 | 5 |
| Cell 3 SCK | LRCK (shared) | 17 |
| SD card SS | D8 alias | 5 |
| RTC | I2C | SDA=21, SCL=22 |
| Mode switch | D7 | 13 |
| Status LEDs | D6/D9/A4/D8 | 10/2/15/5 |

The "GPIO 9 = flash" issue on cell 1 is the root cause of corrupted readings (raw == 0xFFFFFF returned as -160.68 g). A defensive software patch in `LoadCell.cpp` rejects this signature, but the long-term fix is to reroute that DOUT to GPIO 25 or 26 (silkscreen D2 or D3).
