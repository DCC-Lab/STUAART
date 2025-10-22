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
# cage.compute_hanging(first_day=True, produce_graph=True)

# LOCATION
# directory_ground_truth_location = "/Users/valeriepineaunoel/Documents/PhD/Results/STUAART/20251016-TestSTUAARTOneMouse80Hz/20251016-BehaviourDataAfterWatching/"
# filenames_ground_truth_location = ["On scale 1-Table 1.csv", "On scale 2-Table 1.csv", "On scale 3-Table 1.csv", "On scales 1 and 2-Table 1.csv", "On scales 2 and 3-Table 1.csv"]
# cage.compute_location_on_scale(first_day=True, produce_graph=True, is_saved=True)
# cage.compute_location_on_scale_accuracy(is_saved=True, directory_ground_truth=directory_ground_truth_location, filenames=filenames_ground_truth_location, delay_in_seconds=delay_video_weight, evaluate_only_between_these_hours=None)


# GROOMING
# Look at 2-second samples of weight data per behaviour type PER SCALE and produce PCA. 
# directory_behaviour = "/Users/valeriepineaunoel/Documents/PhD/Results/STUAART/20251016-TestSTUAARTOneMouse80Hz/20251016-BehaviourDataAfterWatching/Behaviour/"
# two_second_data, on_scale, targets, labels = cage.produce_behaviour_dataset_per_scale(directory=directory_behaviour, delay_in_seconds=delay_video_weight)
# cage.pca(dataset=two_second_data, number_of_PCs=10, targets=targets, labels=labels, on_scale=on_scale, PCs_to_plot=[1,2,3], label_per_scale=False)

# # Look at 2-second samples of weight data per behaviour type, overall weight of the system, and produce PCA. 
# two_second_data, targets, labels = cage.produce_behaviour_dataset(directory=directory_behaviour, delay_in_seconds=delay_video_weight)
# cage.pca(dataset=two_second_data, number_of_PCs=10, targets=targets, labels=labels, on_scale=on_scale, label_per_scale=False)

# two_second_data, on_scale, targets, labels = cage.produce_behaviour_dataset_per_scale(directory=directory_behaviour, delay_in_seconds=delay_video_weight)
# cage.fft_behaviour(dataset=two_second_data, labels=labels, plot=True)









