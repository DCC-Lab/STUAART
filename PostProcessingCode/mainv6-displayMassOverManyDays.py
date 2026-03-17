import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from DataClass import Data
from CageClass import Cage
from datetime import datetime
from scipy.signal import find_peaks

def identify_buffer_flushes(time, data, remove=False):
	indices_of_buffer_flushes = np.where(time == "--")[0]
	
	dt = np.diff(time[indices_of_buffer_flushes-1].astype(int))
	mean_dt = np.mean(dt)
	stdev_dt = np.std(dt)

	print(f"Mean time between buffer flushes : {mean_dt/1000:.4f} +- {stdev_dt/1000:.4f} seconds.")

	indices_before_and_after_flushes = np.sort(np.concatenate((time[indices_of_buffer_flushes-1].astype(int), time[indices_of_buffer_flushes+1].astype(int))))
	indices_before_and_after_flushes_reshaped = np.reshape(indices_before_and_after_flushes, (-1, 2))
	dt_flush = np.diff(indices_before_and_after_flushes_reshaped, axis=1)
	mean_dt_flush = np.mean(dt_flush)
	stdev_dt_flush = np.std(dt_flush)

	print(f"Mean time to flush buffer in SD card : {mean_dt_flush/1000:.4f} +- {stdev_dt_flush/1000:.4f} seconds.")

	if remove:
		weight_data_without_flushes = np.delete(data, indices_of_buffer_flushes, axis=0)
		time_without_flushes = np.delete(time, indices_of_buffer_flushes)
		return time_without_flushes.astype(float), weight_data_without_flushes.astype(float)
	else:
		return time, data


color_data1 = "b"
color_data2 = "r"
color_data3 = "g"

save_figure = True
data = np.array(pd.read_csv('/Users/valeriepineaunoel/Library/Mobile Documents/com~apple~CloudDocs/Documents/PhD/Results/STUAART/20260310-3MiceIn3STUAARTsFor4days/green-172.16.6.9/2026.03.10.csv'))
time = data[:, 0]
mass_data = data[:, 1:]

# Remove bluffer flushes in data
time, mass_data = identify_buffer_flushes(time=time, data=mass_data, remove=True)

# -----------
# Individual scales

time = time/(1000 * 60 * 60) # time in hours
data1 = mass_data[:,0] # weight measurements scale 1, 300g
data2 = mass_data[:,1] # weight measurements scale 1, 100g
data3 = mass_data[:,2] # weight measurements scale 1, 100g

index_hour1 = np.where(time > 1)[0][0]
index_30min = np.where(time > 0.5)[0][0]

# real_data = np.array([[time[0]],[34.1]]) # measured weight of the mouse
real_data = None

# if the measurements are higher than the threshold [g], for sure they are outliers
threshold1 = [-10, 40]
threshold2 = [-10, 40]
threshold3 = [-10, 40]

data1 = Data(data1[:index_30min], time[:index_30min])
data2 = Data(data2[:index_30min], time[:index_30min])
data3 = Data(data3[:index_30min], time[:index_30min])

print("DATA", data1, data1.shape, data1.dtype, type(data1))

data1.plot_signal(threshold=False, peaks=False, baseline=False, color=color_data1, is_saved=save_figure, real_data=real_data)
data2.plot_signal(threshold=False, peaks=False, baseline=False, color=color_data2, is_saved=save_figure, real_data=real_data)
data3.plot_signal(threshold=False, peaks=False, baseline=False, color=color_data3, is_saved=save_figure, real_data=real_data)

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

data1.plot_signal(threshold=False, peaks=False, baseline=False, color=color_data1, is_saved=save_figure, real_data=real_data)
data2.plot_signal(threshold=False, peaks=False, baseline=False, color=color_data2, is_saved=save_figure, real_data=real_data)
data3.plot_signal(threshold=False, peaks=False, baseline=False, color=color_data3, is_saved=save_figure, real_data=real_data)

