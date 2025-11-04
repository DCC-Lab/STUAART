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
from sklearn.decomposition import FastICA
from sklearn.cluster import HDBSCAN
from sklearn.metrics import adjusted_rand_score
import matplotlib.cm as cm

# color_data1 = "b"
# color_data2 = "r"
# color_data3 = "g"

# save_figure = False

delay_video_weight = -25

data = np.array(pd.read_csv(my_path))
directory = "/Users/valeriepineaunoel/Documents/PhD/Results/STUAART/20251028-TestSTUAARTOneMouse80Hz2/"
filename = "2025.10.28-RawWeightData-80Hz.csv"
cage = Cage(directory=directory, filename=filename, number_of_scales=3, real_data=np.array([0, 22]))
# cage.plot_data_per_scale()
# cage.compute_individual_scale_information(first_day=True, produce_graph=True)

# HANGING
# cage.compute_hanging(first_day=True, produce_graph=True)

# LOCATION
# directory_ground_truth_location = "/Users/valeriepineaunoel/Documents/PhD/Results/STUAART/20251028-TestSTUAARTOneMouse80Hz2/20251028-BehaviourDataAfterWatching/"
# filenames_ground_truth_location = ["On scale 1-Table 1.csv", "On scale 2-Table 1.csv", "On scale 3-Table 1.csv", "On scales 1 and 2-Table 1.csv", "On scales 2 and 3-Table 1.csv"]
# cage.compute_location_on_scale(first_day=True, produce_graph=True, is_saved=True)
# cage.compute_location_on_scale_accuracy(is_saved=True, directory_ground_truth=directory_ground_truth_location, filenames=filenames_ground_truth_location, delay_in_seconds=delay_video_weight, evaluate_only_between_these_hours=None)


# GROOMING
# # Look at 2-second samples of weight data per behaviour type PER SCALE and produce PCA. 
directory_behaviour = "/Users/valeriepineaunoel/Documents/PhD/Results/STUAART/20251028-TestSTUAARTOneMouse80Hz2/20251028-BehaviourDataAfterWatching/Behaviour/"
# two_second_data, on_scale, targets, labels = cage.produce_behaviour_dataset_per_scale(directory=directory_behaviour, delay_in_seconds=delay_video_weight)
# cage.pca(dataset=two_second_data, number_of_PCs=10, targets=targets, labels=labels, on_scale=on_scale, PCs_to_plot=[1,2,3], label_per_scale=False)

# # Look at 2-second samples of weight data per behaviour type, overall weight of the system, and produce PCA. 
# two_second_data, targets, labels = cage.produce_behaviour_dataset(directory=directory_behaviour, delay_in_seconds=delay_video_weight)
# cage.pca(dataset=two_second_data, number_of_PCs=10, targets=targets, labels=labels, on_scale=on_scale, label_per_scale=False)

two_second_data, on_scale, targets, labels = cage.produce_behaviour_dataset_per_scale(directory=directory_behaviour, delay_in_seconds=delay_video_weight)
all_frequencies, all_amplitudes = cage.fft_behaviour(dataset=two_second_data, labels=labels, plot=True)


# # 2025.10.24
# # PLOT LES BEHAVIOURS FOR VISUALISATION
# print(two_second_data, type(two_second_data), two_second_data.shape)

# fig, axs = plt.subplots(nrows=np.unique(labels).shape[0], figsize=(10,10)) # si 4 behaviours, alors 4 subplots
# x = range(0, 190, 1)
# i = 0

# for label in np.unique(labels):
# 	indices_of_behaviour = np.where(label == labels)[0]

# 	for j in range(indices_of_behaviour.shape[0]):
# 		axs[i].plot(x, two_second_data[indices_of_behaviour[j], :], alpha=0.7)

# 	axs[i].set_title(str(label), fontsize=16)
# 	axs[i].set_ylabel("Weight [g]", fontsize=12)
# 	axs[i].set_xlabel("Timestamps (190 data points = 2 seconds)", fontsize=10)
# 	axs[i].set_ylim(bottom=0, top=40)

# 	i += 1

# fig.tight_layout()
# plt.savefig("/Users/valeriepineaunoel/Documents/PhD/Results/STUAART/20251028-TestSTUAARTOneMouse80Hz2/Figures/2second-behaviours-raw.png", format="png")
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
# x = np.arange(0, fft_of_clean_grooming.shape[1])/80

# fig = plt.figure(figsize=(15, 4))

