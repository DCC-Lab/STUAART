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
from scipy.signal import find_peaks, stft
from sklearn.decomposition import FastICA
from sklearn.cluster import HDBSCAN
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score, fowlkes_mallows_score
import matplotlib.cm as cm
from hmmlearn import hmm
from sklearn.preprocessing import StandardScaler
from tqdm import tqdm

# color_data1 = "b"
# color_data2 = "r"
# color_data3 = "g"

# save_figure = False

delay_video_mass = 20.5

directory = '/Volumes/ValériePN/PhD/STUAART/20251128-TestWithMouseForMoreBehaviourData/'
filename = "2025.11.28-RawMassData_NoBufferLog.csv"
# np.array([22.8, 22.8])
cage = Cage(directory=directory, filename=filename, number_of_scales=3, real_data=[23.6, 22.])
# cage.plot_data_per_scale()
# cage.compute_individual_scale_information(first_day=True, produce_graph=True)
# cage.compute_mean_data(smooth_level=4, produce_graph=True, is_saved=True)

# HANGING
# cage.compute_hanging(first_day=True, produce_graph=True)

# LOCATION
# directory_ground_truth_location = '/Users/valeriepineaunoel/Library/Mobile Documents/com~apple~CloudDocs/Documents/PhD/Results/STUAART/20251128-TestWithMouseForMoreBehaviourData/20251128-BehaviourDataAfterWatchingVideo/'
# filenames_ground_truth_location = ["On scale 1-Table 1.csv", "On scale 2-Table 1.csv", "On scale 3-Table 1.csv", "On scales 1 and 2-Table 1.csv", "On scales 2 and 3-Table 1.csv"]
# cage.compute_location_on_scale(first_day=True, produce_graph=True, is_saved=False)
# cage.compute_location_on_scale_accuracy(is_saved=False, directory_ground_truth=directory_ground_truth_location, filenames=filenames_ground_truth_location, delay_in_seconds=delay_video_mass, evaluate_only_between_these_hours=[0, 1])


# GROOMING
# # Look at 2-second samples of mass data per behaviour type PER SCALE and produce PCA. 
directory_behaviour = '/Volumes/ValériePN/PhD/STUAART/20251128-TestWithMouseForMoreBehaviourData/20251128-BehaviourDataAfterWatchingVideo/Behaviour/'
# two_second_data, on_scale, targets, labels = cage.produce_behaviour_dataset_per_scale(directory=directory_behaviour, delay_in_seconds=delay_video_mass)
# cage.pca(dataset=two_second_data, number_of_PCs=10, targets=targets, labels=labels, on_scale=on_scale, PCs_to_plot=[1,2,3], label_per_scale=False)

# # Look at 2-second samples of mass data per behaviour type, overall mass of the system, and produce PCA. 
# two_second_data, targets, labels = cage.produce_behaviour_dataset(directory=directory_behaviour, delay_in_seconds=delay_video_mass)
# cage.pca(dataset=two_second_data, number_of_PCs=10, targets=targets, labels=labels, on_scale=on_scale, PCs_to_plot=[1,2,3], label_per_scale=False)

data, on_scale, targets, labels = cage.produce_behaviour_dataset_per_scale(directory=directory_behaviour, delay_in_seconds=delay_video_mass, window_duration_in_seconds=2)
np.savetxt(directory+"2sec-data/data.csv", data, delimiter=",")
np.savetxt(directory+"2sec-data/on_scale.csv", on_scale, delimiter=",")
np.savetxt(directory+"2sec-data/targets.csv", targets, delimiter=",")
print(np.unique(labels, return_index=True))

# all_frequencies, all_amplitudes = cage.fft_behaviour(dataset=two_second_data, labels=labels, plot=True)


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
# 	axs[i].set_ylabel("mass [g]", fontsize=12)
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
# 	plt.ylabel("mass [g]", fontsize=10)
# 	plt.xlabel("Timestamps (190 data points = 2 seconds)", fontsize=10)
# 	plt.savefig("/Users/valeriepineaunoel/Documents/PhD/Results/STUAART/20251016-TestSTUAARTOneMouse80Hz/Figures/RawGrooming/Individual-2second-grooming-raw-index" + str(j) + ".png", format="png")
# 	plt.close()
# 	i += 1

