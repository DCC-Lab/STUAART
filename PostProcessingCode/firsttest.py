# create a python file named path.py in the same directory containing the file (on the same level)
# add this file to gitignore, only you will see it
# create a variable named your_path = "your path to the data" (string type)
# this variable is imported in this file
# this way, everyone can run this code even if all paths to the data are different
from path import your_path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from DataClass import Data


data = np.array(pd.read_csv(your_path))

time = data[:,0]/(1000 * 60 * 60)
data1 = data[:,1]
data2 = data[:,2]
data3 = data[:,3]

data1 = Data(data1, time)
data2 = Data(data2, time)
data3 = Data(data3, time)

threshold1 = 2 * 10**5
threshold2 = 4 * 10**5
threshold3 = 4 * 10**5

data1.set_outliers_threshold(threshold1)
data2.set_outliers_threshold(threshold2)
data3.set_outliers_threshold(threshold3)

data1.center_data_on_zero()
data2.center_data_on_zero()
data3.center_data_on_zero()

data1.remove_outliers()
data2.remove_outliers()
data3.remove_outliers()

data1.set_weight_threshold()
data2.set_weight_threshold()
data3.set_weight_threshold()

data1.find_peak_average_values()
data2.find_peak_average_values()
data3.find_peak_average_values()

data1.find_all_peaks_values()
data2.find_all_peaks_values()
data3.find_all_peaks_values()




data1.plot_signal()
data1.plot_peak_averages()
data1.plot_all_peaks()

# data2.plot_signal()
# data2.plot_peaks_average()

# data3.plot_signal()
# data3.plot_peaks_average()

