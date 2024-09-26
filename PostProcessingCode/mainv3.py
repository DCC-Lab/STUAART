# create a python file named path.py in the same directory containing the file (on the same level)
# add this file to gitignore, only you will see it
# create a variable named your_path = "your path to the data" (string type)
# this variable is imported in this file
# this way, everyone can run this code even if all paths to the data are different
from path import your_path
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

data = np.array(pd.read_csv(your_path))
directory = "/Users/valeriepineaunoel/Documents/PhD/Results/20240407-AcquireWeightForALongTimeNoAutotareMouse588/"
filename = "20240407-3hours.csv"
cage = Cage(directory=directory, filename=filename, number_of_scales=3, real_data=np.array([0, 34.1]))
# cage.plot_data_per_scale()
# cage.compute_individual_scale_information(first_day=True, produce_graph=True)
cage.compute_location_on_scale(first_day=True, produce_graph=True)