# # THESE ARE THE ONES THAT I FOUND VISUALLY CLEAN SO I'M ONLY GOING TO FFT THESE TIME SERIES
# indices_clean_grooming = [58, 59, 65, 66, 70, 77, 80, 81, 88, 93, 100, 103]
# mass_data_of_clean_grooming = two_second_data[indices_clean_grooming, :]
# fft_of_clean_grooming = np.fft.fft(mass_data_of_clean_grooming)
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

# plt.ylabel("mass [g]", fontsize=12)
# plt.xlabel("Timestamp (190 data points = 2 seconds)", fontsize=12)
# plt.savefig("/Users/valeriepineaunoel/Documents/PhD/Results/STUAART/20251016-TestSTUAARTOneMouse80Hz/Figures/RawGrooming/mass_data_of_clean_2second_grooming.png", format="png")
# plt.show()


# # FFT OF ALL 10-SECOND GROOMING EVENTS FOR VISUALISATION 
# indices_of_grooming = np.where(labels == "Grooming")[0]
# data_of_grooming = two_second_data[indices_of_grooming, :]
# fft_of_grooming = np.fft.fft(data_of_grooming)
# x = np.arange(0, fft_of_grooming.shape[1])/800

# fig = plt.figure(figsize=(15, 4))

# for i in range(len(indices_of_grooming)):
# 	freqs = np.fft.fftfreq(fft_of_grooming[i].shape[0], d=x[1]-x[0])
# 	plt.plot(freqs[:len(freqs)//2], np.abs(fft_of_grooming[i])[:len(freqs)//2], label="Index : " + str(indices_of_grooming[i]), alpha=0.7)

# plt.ylim(0, 200)
# plt.ylabel("Amplitude", fontsize=12)
# plt.xlabel("Timestamp (190 data points = 2 seconds)", fontsize=12)
# # plt.savefig("/Users/valeriepineaunoel/Documents/PhD/Results/STUAART/20251016-TestSTUAARTOneMouse80Hz/Figures/GroomingInvestiguation/FTT_all_grooming.png", format="png")
# plt.show()


# # 2025.10.31 
# # I AM TRYING HERE TO IDENTIFY WHERE THE MOUSE IS GROOMING FOR A LONG TIME. 800 DATA POINTS = 10 SECONDS
# cage.retreive_indicator_behaviour_data_per_scale(directory=directory_behaviour, delay_in_seconds=delay_video_mass)

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
# 	axs[0].set_ylabel("mass [g]", fontsize=12)
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
# baseline_mass = cage.raw_data[0:6500]

# baseline_mass = np.where(baseline_mass < -10, 0, baseline_mass)
# baseline_mass = np.where(baseline_mass > 40, 0, baseline_mass)

# fig = plt.figure(figsize=(15, 4))
# plt.plot(cage.raw_time[0:6500]*60*60, baseline_mass)
# plt.ylim(-7, 7)
# plt.xlabel("Time [s]", fontsize=14)
# plt.ylabel("mass [g]", fontsize=14)
# fig.savefig("/Users/valeriepineaunoel/Documents/PhD/Results/STUAART/20251028-TestSTUAARTOneMouse80Hz2/Figures/Baseline_mass_outliers_removed.png", format="png")
# plt.show()

# fft_baseline = np.fft.fft(baseline_mass)
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
# baseline_mass_per_scale = []
# for i in range(len(cage.raw_data_per_scale)):
# 	baseline_mass_per_scale.append(cage.raw_data_per_scale[i][20:6200])

# baseline_mass_per_scale = np.array(baseline_mass_per_scale)

# baseline_mass_per_scale = np.where(baseline_mass_per_scale < -10, 0, baseline_mass_per_scale)
# baseline_mass_per_scale = np.where(baseline_mass_per_scale > 40, 0, baseline_mass_per_scale)

# colors = ["blue", "red", "green"]

