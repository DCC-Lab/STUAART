import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


path = "/Users/nathan/Documents/UL/Session - E23/Python cage/20240212-TestSmartCageAtDeskWithoutAutotareWithoutObject.csv"
data = np.array(pd.read_csv(path))
mouse_weight = 20
threshold = 2 * mouse_weight


time = data[:,0]/(100 * 60)
weight_1 = data[:,1]
weight_2 = data[:,2]
weight_3 = data[:,3]


mean_1 = np.mean(weight_1)

filtered_weight_1 = weight_1[abs(weight_1) < (mean_1 + threshold)]




fig, ax = plt.subplots()
ax.plot(weight_1, label='Not filtered')
ax.plot(filtered_weight_1, label='Filtered')
# ax.plot(weight_2)
# ax.plot(weight_3)
ax.legend()
plt.show()