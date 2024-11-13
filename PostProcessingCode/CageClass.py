from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt
import scipy.fft as fft
from scipy.signal import find_peaks

class Cage():

    def __init__(self, data_list: list, time: np.ndarray) -> Cage:
        self.raw_time = time # kepts in memory the raw data
        self.time = self.raw_time # might change

        array = np.array(data_list)
        self.raw_data = np.sum(array, axis=0) # kepts in memory the raw data
        self.data = self.raw_data # will change


    def reset_data(self):
        """
        Resets the data to the raw data.
        """
        self.data = self.raw_data
        self.time = self.raw_time


    def when_mouse_is_in(self):
        """Identifies the moment when the mouse is in the cage.

        Data acquisition starts with a plateau at 0g. When the mouse is in, the mean weight goes up.
        Creates two class variables with the time and the weight data when the mouse is in.
        """
        length = 5
        for i in range(self.data.shape[0]):
            mean = np.mean(self.data[i: i+length])
            if np.isclose(mean, 0, atol=1): # + or - one gram is still considered at 0g.
                i += length
            else:
                break
        self.time_when_mouse_is_in = self.time[i+length]
        self.weight_when_mouse_is_in = self.data[i+length]


    def remove_outliers(self, upper_threshold: float=45, change_tol: float=5):
        """
        Data can be more cleaned up by removing outliers, first with a simple threshold, then by verifying if a data point
        """

        # rough filtering by removing any values over the specified threshold
        # get all index where condition is met
        under_threshold_index = np.argwhere(np.abs(self.data) < upper_threshold)
        self.data = self.data[under_threshold_index].squeeze()
        self.time = self.time[under_threshold_index.squeeze()]

        # removing all values of spontaneous peaks
        # looping on all values
        mean = np.mean(self.data)
        outliers_index = []
        for i, value in enumerate(self.data):
            # do not consider the first and last data points
            if i == 0 or i == self.data.shape[0]-1:
                continue

            # if data before and after are very different, remove the point
            data_before = self.data[i-1]
            data_after = self.data[i+1]
            if abs(value - data_before) > change_tol and abs(value - data_after) > change_tol:
                outliers_index.append(i)

        # delete data points considered as outliers
        self.data = np.delete(self.data, outliers_index)
        self.time = np.delete(self.time, outliers_index)

    def find_dynamic_threshold(self, time_window_length: float):
        """NOT IMPLEMENTED

        This function could be use to calculate a threshold identifying what is considered
        "empty". It was found that using a threshold to eleminate data points near zero before using
        a convolutional filter works pretty well. The determination of this threshold can be simple if a value like 5g is used
        for the whole experiment. But, using a more cleverly chosen value can help with the smoothing of the signal.
        Single value threshold forces us to be safe since it needs always work (implying a less efficient approach). A dynamic threshold could help us
        discrminate more points before convolutional filtering and gain in precision (we would avoid ups and downs more efficiently).

        Suggested aproach: Calculate the mean value over a fixed time interval (like 1 hour). Use a fraction of this mean as your
        threshold (like 1/4). Mean value should always be around the weight of the mouse, so a fraction is a good guess for our threshold.
        We can repeat that for the next time interval to have a dynamic threshold following the general tendency of the weight. Time interval length
        should be chosen to match how fast weight is expected to change.

        Looping on all time intervals to calculate the threshold for each of them. Store them in an array to have the dynamic behaviour of our threshold.
        Give this array to another function that would remove all data points under the threshold for all time intervals.

        Arguments:
            - time_window_length: length in hours of the time window used
        """
        pass


    def remove_values_under_threshold(self, threshold: float=5):
        """ Remove every data points under a specified threshold

        Arguments:
            - threshold: specified threshold. default is 5.
        """
        # get all index where condition is met
        # squeeze() ensures that index array is one-dimensional
        positive_values_index = np.argwhere(self.data >= threshold).squeeze()
        # keep only data_points where condition is met
        self.data = self.data[positive_values_index]
        self.time = self.time[positive_values_index]

        # shift time back to zero
        self.time -= self.time[0]


    def convolution_filter_with_padding_edge(self, length: int=10, iteration: int=1, kernel_type='average'):
        """ Convolution filter on the signal. This filter is meant to smooth up the signal
        and remove outliers without any threshold. The edges are padded to correct for boundary effects.

        Arguments:
            - length: length of the kernel to convolve on signal. default is 10
            - iteration: number of consecutive convolutions to do. default is 1
            - kernel_type: distribution of weight function of the kernel array. default is a simple average. (every value is the same)
        """
        # raise an error if number of iteration is not possible
        if iteration <= 0:
            raise ValueError("Number of iteration cannot be under 1")

        # for now, this statement is useless but shows an approriate structure
        # for more kernel types, an example for gaussian is below
        input_data_length = self.data.shape[0]

        if kernel_type == 'average':
            # create an array of approriate length of 1/length at every position
            # this is the specific case of moving average
            filtering_array = np.ones(length)/length
            # doing the convolution the specified number of times
            for i in range(iteration):
                # 'same' arg is used to get an array of same size as self.data. Boundary effects are corrected with edge padding. The extra data on the edges are removed after the convolution with slicing.
                pad_width = len(filtering_array) // 2
                padded_data = np.pad(self.data, pad_width, mode='mean')
                self.data = np.convolve(padded_data, filtering_array, mode='same')
                self.data = self.data[int(length/2):int(length/2+input_data_length)]

        if kernel_type == "high-pass" :
            filtering_array = np.array([-1, -1, 0, 0, 0, 0, 0, 1, 1])  # High-pass filter
            # doing the convolution the specified number of times
            for i in range(iteration):
                # 'same' arg is used to get an array of same size as self.data. Boundary effects are corrected with edge padding. The extra data on the edges are removed after the convolution with slicing.
                pad_width = len(filtering_array) // 2
                padded_data = np.pad(self.data, pad_width, mode='mean')
                self.data = np.convolve(padded_data, filtering_array, mode='same')
                self.data = self.data[int(length/2):int(length/2+input_data_length)]



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

        # update Cage object
        self.data = np.abs(filtered_array)


    def compute_mean_data(self, smooth_level: int=3):
        """
        Computes the mean of the weight to smoothen it maximally and only see the tendency of the weight change over time.
        First removes all data points under 10 g.
        Then convolves the data using 600 points.

        smooth_level : The higher, the smoother. Actively, it changes the number of iterations of convolution.
        """
        self.remove_values_under_threshold(10)
        self.remove_outliers()
        self.convolution_filter_with_padding_edge(length=600, iteration=smooth_level)


    def compute_hanging(self, threshold: int=10, bins: float=0.5, first_day: bool=False, produce_graph: bool=False):
        """
        Hanging is when the weight data drops to 0g for more than 1 second.
        A convolution is done on a small window length (15 points) to smooth the data just enough to identify the moments when the weight data drops to 0g.
        A threshold is set so that all weight data going under the threshold in the convoluted weight data is when the mouse is hanging.
        If it is the first day, then the first weight data are at 0g, but they are not hanging data, as the mouse is not in yet.
        The bins variable indicates how you want the hanging frequency to be computed. 0.5 is 30 min, 1 is one hour.
        """
        self.reset_data()
        self.remove_outliers()
        self.convolution_filter_with_padding_edge(length=15)
        conv_data = self.data
        conv_time = self.time
        self.convolution_filter_with_padding_edge(kernel_type="high-pass")

        hanging_indices = find_peaks(abs(cage.data), height=15, distance=10)[0]
        start_indices = []
        end_indices = []
        i = 0
        while i in range(hanging_indices.shape[0]-1):
            start = hanging_indices[i]
            end = hanging_indices[i+1]

            if cage.time[end] - cage.time[start] > 180/60/60:
            # if the hanging event lasts for more than 3 minutes, do not consider
                i += 1

            elif cage.time[end] - cage.time[start] < 1/60/60:
            # if the hanging event lasts less than a second, do not consider
                i += 1

            else:
            # verifies if the selected range has at least one second of weight measurement under 10g. If so, it is indeed hanging. Otherwise, it is not hanging.
                under_10_indices = np.where(conv_data[start:end] < 10)[0]

                if under_10_indices.shape[0] > 1/60/60:
                    start_indices.append(start)
                    end_indices.append(end)
                    i += 2
                else:
                    i += 1


        if first_day:
            # remove indices that are under the index when the mouse is in
            self.when_mouse_is_in()
            index_when_mouse_is_in = np.where(self.time == self.time_when_mouse_is_in)[0][0]
            start_indices = start_indices[start_indices > index_when_mouse_is_in]
            end_indices = end_indices[end_indices > index_when_mouse_is_in]

        # gets the times when the mouse starts and ends hanging
        start_hanging = self.time[start_indices]
        end_hanging = self.time[end_indices]

        self.total_time_hanging = np.sum(np.subtract(end_hanging, start_hanging))

        # computes hanging frequency
        self.hanging_frequency = []
        for i in np.arange(bins, self.time[-1], bins):
            if i == bins:
                hanging_times = np.where(start_hanging < i)[0].shape[0]
                self.hanging_frequency.append(hanging_times)
            else:
                hanging_times = np.where((start_hanging < i) & (start_hanging > i - bins))[0].shape[0]
                self.hanging_frequency.append(hanging_times)
        self.hanging_frequency = np.array(self.hanging_frequency)

        if produce_graph:
            plt.figure(figsize=(13,7))
            for i in range(start_hanging.shape[0]):
                if i == 0:
                    plt.fill_between(self.raw_time, np.amax(self.raw_data), where=(self.raw_time >= start_hanging[i]) & (self.raw_time <= end_hanging[i]), color="red", alpha=0.7, label="Hanging - Data analysis")
                else:
                    plt.fill_between(self.raw_time, np.amax(self.raw_data), where=(self.raw_time >= start_hanging[i]) & (self.raw_time <= end_hanging[i]), color="red", alpha=0.7)

            plt.plot(self.raw_time, self.raw_data, color="k", label="Not filtered")
            plt.plot(self.time, self.data, label="Convoluted")
            plt.legend()
            plt.xlabel("Time [hour]", fontsize=20)
            plt.ylabel("Fake weight data [g]", fontsize=20)
            plt.show()


