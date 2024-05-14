import numpy as np
import matplotlib.pyplot as plt
import exceptions
import scipy.fft as fft


class Cage():

    def __init__(self, data_list: list, time: np.ndarray):
        self.time = time
        
        array = np.array(data_list)
        self.data = np.sum(array, axis=0)

    def remove_outliers(self, upper_threshold: float=45, window_length: int=20, change_tolerance: float=5):
        # rough filtering by removing any values over the specified threshold
        under_threshold_index = np.argwhere(np.abs(self.data) < upper_threshold)
        self.data = self.data[under_threshold_index].squeeze()
        self.time = self.time[under_threshold_index.squeeze()]

        # removing all negative values
        # get all index where condition is met
        positive_values_index = np.argwhere(self.data >= 0)
        self.data = self.data[positive_values_index].squeeze()
        self.time = self.time[positive_values_index.squeeze()]


        # removing all values of spontaneous peaks
        # looping on all values
        outliers_index = []
        for i, value in enumerate(self.data):
            # only considering windows that are clear from start
            if i >= window_length:
                # slicing window of interest
                window_array = self.data[i - window_length: i]
                # getting maximum of the window
                maximum_in_window = np.max(window_array)
                # calculating the average difference from neighbors
                average_difference = np.sum(maximum_in_window - window_array)/(window_length - 1)

                if average_difference < change_tolerance:
                    outliers_index.append(i)

        # delete data points considered as outliers
        self.data = np.delete(self.data, outliers_index)
        self.time = np.delete(self.time, outliers_index)



    def fft_filter(self, cutoff_freq: float=60):
        """ Low pass fft filter on the signal. A simple filter is implemented for now. A sharp cut is done
        at the cutoff frequency in fft spectrum. The signal is regenerated from the modified frequency spectrum.


        Arguments:
            - cutoff_frequency: cutoff frquency of the sharp low pass filter in fft spectrum
        """
        # # this code section is not used for now. uncomment if needed.
        # # generate frequencies array. this could be used to calculate cutoff frequency automatically. not implemented yet

        # get frequencies array [-max_freq, ..., 0, ... max_freq]
        freqs = fft.fftfreq(len(self.data), self.time[1] - self.time[0])

        print(self.time)
        # # consider only postive frequencies to calculate cutoff frequency more easily
        # positive_freqs = freqs[:len(freqs)//2]
        # # take median frequency as cutoff frequency (arbitrary)
        # cutoff_freq = freqs[len(freqs)//2]


        # take the fourier transform of the signal (self)
        transformed_array = fft.fft(self.data)
        # get amplitudes of all frequency, norm of complex amplitudes (we don't need the phase) |Ae^{iwt}| = A
        amplitudes = np.abs(transformed_array)

        # copy of amplitudes to modify them (filter). we do this to keep amplitudes array 
        # untouched if we want to compare both later
        filtered_amplitudes = transformed_array.copy()

        # set to zero where we are over the cutoff frequency
        filtered_amplitudes[(np.abs(freqs) > cutoff_freq)] = 0
        # regenerate filtered signal
        filtered_array = fft.ifft(filtered_amplitudes)


        ## potting for debugging
        # plt.plot(freqs, amplitudes)
        # plt.plot(freqs, filtered_amplitudes)
        # plt.show()

        # update Cage object
        self.data = np.abs(filtered_array)
