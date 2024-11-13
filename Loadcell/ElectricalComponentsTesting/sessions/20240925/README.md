# Smart Cage - Maxime Tousignant-Tremblay (2024/09/25)

Log file for the test session of 2024/09/25

## Objective and methods

Today's test aimed to isolate the source(s) of outliers in weight data. Indeed, the original electronic setup (before any component testing began) yields significant weigth value spikes at a rate of about 16 outliers/h (based on Valerie's graphs in the "SmartCage-AllDataUntilNow" presentation). Using the same simplified electronic setup as last time (see 20240918/README.md for more info), this session will attempt to confirm whether or not the loadcells (sensor, not HX711) are the issue. The HX711 module is an instrumentation amplifier combined with an ADC, which means that it amplifies the voltage difference between two input signals (+ and -). If both inputs are tied to GND, then the difference should be almost 0 V so the weight measurements (calculated based on the voltage difference) should also be almost 0 g. In that case, if outliers are still there, then it means the problem is not the loadcells. The remaining source of issues would likely be : bad HX711 module, microcontroller board problems or SPI communication issues.

## Testing and results

For more accurate outliers average, the same experiment as in 20240918 was conducted. However, data was recorded for 60 min instead of 15 min. With an Arduino Uno R3, an HX711 module and a single loadcell, the outlier rate was 3 outliers/h. With both inputs of the HX711 module tied to GND, an outlier rate of 5 outliers/h was recorded. Therefore, the problem is not the loadcell sensors. Since the spikes were way off scale, both plots as a "Crop" version for easier spike rate reading.
