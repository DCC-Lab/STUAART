# Drift correction sketch

This Arduino sketch implements the drift correction strategy that consists of taking weight measurements 
when the scale is empty as the new reference/offset. This strategy is detailled in [Lab notes](https://www.overleaf.com/read/vvxvjbdjmgmg)
at the end of the document.

In this sketch, the start-up is not done with easy_start_with_params(). Functions that allow the taring of all the LoadCells are used.

Also, the controller.get_weight_with_auto_recalibration() function is used to perform a reading.

The code allows to switch from automatic start-up to manual calibration start-up (see sketch for more details)
