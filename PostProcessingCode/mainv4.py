# create a python file named path.py in the same directory containing the file (on the same level)
# add this file to gitignore, only you will see it
# create a variable named your_path = "your path to the data" (string type)
# this variable is imported in this file
# this way, everyone can run this code even if all paths to the data are different
from my_module_paths import my_path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from CageClass import Cage
from datetime import datetime
from scipy.signal import find_peaks

# color_data1 = "b"
# color_data2 = "r"
# color_data3 = "g"

# save_figure = False

delay_video_weight = 179

data = np.array(pd.read_csv(my_path))
directory = "/Users/valeriepineaunoel/Documents/PhD/Results/STUAART/20251016-TestSTUAARTOneMouse80Hz/"
filename = "2025.10.16-RawWeightData.csv"
cage = Cage(directory=directory, filename=filename, number_of_scales=3, real_data=np.array([0, 20]))
# cage.plot_data_per_scale()
# cage.compute_individual_scale_information(first_day=True, produce_graph=True)

# HANGING
cage.compute_hanging(first_day=True, produce_graph=True)

# LOCATION
# directory_ground_truth_location = "/Users/valeriepineaunoel/Documents/PhD/Results/STUAART/20251016-TestSTUAARTOneMouse80Hz/20251016-BehaviourDataAfterWatching/"
# filenames_ground_truth_location = ["On scale 1-Table 1.csv", "On scale 2-Table 1.csv", "On scale 3-Table 1.csv", "On scales 1 and 2-Table 1.csv", "On scales 2 and 3-Table 1.csv"]
# cage.compute_location_on_scale(first_day=True, produce_graph=True, is_saved=True)
# cage.compute_location_on_scale_accuracy(is_saved=True, directory_ground_truth=directory_ground_truth_location, filenames=filenames_ground_truth_location, delay_in_seconds=delay_video_weight, evaluate_only_between_these_hours=None)


# GROOMING
# # Look at 2-second samples of weight data per behaviour type PER SCALE and produce PCA. 
# directory_behaviour = "/Users/valeriepineaunoel/Documents/PhD/Results/STUAART/20251016-TestSTUAARTOneMouse80Hz/20251016-BehaviourDataAfterWatching/Behaviour/"
# two_second_data, on_scale, targets, labels = cage.produce_behaviour_dataset_per_scale(directory=directory_behaviour, delay_in_seconds=delay_video_weight)
# cage.pca(dataset=two_second_data, number_of_PCs=10, targets=targets, labels=labels, on_scale=on_scale, PCs_to_plot=[1,2,3], label_per_scale=False)

# # Look at 2-second samples of weight data per behaviour type, overall weight of the system, and produce PCA. 
# two_second_data, targets, labels = cage.produce_behaviour_dataset(directory=directory_behaviour, delay_in_seconds=delay_video_weight)
# cage.pca(dataset=two_second_data, number_of_PCs=10, targets=targets, labels=labels, on_scale=on_scale, label_per_scale=False)

# two_second_data, on_scale, targets, labels = cage.produce_behaviour_dataset_per_scale(directory=directory_behaviour, delay_in_seconds=delay_video_weight)
# cage.fft_behaviour(dataset=two_second_data, labels=labels, plot=True)


# # 2025.10.24
# # PLOT LES BEHAVIOURS FOR VISUALISATION
# print(two_second_data, type(two_second_data), two_second_data.shape)

# fig, axs = plt.subplots(nrows=np.unique(labels).shape[0], figsize=(10,10)) # si 4 behaviours, alors 4 subplots
# x = range(0, 380, 1)
# i = 0

# for label in np.unique(labels):
# 	indices_of_behaviour = np.where(label == labels)[0]

# 	for j in range(indices_of_behaviour.shape[0]):
# 		axs[i].plot(x, two_second_data[indices_of_behaviour[j], :], alpha=0.7)

# 	axs[i].set_title(str(label), fontsize=16)
# 	axs[i].set_ylabel("Weight [g]", fontsize=12)
# 	axs[i].set_xlabel("Timestamps (380 data points = 4 seconds)", fontsize=10)

