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

color_data1 = "b"
color_data2 = "r"
color_data3 = "g"

save_figure = False

data = np.array(pd.read_csv(your_path))

# -----------
# Individual scales

time = data[:,0]/(1000 * 60) # time in min
data1 = data[:,1] # weight measurements scale 1, 300g
data2 = data[:,2] # weight measurements scale 1, 100g
data3 = data[:,3] # weight measurements scale 1, 100g

# real_data = np.array([[time[0], time[-1]],[29.5, 29.5]]) # measured weight of the mouse

# This is used in case we want to amplify the drift for testing
# data1[3000:] += 3000
# data1[5000:] += 3000

data1 = Data(data1, time)
data2 = Data(data2, time)
data3 = Data(data3, time)

# Step 1 : Clean the signal and ready the data for the analysis
# set baseline, correct for shifts of weight over time, remove outliers with a simple threshold. 

# if the measurements are higher than the threshold [g], for sure they are outliers
threshold1 = [-10, 40]
threshold2 = [-10, 40]
threshold3 = [-10, 40]

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

# data1.plot_signal(threshold=False, peaks=False, baseline=True, color=color_data1, is_saved=save_figure, real_data=real_data)
# data2.plot_signal(threshold=False, peaks=False, baseline=True, color=color_data2, is_saved=save_figure, real_data=real_data)
# data3.plot_signal(threshold=False, peaks=False, baseline=True, color=color_data3, is_saved=save_figure, real_data=real_data)

data1.subtract_baseline()
data2.subtract_baseline()
data3.subtract_baseline()

# Obsolete : Isolate the peaks to identify the moments where the mouse if weighted. Les entre-deux sont tannants à gérer. Revient au problème de changer le threshold parce que le poids de la souris change dans le temps. 
# data1.set_weight_threshold()
# data2.set_weight_threshold()
# data3.set_weight_threshold()

# data1.find_peak_average_values()
# data2.find_peak_average_values()
# data3.find_peak_average_values()

# data1.find_all_peaks_values()
# data2.find_all_peaks_values()
# data3.find_all_peaks_values()

# plt.plot(time, data1, color=color_data1, label="Scale 1")
# plt.plot(time, data2, color=color_data2, label="Scale 2")
# plt.plot(time, data3, color=color_data3, label="Scale 3")
# plt.xlabel("Time [min]", fontsize=16)
# plt.ylabel("Weight [g]", fontsize=16)
# plt.legend()
# plt.show()

# -------
# Cage 

data_list = [data1, data2, data3]
cage = Cage(data_list, time)


# FIND WHEN MOUSE GETS IN THE CAGE
cage.when_mouse_is_in()
index_when_mouse_is_in = np.where(cage.time == cage.time_when_mouse_is_in)[0][0]

# COMPUTE AVERAGE WEIGHT OVER TIME

# cage.compute_mean_data()

# plt.plot(cage.raw_time, cage.raw_data, color="k", label="Not filtered")
# plt.plot(cage.time, cage.data, label="Filtered")
# plt.scatter(real_data[0], real_data[1], s=100, alpha=0.7, c="y", marker="*", label="Real data")
# plt.legend()
# plt.xlabel("Time [hour]", fontsize=20)
# plt.ylabel("Weight [g]", fontsize=20)
# plt.show()


# ACCESS HANGING DATA
Hanging data from video, reference
true_hanging_time = np.array(pd.read_csv("/Users/valeriepineaunoel/Documents/PhD/Results/20240407-AcquireWeightForALongTimeNoAutotareMouse588/video3h/20240407-AcquireWeightFor3hoursMouse5883-BehaviourDataAdterWatching/Hanging.csv"))
time_hanging = true_hanging_time[:,-1]

for i in range(time_hanging.shape[0]):
	time_hanging[i] = int(time_hanging[i][:-1]) # convert str data in int data

starting_time = []
for i in range(true_hanging_time[:,0].shape[0]):
	time_hanging = datetime.strptime(true_hanging_time[i,0], '%H:%M:%S') # convert str time data to time object
	# convert time object in int. 77 seconds before the mouse is in compared to when the video started. time_mouse_in is when the weight started to be measured, mouse is in the cage.
	total_hours = (time_hanging.hour * 3600 + time_hanging.minute * 60 + time_hanging.second-77)/(60*60) # time in hours
	starting_time.append(total_hours)