# fig = plt.figure(figsize=(15, 4))
# for i in range(baseline_mass_per_scale.shape[0]):
# 	plt.plot(cage.raw_time[20:6200]*60*60, baseline_mass_per_scale[i], color=colors[i], alpha=0.7)
# plt.ylim(-2, 2)
# plt.xlabel("Time [s]", fontsize=14)
# plt.ylabel("mass [g]", fontsize=14)
# fig.savefig("/Users/valeriepineaunoel/Documents/PhD/Results/STUAART/20251028-TestSTUAARTOneMouse80Hz2/Figures/Baseline_mass_per_scale_outliers_removed_2.png", format="png")
# plt.show()

# fft_baseline_per_scale = np.fft.fft(baseline_mass_per_scale)
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


# # 2025.11.04 
# # JE VAIS ESSAYER DE FAIRE PCA SUR LES POWER SPECTRA

# eigenvectors, projected_data = cage.pca(dataset=all_amplitudes, number_of_PCs=10, targets=targets, labels=labels, on_scale=on_scale, PCs_to_plot=[0,1,2], label_per_scale=False, x_label="Frequency [Hz]")

# # JE VAIS ENSUITE ESSAYER DE FAIRE DE LA CLASSIFICATION DU TYPE HDBSCAN

# clusterer = HDBSCAN(
#     min_cluster_size=2,  # minimum number of samples per cluster
#     min_samples=3,       # smaller = more clusters, larger = fewer
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


# X: (n_samples, n_features) — your mass data from the 3 scales
# Example placeholder:
# X = np.load("masss.npy")

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


# # TEST SHORT-TIME FOURIER TRANSFORM + HMM

# index = np.where(cage.raw_time > 0.745691)[0][0]
# time = cage.raw_time[:index]
# print("Total time of the experiment : {:.4f} seconds.".format(time[-1]*60*60))

# max_sampling, fs_mean = cage.compute_sampling_rate(time_array_in_hours=cage.raw_time)
# nperseg = max_sampling * 3
# noverlap = max_sampling * 2

# # # WITH INTERPOLATION BEFORE THE STFT. I have to interpolate to have the same number of data points per second to that I can compare my behaviour data with the ground truth
# time_uniform = np.arange(time[0]*60*60, time[-1]*60*60, 1/max_sampling)
# to_remove = np.array([3600, 3601, 3602, 3603, 3604, 3605, 7200, 7201])
# times_filtered = time_uniform[~np.isin(time_uniform.astype(int), to_remove.astype(int))]

# mass_per_scale = []
# for i in range(len(cage.raw_data_per_scale)):
#   data = cage.raw_data_per_scale[i][:index]
#   uniform_data = np.interp(times_filtered, time, data)
#   mass_per_scale.append(uniform_data)
# mass_per_scale = np.array(mass_per_scale)

# # Compute STFT for each scale
# spectrograms_with = []
# all_ts_with = []
# all_fs = []
# for i in tqdm(range(mass_per_scale.shape[0])):
#   data = mass_per_scale[i, :]
#   x_padded = np.pad(data, (int(max_sampling), int(max_sampling)), mode='constant') # this is to not miss the beginning and ending data
#   # f: frequency bins (0 → 40 Hz since Nyquist = fs/2)
#   # t: time points (centers of each window, spaced by 1 second)
#   # Zxx: complex spectrogram, shape = (n_frequencies, n_time_windows)
#   f, t_with, Zxx = stft(x_padded, fs=max_sampling, nperseg=nperseg, noverlap=noverlap, nfft=nperseg)
#   # Use magnitude (power spectrum)
#   spectrograms_with.append(np.abs(Zxx))
#   all_ts_with.append(t_with)
#   all_fs.append(f)




# # WITHOUT INTERPOLATION BEFORE THE STFT
# mass_per_scale = []
# for i in range(len(cage.raw_data_per_scale)):
#   data = cage.raw_data_per_scale[i][:index]
#   mass_per_scale.append(data)
# mass_per_scale = np.array(mass_per_scale)

