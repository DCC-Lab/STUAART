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

color_data1 = "b"
color_data2 = "r"
color_data3 = "g"

save_figure = False

data = np.array(pd.read_csv(your_path))


# -----------

time = data[:,0]/(1000 * 60 * 60) # time in hours
data1 = data[:,1] # weight measurements scale 1, 300g
data2 = data[:,2] # weight measurements scale 1, 100g
data3 = data[:,3] # weight measurements scale 1, 100g

real_data = np.array([[time[0], time[-1]],[29.5, 29.5]])

# This is used in case we want to amplify the drift for testing
# data1[3000:] += 3000
# data1[5000:] += 3000

data1 = Data(data1, time)
data2 = Data(data2, time)
data3 = Data(data3, time)

# if the measurements are higher than the threshold [g], for sure they are outliers
threshold1 = [-10, 40]
threshold2 = [-10, 40]
threshold3 = [-10, 40]

# data1.plot_signal(threshold=False, peaks=False, baseline=False, color=color_data1, is_saved=save_figure, real_data=real_data)
# data2.plot_signal(threshold=False, peaks=False, baseline=False, color=color_data2, is_saved=save_figure, real_data=real_data)
# data3.plot_signal(threshold=False, peaks=False, baseline=False, color=color_data3, is_saved=save_figure, real_data=real_data)

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
# data1.plot_signal(threshold=False, peaks=False, baseline=False, color=color_data1, is_saved=save_figure, real_data=real_data)
# data2.plot_signal(threshold=False, peaks=False, baseline=False, color=color_data2, is_saved=save_figure, real_data=real_data)
# data3.plot_signal(threshold=False, peaks=False, baseline=False, color=color_data3, is_saved=save_figure, real_data=real_data)

data1.set_weight_threshold()
data2.set_weight_threshold()
data3.set_weight_threshold()

data1.find_peak_average_values()
data2.find_peak_average_values()
data3.find_peak_average_values()

data1.find_all_peaks_values()
data2.find_all_peaks_values()
data3.find_all_peaks_values()
# data1.plot_signal(threshold=False, peaks=True, baseline=False, color=color_data1, is_saved=save_figure)
# data2.plot_signal(threshold=False, peaks=True, baseline=False, color=color_data2, is_saved=save_figure)
# data3.plot_signal(threshold=False, peaks=True, baseline=False, color=color_data3, is_saved=save_figure)


# Donc, basically ici je fais la somme des 3 mesures des balances dans le temps parce que ça devrait toujours être le poids de la souris uknow. 
sum_data = data1 + data2 + data3
print("DATA1 : ", data1)
fig = plt.figure(figsize=(15,5))
plt.scatter(real_data[0], real_data[1], color="y", label="Real weight", edgecolors="k", marker="*", s=200)
plt.plot(data1.time, sum_data, color="k")
plt.xlabel("Time [h]", fontsize=17)
plt.ylabel("Weight [g]", fontsize=17)
plt.show()

# Ici je vais la matrice de corrélation des données dans le temps. Ça devrait corréler négativement parce que, si la souris est sur une balance, elle n'est pas sur les autres, etc. 
# all_data = np.array([data1,data2,data3])
# print("Shape all data : ", all_data.shape)
# C = np.corrcoef(all_data)
# plt.imshow(C, cmap="PiYG")
# plt.colorbar()
# plt.xticks(range(len(all_data)), ["Scale 1", "Scale 2", "Scale 3"])
# plt.yticks(range(len(all_data)), ["Scale 1", "Scale 2", "Scale 3"])
# plt.show()

# data1.plot_signal(baseline=False)
# data1.plot_baseline()
# data1.plot_all_peaks()