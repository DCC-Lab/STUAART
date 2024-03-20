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


data = np.array(pd.read_csv(your_path))

time = data[:,0]/(1000 * 60 * 60)
data1 = data[:,1]
data2 = data[:,2]
data3 = data[:,3]

data1 = Data(data1)
data2 = Data(data2)
data3 = Data(data3)
print(data1)

threshold = 5 * 10**5

data1.set_outliers_threshold(threshold)
data2.set_outliers_threshold(threshold)
data3.set_outliers_threshold(threshold)

data1.center_data_on_zero()
data2.center_data_on_zero()
data3.center_data_on_zero()

data1.remove_outliers()
data2.remove_outliers()
data3.remove_outliers()




plt.plot(time, data1)
plt.plot(time, data2)
plt.plot(time, data3)
plt.xlabel("Time [h]")
plt.ylabel("Raw output [-]")
plt.show()