# # Compute STFT for each scale
# spectrograms_without = []
# all_ts = []
# all_fs = []
# for i in tqdm(range(mass_per_scale.shape[0])):
#   data = mass_per_scale[i, :]
#   x_padded = np.pad(data, (int(max_sampling), int(max_sampling)), mode='constant') # this is to not miss the beginning and ending data
#   # f: frequency bins (0 → 40 Hz since Nyquist = fs/2)
#   # t: time points (centers of each window, spaced by 1 second)
#   # Zxx: complex spectrogram, shape = (n_frequencies, n_time_windows)
#   f, t_without, Zxx = stft(x_padded, fs=max_sampling, nperseg=nperseg, noverlap=noverlap, nfft=nperseg)
#   # Use magnitude (power spectrum)
#   spectrograms_without.append(np.abs(Zxx))
#   all_ts.append(t_without)
#   all_fs.append(f)



# # PLOT SPECTROGRAMS
# n = len(spectrograms_with)
# cols = 3
# rows = int(np.ceil(n / cols))

# fig, axes = plt.subplots(rows, cols, figsize=(15, 4 * rows))
# axes = axes.flatten()

# for i, ax in enumerate(axes[:n]):
#   pcm = ax.pcolormesh(all_ts_with[i], all_fs[i], spectrograms_with[i], shading='gouraud', cmap="Greys", vmin=0, vmax=1.7)
#   ax.set_title(f"Spectrogram from scale {i+1}")
#   ax.set_ylabel('Freq [Hz]')
#   ax.set_xlabel('Time [s]')
#   # ax.set_ylim(bottom=0, top=5)

# # Remove empty subplots if any
# for ax in axes[n:]:
#   ax.axis('off')

# # fig.colorbar(pcm, ax=axes[:n], orientation='vertical', label='Amplitude')
# fig.tight_layout()
# plt.show()


# Stack across scales and flatten frequency info
# Shape: (n_time_windows, total_features)
# S_with = np.concatenate([s.T for s in spectrograms_with], axis=1)
# S_without = np.concatenate([s.T for s in spectrograms_without], axis=1)

# # Optional: scale the features
# S_with = StandardScaler().fit_transform(S_with)
# S_without = StandardScaler().fit_transform(S_without)

# # Fit an HMM to segment into different "behavioral states"
# n_states = 4  # e.g., you suspect 5 types of behavior
# model_with = hmm.GaussianHMM(n_components=n_states, covariance_type="diag", random_state=0)
# model_with.fit(S_with)

# model_without = hmm.GaussianHMM(n_components=n_states, covariance_type="diag", random_state=0)
# model_without.fit(S_without)

# # Predict hidden states
# states_with = model_with.predict(S_with)
# states_without = model_without.predict(S_without)

# cage.retreive_indicator_behaviour_data_per_timestamp(timestamp=60, directory=directory_behaviour, delay_in_seconds=delay_video_mass, index=index)
# print("Behaviour indicator per second : ", cage.behaviour_indicator_per_timestamp["Grooming"].shape)
# print("States without interpolation : ", states_without.shape, np.amin(states_without), np.amax(states_without))

# time_grondtruth = np.linspace(0, cage.behaviour_indicator_per_timestamp["Grooming"].shape[0], cage.behaviour_indicator_per_timestamp["Grooming"].shape[0])
# print(time_grondtruth.shape)
# interpol_states = np.floor(np.interp(time_grondtruth, t_without, states_without))
# print("Interpolated states : ", interpol_states.shape, np.amin(interpol_states), np.amax(interpol_states), np.unique(interpol_states))


# j = 0
# all_behaviour_indicators = np.zeros(shape=cage.behaviour_indicator_per_timestamp["Grooming"].shape[0])
# for key in cage.behaviour_indicator_per_timestamp.keys():
#   indicator_behaviour = cage.behaviour_indicator_per_timestamp[key]
#   all_behaviour_indicators = np.where(indicator_behaviour == 1, j, all_behaviour_indicators)
#   j += 1

# print("All_behaviour states ground truth : ", all_behaviour_indicators, all_behaviour_indicators.shape, np.unique(all_behaviour_indicators))


