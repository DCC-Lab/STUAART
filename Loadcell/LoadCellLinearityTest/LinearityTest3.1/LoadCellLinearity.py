import numpy as np
import matplotlib.pyplot as plt
import scipy.optimize as scipy
import pandas as pd

path = "/Users/nathan/Documents/UL/Session - E23/IntelligentCage/Loadcell/LoadCellLinearityTest/LinearityTest3.1/testlinearityloadcelldata.csv"

data = np.array(pd.read_csv(path, header=0))

weights = np.sort(data[:,1])


offset = data[:,2]
output = data[:,3]
print(weights)
output_variation = np.sort(output - offset)


def curve_func(x, m):
    return m*x

# curve_fit for all points from 0 to 55g
full_popt, pcov = scipy.curve_fit(curve_func, weights, output_variation)

full_m = full_popt[0]

x = np.linspace(0, 55, 1000)
full_y = np.array([curve_func(i, full_m) for i in x])


# curve fit for the first points from 0 to 20g
partial_popt, pcov = scipy.curve_fit(curve_func, weights[:5], output_variation[:5])

partial_m = partial_popt[0]

partial_y = np.array([curve_func(i, partial_m) for i in x])



print(full_m, partial_m)

# plt.rcParams['text.usetex'] = Trues

fig, axs = plt.subplots(1, 1)
axs.plot(weights, output_variation, label="Data")
axs.plot(x, full_y, label="Curve with all points")
axs.plot(x,partial_y, label="Curve with points under 25g")
axs.set_xlabel("Weight [g]")
axs.set_ylabel("Output of the load cell [-]")
axs.legend()
plt.show()