# for i in range(len(indices_clean_grooming)):
# 	freqs = np.fft.fftfreq(fft_of_clean_grooming[i].shape[0], d=x[1]-x[0])
# 	plt.plot(freqs[:len(freqs)//2], np.abs(fft_of_clean_grooming[i])[:len(freqs)//2], label="Index : " + str(indices_clean_grooming[i]), alpha=0.7)

# plt.ylim(0, 200)
# plt.ylabel("Amplitude", fontsize=12)
# plt.xlabel("Frequency [Hz]", fontsize=12)
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
# x = np.arange(0, fft_of_grooming.shape[1])/80

# fig = plt.figure(figsize=(15, 4))

# for i in range(len(indices_of_grooming)):
# 	freqs = np.fft.fftfreq(fft_of_grooming[i].shape[0], d=x[1]-x[0])
# 	plt.plot(freqs[:len(freqs)//2], np.abs(fft_of_grooming[i])[:len(freqs)//2], label="Index : " + str(indices_of_grooming[i]), alpha=0.7)

# plt.ylim(0, 200)
# plt.ylabel("Amplitude", fontsize=12)
# plt.xlabel("Timestamp (190 data points = 2 seconds)", fontsize=12)
# plt.savefig("/Users/valeriepineaunoel/Documents/PhD/Results/STUAART/20251016-TestSTUAARTOneMouse80Hz/Figures/GroomingInvestiguation/FTT_all_grooming.png", format="png")
# plt.show()


# # 2025.10.31 
# # I AM TRYING HERE TO IDENTIFY WHERE THE MOUSE IS GROOMING FOR A LONG TIME. 800 DATA POINTS = 10 SECONDS
# cage.retreive_indicator_behaviour_data_per_scale(directory=directory_behaviour, delay_in_seconds=delay_video_weight)

# # # The 3rd scale is where the mouse groomed the most. I'm going to isolate 10-second grooming events. 
# indicator_behaviour_scale = cage.behaviour_indicator_per_scale["Grooming"][2]
# diff = np.diff(np.concatenate(([0], indicator_behaviour_scale, [0])))
# starts = np.where(diff == 1)[0]
# ends = np.where(diff == -1)[0]
# lengths = ends - starts
# mask = lengths >= 1600 # 800 points = approximately 10 seconds
# runs_exact_x = np.array(list(zip(starts[mask], ends[mask]))) # here I have the start and end elements of the grooming events 

# data = np.array(cage.raw_data_per_scale)

# figure, axs = plt.subplots(2, 1, figsize=(10,5))
# for i in range(runs_exact_x.shape[0]):
# 	length = runs_exact_x[i,1] - runs_exact_x[i,0]
# 	x = np.arange(0, length, 1)/80
# 	y = data[2, runs_exact_x[i,0]:runs_exact_x[i,1]]

# 	axs[0].plot(x, y, alpha=0.5, label=i)
# 	axs[0].set_xlabel("Time [sec]", fontsize=12)
# 	axs[0].set_ylabel("Weight [g]", fontsize=12)
# 	axs[0].legend()

# 	fft_data = np.fft.fft(y)
# 	freqs = np.fft.fftfreq(y.shape[0], d=x[1]-x[0])
# 	axs[1].plot(freqs[:len(freqs)//2], np.abs(fft_data)[:len(freqs)//2], linewidth=1, alpha=0.5, label=i)
# 	axs[1].set_xlabel("Frequency [Hz]", fontsize=12)
# 	axs[1].set_ylabel("Amplitude", fontsize=12)
# 	axs[1].set_ylim(bottom=0, top=600)
# 	axs[1].legend()

# plt.show()


# # 2025.11.03 
# # FFT OF THE SYSTEM WHEN THERE IS NOTHING ON THE SCALES
# baseline_weight = cage.raw_data[0:6500]

# baseline_weight = np.where(baseline_weight < -10, 0, baseline_weight)
# baseline_weight = np.where(baseline_weight > 40, 0, baseline_weight)

# fig = plt.figure(figsize=(15, 4))
# plt.plot(cage.raw_time[0:6500]*60*60, baseline_weight)
# plt.ylim(-7, 7)
# plt.xlabel("Time [s]", fontsize=14)
# plt.ylabel("Weight [g]", fontsize=14)
# fig.savefig("/Users/valeriepineaunoel/Documents/PhD/Results/STUAART/20251028-TestSTUAARTOneMouse80Hz2/Figures/Baseline_weight_outliers_removed.png", format="png")
# plt.show()