# ari = adjusted_rand_score(all_behaviour_indicators, interpol_states) # Measures similarity between cluster assignments, independent of label values. Perfect match = 1.0, 0.0 is random grouping. 
# print("Adjusted Rand Index:", ari)

# nmi = normalized_mutual_info_score(all_behaviour_indicators, interpol_states)
# print("Normalized mutual information score : ", nmi)

# fms = fowlkes_mallows_score(all_behaviour_indicators, interpol_states)
# print("Fowlkes–Mallows Index : ", fms)


# plt.figure(figsize=(12, 4))
# plt.plot(t_without, states_without, linewidth=0, marker="s", color="y", markersize=6, label="Without interpolation before STFT")
# plt.plot(t_with, states_with, linewidth=0, marker="o", color="m", alpha=0.5, markersize=4, label="With interpolation before STFT")
# plt.title("Inferred behavioral states over time")
# # plt.legend()
# plt.show()




# # 2026.01.08 : ESSAYER D'EXTRAIRE LES FEATURES ET DE VOIR SI JE SUIS CAPABLE D'IDENTIFIER LE GROOMING AVEC ÇA
# cage.retreive_indicator_behaviour_data_per_scale(directory=directory_behaviour, delay_in_seconds=delay_video_mass, evaluate_only_between_these_hours=[0, 0.5])

# behaviour_labels_ground_truth = np.zeros(shape=(3, cage.behaviour_indicator_per_scale["Grooming"].shape[1]))
# for n in range(3):
# 	indices_grooming = np.where(cage.behaviour_indicator_per_scale["Grooming"][n] == 1.0)[0]
# 	behaviour_labels_ground_truth[n, indices_grooming] = 1.0
# 	indices_nesting = np.where(cage.behaviour_indicator_per_scale["Nesting"][n] == 1.0)[0]
# 	behaviour_labels_ground_truth[n, indices_nesting] = 1.0
# 	# indices_nesting = np.where(cage.behaviour_indicator_per_scale["Play with isopad"][n] == 1.0)[0]
# 	# behaviour_labels_ground_truth[n, indices_nesting] = 1.0
# 	# indices_nesting = np.where(cage.behaviour_indicator_per_scale["Rearing"][n] == 1.0)[0]
# 	# behaviour_labels_ground_truth[n, indices_nesting] = 1.0
# 	indices_nesting = np.where(cage.behaviour_indicator_per_scale["Eating"][n] == 1.0)[0]
# 	behaviour_labels_ground_truth[n, indices_nesting] = 1.0
# 	indices_nesting = np.where(cage.behaviour_indicator_per_scale["Licking"][n] == 1.0)[0]
# 	behaviour_labels_ground_truth[n, indices_nesting] = 1.0
# 	# indices_nesting = np.where(cage.behaviour_indicator_per_scale["Play with cables"][n] == 1.0)[0]
# 	# behaviour_labels_ground_truth[n, indices_nesting] = 1.0
# 	indices_nesting = np.where(cage.behaviour_indicator_per_scale["Sniffing"][n] == 1.0)[0]
# 	behaviour_labels_ground_truth[n, indices_nesting] = 1.0

# valid_times, features, feature_names = cage.extract_feature_every_timestamp(behaviour_labels=behaviour_labels_ground_truth, is_saved=False, produce_graph=False, evaluate_only_between_these_hours=[0, 0.5])
# # grooming_indicator_per_scale = cage.identify_grooming_with_common_indices(features=features, timestamps=np.array(valid_times), feature_names=feature_names)
# grooming_indicator_per_scale = cage.identify_grooming_with_number_of_hits(features=features, timestamps=np.array(valid_times), feature_names=feature_names, min_number_of_hits=6)
# cage.compare_with_behaviour_labels(timestamps=np.array(valid_times), behaviour_labels=grooming_indicator_per_scale, behaviour_labels_ground_truth=behaviour_labels_ground_truth, evaluate_only_between_these_hours=[0, 0.5], produce_graph=True, is_saved=True)