ending_time = []
for i in range(true_hanging_time[:,1].shape[0]):
	time_hanging = datetime.strptime(true_hanging_time[i,1], '%H:%M:%S') # convert str time data to time object
	# convert time object in int. 77 seconds before the mouse is in compared to when the video started. time_mouse_in is when the weight started to be measured, mouse is in the cage.
	total_hours = (time_hanging.hour * 3600 + time_hanging.minute * 60 + time_hanging.second-77)/(60*60) # time in hours
	ending_time.append(total_hours)


# Fetch hanging data from weight data
cage.remove_outliers()
cage.convolution_filter_with_padding_edge(length=15)
cage.compute_hanging()

# get data only under 10 g
hanging_data = cage.data[cage.data < 10]
index_hanging_data = np.where(cage.data < 10)[0]
hanging_time = cage.time[index_hanging_data]
hanging_indicator = np.where(cage.data < 10, 1, 0) # 1 = the mouse is hanging at that time, otherwise 0
start_indices = np.where((hanging_indicator[:-1] == 0) & (hanging_indicator[1:] == 1))[0] + 1 # Find the start indices of sequences of 1s
end_indices = np.where((hanging_indicator[:-1] == 1) & (hanging_indicator[1:] == 0))[0] # Find the end indices of sequences of 1s

# remove indices that are under the index when the mouse is in 
start_indices = start_indices[start_indices > index_when_mouse_is_in]
end_indices = end_indices[end_indices > index_when_mouse_is_in]

# gets the times when the mouse starts and ends hanging
start_hanging = cage.time[start_indices]
end_hanging = cage.time[end_indices]

# compute accuracy of hanging times identification, comparing the analysis of weight data with the reference done with the video
# total time accuracy
total_time_hanging_reference = np.sum(np.subtract(ending_time, starting_time))
total_time_hanging = np.sum(np.subtract(end_hanging, start_hanging))
absolute_error = abs(total_time_hanging - total_time_hanging_reference)
relative_error = absolute_error/total_time_hanging_reference
accuracy_total_time_hanging = 100 - (relative_error*100)

# Verify in each reference hanging moments if most of it is identified 
indicator_hanging_reference = np.zeros(shape=cage.time.shape)
for i in range(len(starting_time)):
	start = starting_time[i]
	end = ending_time[i]
	result = np.where((cage.time >= start) & (cage.time <= end), 1, 0)
	indicator_hanging_reference = indicator_hanging_reference + result

compare = (hanging_indicator == 1) & (indicator_hanging_reference == 1) # verifies when both have 1 == True, otherwise False
number_of_success = np.where(compare == True)[0].shape[0]
number_of_hanging_reference = np.where(indicator_hanging_reference == 1)[0].shape[0]
accuracy_hanging_identification = number_of_success/number_of_hanging_reference*100


plt.figure(figsize=(13,7))
# fill between the moment where I know the mouse is hanging from the video
for i in range(len(starting_time)):
	if i == 0:
		plt.fill_between(cage.raw_time, np.amax(cage.raw_data), where=(cage.raw_time >= starting_time[i]) & (cage.raw_time <= ending_time[i]), color="gray", alpha=0.7, label="Hanging - Reference")
	else:
		plt.fill_between(cage.raw_time, np.amax(cage.raw_data), where=(cage.raw_time >= starting_time[i]) & (cage.raw_time <= ending_time[i]), color="gray", alpha=0.7)

# fill between the moment where the mouse is hanging from my weight data analysis
for i in range(start_hanging.shape[0]):
	if i == 0:
		plt.fill_between(cage.raw_time, np.amax(cage.raw_data), where=(cage.raw_time >= start_hanging[i]) & (cage.raw_time <= end_hanging[i]), color="red", alpha=0.7, label="Hanging - Data analysis")
	else:
		plt.fill_between(cage.raw_time, np.amax(cage.raw_data), where=(cage.raw_time >= start_hanging[i]) & (cage.raw_time <= end_hanging[i]), color="red", alpha=0.7)

plt.plot(cage.raw_time, cage.raw_data, color="k", label="Not filtered")
plt.plot(cage.time, cage.data, label="Convoluted (15)")
plt.scatter(real_data[0], real_data[1], s=100, alpha=0.7, c="y", marker="*", label="Real data")
plt.legend()
plt.title(f"Total time accuracy : {accuracy_total_time_hanging}% \n Accuracy hanging identification : {accuracy_hanging_identification}% ")
plt.show()
