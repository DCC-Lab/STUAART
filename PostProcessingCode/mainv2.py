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
from CageClass import Cage
from datetime import datetime
from scipy.signal import find_peaks

color_data1 = "b"
color_data2 = "r"
color_data3 = "g"

save_figure = False

data = np.array(pd.read_csv(your_path))

# -----------
# Individual scales

time = data[:,0]/(1000 * 60 * 60) # time in hours
data1 = data[:,1] # weight measurements scale 1, 300g
data2 = data[:,2] # weight measurements scale 1, 100g
data3 = data[:,3] # weight measurements scale 1, 100g

real_data = np.array([[time[0]],[34.1]]) # measured weight of the mouse

# if the measurements are higher than the threshold [g], for sure they are outliers
threshold1 = [-10, 40]
threshold2 = [-10, 40]
threshold3 = [-10, 40]

# This is used in case we want to amplify the drift for testing
# data1[3000:] += 3000
# data1[5000:] += 3000

data1 = Data(data1, time)
data2 = Data(data2, time)
data3 = Data(data3, time)

print("DATA", data1, data1.shape, data1.dtype, type(data1))

# data1.plot_signal(threshold=False, peaks=False, baseline=False, color=color_data1, is_saved=save_figure, real_data=real_data)
# data2.plot_signal(threshold=False, peaks=False, baseline=False, color=color_data2, is_saved=save_figure, real_data=real_data)
# data3.plot_signal(threshold=False, peaks=False, baseline=False, color=color_data3, is_saved=save_figure, real_data=real_data)

# Step 1 : Clean the signal and ready the data for the analysis
# set baseline, correct for shifts of weight over time, remove outliers with a simple threshold. 

data1.set_outliers_threshold(threshold1)
data2.set_outliers_threshold(threshold2)
data3.set_outliers_threshold(threshold3)

data1.shift_data_to_zero()
data2.shift_data_to_zero()
data3.shift_data_to_zero()

data1.remove_outliers()
data2.remove_outliers()
data3.remove_outliers()

data1.find_baseline()
data2.find_baseline()
data3.find_baseline()

data1.subtract_baseline()
data2.subtract_baseline()
data3.subtract_baseline()

print("ALLO")

# data1.plot_signal(threshold=False, peaks=False, baseline=True, color=color_data1, is_saved=save_figure, real_data=real_data)
# data2.plot_signal(threshold=False, peaks=False, baseline=True, color=color_data2, is_saved=save_figure, real_data=real_data)
# data3.plot_signal(threshold=False, peaks=False, baseline=True, color=color_data3, is_saved=save_figure, real_data=real_data)


# -------
# Cage 

# data_list = [data1, data2, data3]
# cage = Cage(data_list, time)


# FIND WHEN MOUSE GETS IN THE CAGE
# cage.when_mouse_is_in()
# index_when_mouse_is_in = np.where(cage.time == cage.time_when_mouse_is_in)[0][0]

# COMPUTE AVERAGE WEIGHT OVER TIME
# cage.remove_outliers()

# plt.plot(cage.raw_time, cage.raw_data, color="k", label="Not filtered")
# plt.plot(cage.time, cage.data, c="g", linewidth=4, alpha=0.6, label="Outliers removed")
# cage.reset_data()
# cage.compute_mean_data()
# plt.plot(cage.time, cage.data, c="b", linewidth=4, alpha=0.6, label="Filtered")
# plt.scatter(real_data[0], real_data[1], s=100, alpha=0.7, c="y", marker="*", label="Real data")
# plt.legend()
# plt.xlabel("Time [hour]", fontsize=20)
# plt.ylabel("Weight [g]", fontsize=20)
# plt.show()