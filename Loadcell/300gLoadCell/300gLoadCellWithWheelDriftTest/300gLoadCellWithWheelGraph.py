import numpy as np
import matplotlib.pyplot as plt
import scipy.optimize as scipy
import pandas as pd
import csv


path = "/Users/nathan/Documents/UL/Session - E23/IntelligentCage/Loadcell/300gLoadCell/300gLoadCellWithWheelDriftTest/data.csv"

data = np.array(pd.read_csv(path, header=0))

weight = data[:,1]
time = data[:,0]

# plt.rcParams['text.usetex'] = Trues

reference = np.ones(len(weight)) * 21.4


fig, axs = plt.subplots(1, 1)
axs.plot(time, weight, label="With 200g wheel", color="black")
axs.plot(time, reference, label="Reference weight of 21.4 g", linestyle="dashed", color="red")
axs.set_xlabel("Times [h]")
axs.set_ylabel("Weight [g]")
axs.legend()
axs.set_yticks([0, 10, 21, 21.5, 22])
plt.show()