# fft_baseline = np.fft.fft(baseline_weight)
# T = 1/80
# N = len(fft_baseline)
# freqs = np.fft.fftfreq(N, T)  # frequency bins
# half = N // 2
# freqs = freqs[:half]
# amplitude = np.abs(fft_baseline[:half]) * 2 / N  # normalize amplitude

# fig = plt.figure(figsize=(15, 4))
# plt.plot(freqs, amplitude)
# plt.ylim(0, 0.15)
# plt.xlabel("Frequency [Hz]", fontsize=14)
# plt.ylabel("Amplitude", fontsize=14)
# fig.savefig("/Users/valeriepineaunoel/Documents/PhD/Results/STUAART/20251028-TestSTUAARTOneMouse80Hz2/Figures/FFT_baseline_outliers_removed.png", format="png")
# plt.show()


# # FFT OF THE 3 SCALES ALONE OF THE BASELINE SIGNAL. MAYBE THE 3 SCALES DO NOT HAVE THE SAME NOISE. 
# baseline_weight_per_scale = []
# for i in range(len(cage.raw_data_per_scale)):
# 	baseline_weight_per_scale.append(cage.raw_data_per_scale[i][20:6200])

# baseline_weight_per_scale = np.array(baseline_weight_per_scale)

# baseline_weight_per_scale = np.where(baseline_weight_per_scale < -10, 0, baseline_weight_per_scale)
# baseline_weight_per_scale = np.where(baseline_weight_per_scale > 40, 0, baseline_weight_per_scale)

# colors = ["blue", "red", "green"]

# fig = plt.figure(figsize=(15, 4))
# for i in range(baseline_weight_per_scale.shape[0]):
# 	plt.plot(cage.raw_time[20:6200]*60*60, baseline_weight_per_scale[i], color=colors[i], alpha=0.7)
# plt.ylim(-2, 2)
# plt.xlabel("Time [s]", fontsize=14)
# plt.ylabel("Weight [g]", fontsize=14)
# fig.savefig("/Users/valeriepineaunoel/Documents/PhD/Results/STUAART/20251028-TestSTUAARTOneMouse80Hz2/Figures/Baseline_weight_per_scale_outliers_removed_2.png", format="png")
# plt.show()

# fft_baseline_per_scale = np.fft.fft(baseline_weight_per_scale)
# T = np.arange(0, fft_baseline_per_scale.shape[1])/80

# fig = plt.figure(figsize=(15, 4))

# for i in range(fft_baseline_per_scale.shape[0]):
# 	N = len(fft_baseline_per_scale[i])
# 	half = N // 2
# 	freqs = np.fft.fftfreq(fft_baseline_per_scale[i].shape[0], d=T[1]-T[0])  # frequency bins
# 	plt.plot(freqs[:len(freqs)//2], np.abs(fft_baseline_per_scale[i])[:len(freqs)//2], color=colors[i])

# plt.xlabel("Frequency [Hz]", fontsize=14)
# plt.ylabel("Amplitude", fontsize=14)
# fig.savefig("/Users/valeriepineaunoel/Documents/PhD/Results/STUAART/20251028-TestSTUAARTOneMouse80Hz2/Figures/FFT_baseline_outliers_per_scale_removed_2.png", format="png")
# plt.show()


# # JE VAIS ESSAYER DE FAIRE LE ICA DES DONNÉES 
# Initialize ICA
# weight_data = []
# for i in range(len(cage.raw_data_per_scale)):
# 	weight_data.append(cage.raw_data_per_scale[i])

# weight_data = np.array(weight_data)

# weight_data = np.where(weight_data < -10, 0, weight_data)
# weight_data = np.where(weight_data > 40, 0, weight_data)

# colors = ["blue", "red", "green"]

# ica = FastICA(n_components=3, random_state=0)

# # Fit ICA model and transform data
# S_ = ica.fit_transform(weight_data)  # Reconstructed independent sources
# A_ = ica.mixing_           # Estimated mixing matrix

# # Optional: recover the signals back (check reconstruction)
# X_reconstructed = S_ @ A_.T

# fig, axes = plt.subplots(2, 3, figsize=(10, 6))
# axes[0,0].set_ylabel("Mixed signals")
# axes[1,0].set_ylabel("ICA recovered")

# for i in range(3):
#     axes[0,i].plot(weight_data[i, :], color=colors[i])
#     axes[1,i].plot(S_[:, i], color=colors[i])