# 	i += 1

# fig.tight_layout()
# plt.savefig("/Users/valeriepineaunoel/Documents/PhD/Results/STUAART/20251016-TestSTUAARTOneMouse80Hz/Figures/4second-behaviours-raw.png", format="png")
# plt.show()


# # PLOT ALL GROOMING FOR VISUALISATION. ISOLATE THE ONES THAT ARE CLEAN. 
# indices_of_grooming = np.where(labels == "Grooming")[0]
# fig = plt.figure(figsize=(13, 4)) # plot all grooming, one per plot
# x = range(0, 190, 1)
# i = 0

# for j in indices_of_grooming:
# 	plt.plot(x, two_second_data[j, :], label="Index : " + str(j))
# 	plt.ylabel("Weight [g]", fontsize=10)
# 	plt.xlabel("Timestamps (190 data points = 2 seconds)", fontsize=10)
# 	plt.savefig("/Users/valeriepineaunoel/Documents/PhD/Results/STUAART/20251016-TestSTUAARTOneMouse80Hz/Figures/RawGrooming/Individual-2second-grooming-raw-index" + str(j) + ".png", format="png")
# 	plt.close()
# 	i += 1

# # THESE ARE THE ONES THAT I FOUND VISUALLY CLEAN SO I'M ONLY GOING TO FFT THESE TIME SERIES
# indices_clean_grooming = [58, 59, 65, 66, 70, 77, 80, 81, 88, 93, 100, 103]
# weight_data_of_clean_grooming = two_second_data[indices_clean_grooming, :]
# fft_of_clean_grooming = np.fft.fft(weight_data_of_clean_grooming)
# x = range(0, 190, 1)

# fig = plt.figure(figsize=(15, 4))

# for i in range(len(indices_clean_grooming)):
# 	plt.plot(x, fft_of_clean_grooming[i], label="Index : " + str(indices_clean_grooming[i]), alpha=0.7)

# plt.ylim(-50, 50)
# plt.ylabel("Amplitude", fontsize=12)
# plt.xlabel("Timestamp (190 data points = 2 seconds)", fontsize=12)
# plt.savefig("/Users/valeriepineaunoel/Documents/PhD/Results/STUAART/20251016-TestSTUAARTOneMouse80Hz/Figures/RawGrooming/FFT_of_clean_grooming.png", format="png")
# plt.show()


# # PLOT ONLY THE CLEAN GROOMING EVENTS FOR VISUALISATION
# fig = plt.figure(figsize=(15, 4))

# for i in indices_clean_grooming:
# 	plt.plot(x, two_second_data[i], label="Index : " + str(i), alpha=0.7)

# plt.ylabel("Weight [g]", fontsize=12)
# plt.xlabel("Timestamp (190 data points = 2 seconds)", fontsize=12)
# plt.savefig("/Users/valeriepineaunoel/Documents/PhD/Results/STUAART/20251016-TestSTUAARTOneMouse80Hz/Figures/RawGrooming/Weight_data_of_clean_2second_grooming.png", format="png")
# plt.show()


# # FFT OF ALL 2-SECOND GROOMING EVENTS FOR VISUALISATION 
# indices_of_grooming = np.where(labels == "Grooming")[0]
# data_of_grooming = two_second_data[indices_of_grooming, :]
# fft_of_grooming = np.fft.fft(data_of_grooming)
# x = range(0, 190, 1)

# fig = plt.figure(figsize=(15, 4))

# for i in range(indices_of_grooming.shape[0]):
# 	plt.plot(x, fft_of_grooming[i], alpha=0.7)

# plt.ylim(-50, 50)
# plt.ylabel("Amplitude", fontsize=12)
# plt.xlabel("Timestamp (190 data points = 2 seconds)", fontsize=12)
# plt.savefig("/Users/valeriepineaunoel/Documents/PhD/Results/STUAART/20251016-TestSTUAARTOneMouse80Hz/Figures/GroomingInvestiguation/FTT_all_grooming.png", format="png")
# plt.show()




















