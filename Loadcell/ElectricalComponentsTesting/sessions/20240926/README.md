# Smart Cage - Maxime Tousignant-Tremblay (2024/09/26)

Log file for the test session of 2024/09/26

## Objective and methods

Today's test aimed to verify the ADC's power line stability (HX711). Since an ADC's resolution depends on supply voltage, high resolution ADCs require very stable power input. As a general rule of thumb, a 12 bits ADC's supply fluctuation tolerance is around 50 mV max. Voltage variations exceeding this threshold is likely to affect the ADC's reliability. For a 24 bits ADC such as the HX711, we should expect a much lower tolerance. Power line unstabilities should produce inaccurate readings or drifts in measurements, but it's unlikely to be the cause of outliers. However, assessing supply voltage stability could help improve the overall design reliability. Note that this experiment is still made on breadboard and might not entirely reflect the circuit's behaviour on a PCB.

## Testing and results

The concerns about supply voltage stability proved to be correct. During a 60 min acquisition, many periods of random voltage fluctuations occured, way above the 50 mV limit (FOR 12 BITS ADCs, 24 bits ADC should be even less!!!). Since the events were captured using an oscilloscope, I wasn't able to record enough data to produce multiple plots of different moments. As a reminder though, this problem is unlikely to be the cause of outliers. Therefore, power line unstability is A problem, not THE problem. Simple solutions for this could be : adding decoupling capacitors close to the HX711 supply input pin, adding a ferite bead in series to filter out high frequency noise and/or adding a 5V voltage regulator (a low dropout version would be best, but not necessary) to the circuit.