# plt.tight_layout()
# plt.show()


# # 2025.11.04 
# # JE VAIS ESSAYER DE FAIRE PCA SUR LES POWER SPECTRA

# eigenvectors, projected_data = cage.pca(dataset=all_amplitudes, number_of_PCs=10, targets=targets, labels=labels, on_scale=on_scale, PCs_to_plot=[0,1,2], label_per_scale=False, x_label="Frequency [Hz]")

# # # JE VAIS ENSUITE ESSAYER DE FAIRE DE LA CLASSIFICATION DU TYPE HDBSCAN

# clusterer = HDBSCAN(
#     min_cluster_size=2,  # minimum number of samples per cluster
#     min_samples=11,       # smaller = more clusters, larger = fewer
#     cluster_selection_epsilon=0.0
# )
# labels_hdbscan = clusterer.fit_predict(projected_data)

# ari = adjusted_rand_score(targets, labels_hdbscan) # Measures similarity between cluster assignments, independent of label values. Perfect match = 1.0, 0.0 is random grouping. 
# print("Adjusted Rand Index:", ari)

# # -1 means "noise" points (unclustered)
# n_clusters = len(set(labels_hdbscan)) - (1 if -1 in labels_hdbscan else 0)
# print(f"Number of clusters found: {n_clusters}")

# fig = plt.figure(figsize=(8,8))
# ax = fig.add_subplot(111, projection="3d")
# ax.scatter(projected_data[:, 0], projected_data[:, 1], projected_data[:,2], c=labels_hdbscan, cmap='Spectral', s=10)
# ax.set_title("HDBSCAN Clusters in PCA Space")
# ax.set_xlabel("PC 0", fontsize=14)
# ax.set_ylabel("PC 1", fontsize=14)
# ax.set_zlabel("PC 2", fontsize=14)
# plt.show()

# # JE VAIS ESSAYER DE FAIRE ICA PUIS HDBSCAN


# X: (n_samples, n_features) — your weight data from the 3 scales
# Example placeholder:
# X = np.load("weights.npy")

# ica = FastICA(n_components=3, random_state=0)
# X_ica = ica.fit_transform(all_amplitudes)  # Independent components
# A_ = ica.mixing_
# # Compute variance captured by each component (not "explained variance")

# unique_labels = sorted(list(set(labels)))
# cmap = cm.get_cmap("jet", len(unique_labels))  # Use any colormap you like
# color_map = {label: cmap(i) for i, label in enumerate(unique_labels)}
# colors = [color_map[label] for label in labels]

# fig = plt.figure(figsize=(8,8))
# ax = fig.add_subplot(111, projection="3d")
# ax.scatter(X_ica[:,0], X_ica[:,1], X_ica[:,2], c=colors, alpha=0.5)
# for label in unique_labels:
#     ax.scatter([], [], color=color_map[label], label=label)
# ax.legend(title="Labels behaviour")
# ax.set_xlabel("ICA component 0", fontsize=14)
# ax.set_ylabel("ICA component 1", fontsize=14)
# ax.set_zlabel("ICA component 2", fontsize=14)
# plt.show()


# clusterer = HDBSCAN(
#     min_cluster_size=2,  # tune this
#     min_samples=10,       # tune this
# )
# labels_hdbscan = clusterer.fit_predict(X_ica)

# ari = adjusted_rand_score(targets, labels_hdbscan) # Measures similarity between cluster assignments, independent of label values. Perfect match = 1.0, 0.0 is random grouping. 
# print("Adjusted Rand Index:", ari)

# fig = plt.figure(figsize=(8,8))
# ax = fig.add_subplot(111, projection="3d")
# ax.scatter(X_ica[:, 0], X_ica[:, 1], X_ica[:,2], c=labels_hdbscan, cmap='Spectral', s=10)
# ax.set_title("HDBSCAN Clusters in PCA Space")
# ax.set_xlabel("ICA component 0", fontsize=14)
# ax.set_ylabel("ICA component 1", fontsize=14)
# ax.set_zlabel("ICA component 2", fontsize=14)
# plt.title("HDBSCAN on ICA components")
# plt.show()


# plt.figure(figsize=(10,3))
# plt.plot(labels_hdbscan, lw=0.7)
# plt.title("Cluster assignment over time")
# plt.xlabel("Time index")
# plt.ylabel("Cluster ID")
# plt.show()










