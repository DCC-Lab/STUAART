import numpy as np
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from matplotlib.cm import get_cmap
import scipy.fft as fft
import pandas as pd
from scipy.signal import find_peaks
from DataClass import Data
from itertools import groupby
from datetime import datetime
from sklearn.decomposition import PCA
import os 

class Cage():

    def __init__(self, directory:str, filename:str, number_of_scales:int, real_data=None):
        self.directory = directory
        self.filename = filename
        self.number_of_scales = number_of_scales
        self.real_data = real_data

        self.threshold = [-10, 40] # min and max weight thresholds [g]

        self.get_data_and_timepoints()

        self.format_data_per_scale()

        self.colors = ["b", "r", "g", "c", "m"]

    @staticmethod
    def format_time_in_hours(time_array):
        """
        Some data are formatted as ["h:m:s", "h:m:s", ...] and have to be converted in an hours, floats.
        """
        time = []
        for i in range(time_array.shape[0]):
            h, m, s = time_array[i].split(':')
            time.append((int(h) * 3600 + int(m) * 60 + int(s))/3600)
        return np.array(time)

    @staticmethod
    def format_seconds_in_hours(time_array):
        """
        Some data are formatted as ["20s", "15s", ...] and have to be converted in an hours, floats.
        """
        time = []
        for i in range(time_array.shape[0]):
            s = time_array[i][:-1]
            time.append(int(s)/3600)
        return np.array(time)

    def get_data_and_timepoints(self):
        """
        Get .csv data of time and weight measurements per scale and overall from the directory and the filename. 
        """
        all_data = np.array(pd.read_csv(self.directory+self.filename))
        data_list = []

        for i in range(self.number_of_scales+1):
            if i == 0:
                time = all_data[:,i]/(1000 * 60 * 60) # time in hours
            else:
                data = Data(all_data[:,i], time)
                data_list.append(Data(all_data[:,i], time))

        self.raw_time = time # this variable kepts in memory the raw data
        self.time = self.raw_time.copy() # this variable will change 
        self.raw_data_per_scale = data_list # this variable kepts in memory the raw data
        self.data_per_scale = np.array(self.raw_data_per_scale).copy() # this variable will change
        self.sum_data_over_time()
        self.data = self.raw_data.copy() # this variable will change


    def sum_data_over_time(self):
        """
        Sum data per time point to obtain the weight measurement over time of the whole cage system (and not only per scale).
        """
        self.raw_data = np.sum(self.raw_data_per_scale, axis=0) # this variable kepts in memory the raw data


    def reset_data(self):
        """
        Resets the data to the raw data.
        """
        self.data = self.raw_data.copy()
        self.time = self.raw_time.copy()
        self.data_per_scale = np.array(self.raw_data_per_scale).copy()


    def format_data_per_scale(self):
        """
        Format weight data per scale by removing extreme outliers, finding the baseline shift and correcting for it. 
        """
        for i in range(self.number_of_scales):
            self.raw_data_per_scale[i].set_outliers_threshold(self.threshold)
            self.raw_data_per_scale[i].shift_data_to_zero()
            self.raw_data_per_scale[i].remove_outliers()
            self.raw_data_per_scale[i].find_baseline()
            self.raw_data_per_scale[i].subtract_baseline()


    def plot_data_per_scale(self, is_saved=False):
        """
        Plots the data per scale. 
        """

        # fig, axs = plt.subplots(self.number_of_scales, 1, figsize=(13,7))
        print(self.data_per_scale, self.data_per_scale.shape, type(self.data_per_scale), self.data_per_scale.dtype)
        for i in range(self.number_of_scales):
            self.data_per_scale[i].plot_signal(threshold=False, peaks=False, baseline=True, color=self.colors[i], is_saved=is_saved, real_data=self.real_data)


    def when_mouse_is_in(self):
        """
        Identifies the moment when the mouse is in the cage. 
        Data acquisition starts with a plateau at 0g. When the mouse is in, the mean weight goes up.
        Creates two class variables with the time and the weight data when the mouse is in. 
        """
        length = 80
        for i in range(self.data.shape[0]):
            mean = np.mean(self.data[i: i+length])
            if np.isclose(mean, 0, atol=3): # + or - one gram is still considered at 0g. 
                i += length
            else:
                break
        self.time_when_mouse_is_in = self.time[i+length]
        self.weight_when_mouse_is_in = self.data[i+length]


    def remove_outliers(self, upper_threshold: float=45, change_tolerance: float=5):
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
            if abs(value - data_before) > change_tolerance and abs(value - data_after) > change_tolerance:
                outliers_index.append(i)
        # delete data points considered as outliers
        self.data = np.delete(self.data, outliers_index)
        self.time = np.delete(self.time, outliers_index)



    def find_dynamic_threshold(self, time_window_length: float):
        """ 
        NOT IMPLEMENTED
        
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



    def convolution_filter_with_padding_edge_per_scale(self, length: int=10, iteration: int=1, kernel_type='average'):
        """ Convolution filter on the individual signal of each scale. This filter is meant to smooth up the signal
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
        input_data_length = self.data_per_scale[0].shape[0]

        if kernel_type == 'average':
            # create an array of approriate length of 1/length at every position
            # this is the specific case of moving average
            filtering_array = np.ones(length)/length
            # doing the convolution the specified number of times
            for i in range(iteration):
                # 'same' arg is used to get an array of same size as self.data. Boundary effects are corrected with edge padding. The extra data on the edges are removed after the convolution with slicing. 
                pad_width = len(filtering_array) // 2
                for n in range(self.number_of_scales):
                    padded_data = np.pad(self.data_per_scale[n], pad_width, mode='mean')
                    data = np.convolve(padded_data, filtering_array, mode='same')
                    data = data[int(length/2):int(length/2+input_data_length)]
                    self.data_per_scale[n] = data

        if kernel_type == "high-pass" :
            filtering_array = np.array([-1, -1, 0, 0, 0, 0, 0, 1, 1])  # High-pass filter
            # doing the convolution the specified number of times
            for i in range(iteration):
                # 'same' arg is used to get an array of same size as self.data. Boundary effects are corrected with edge padding. The extra data on the edges are removed after the convolution with slicing. 
                pad_width = len(filtering_array) // 2
                for n in range(self.number_of_scales):
                    padded_data = np.pad(self.data_per_scale[n], pad_width, mode='mean')
                    data = np.convolve(padded_data, filtering_array, mode='same')
                    data = data[int(length/2):int(length/2+input_data_length)]
                    self.data_per_scale[n] = data[pad_width:]



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

        hanging_indices = find_peaks(abs(self.data), height=10, distance=10)[0]
        start_indices = []
        end_indices = []
        self.hanging_moments = np.zeros(shape=self.time.shape)
        i = 0
        while i in range(hanging_indices.shape[0]-1):
            start = hanging_indices[i]
            end = hanging_indices[i+1]

            if self.time[end] - self.time[start] > 180/60/60:
            # if the hanging event lasts for more than 3 minutes, do not consider
                i += 1

            elif self.time[end] - self.time[start] < 1/60/60:
            # if the hanging event lasts less than a second, do not consider
                i += 1

            else:
            # verifies if the selected range has at least one second of weight measurement under 10g. If so, it is indeed hanging. Otherwise, it is not hanging. 
                under_10_indices = np.where(conv_data[start:end] < threshold)[0]

                if under_10_indices.shape[0] > 1/60/60:
                    start_indices.append(start)
                    end_indices.append(end)
                    self.hanging_moments[start:end] = 1 
                    i += 2
                else:
                    i += 1

        start_indices = np.array(start_indices)
        end_indices = np.array(end_indices)
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
            plt.ylabel("Weight data [g]", fontsize=20)
            plt.show()



    def compute_location_on_scale(self, bins:float=0.5, first_day: bool=False, produce_graph: bool=False, is_saved:bool=False):
        """
        Time series of weight per individual scale are used to identify where the mouse is over time. 
        After a simple average convolution, the mouse is identified are present on a scale if a non-zero weight is measured (between -2 and 2g). Otherwise, the mouse is not on the scale. 
        The mouse can be on multiple scales at a time. 
        Extra parameters are calculated, such as the number of entries, the relative time spent and the presence bouts per time bin, defined by bins. 
        """
        self.reset_data()
        self.convolution_filter_with_padding_edge_per_scale(length=10)

        indicator_on_scale = np.ones(shape=self.data_per_scale.shape)

        if first_day:
            # remove indices that are under the index when the mouse is in 
            self.when_mouse_is_in()
            index_when_mouse_is_in = np.where(self.time == self.time_when_mouse_is_in)[0][0]
            indicator_on_scale[:,index_when_mouse_is_in] = 0

        self.presence_indicator_per_scale = indicator_on_scale
        for n in range(self.number_of_scales):
            index_data_around_zero = np.where((self.data_per_scale[n] > -2)&(self.data_per_scale[n] < 2))[0]
            self.presence_indicator_per_scale[n, index_data_around_zero] = 0

        # Compute number of entries per bin, average time spent per bin per scale and relative time spent per bin per scale
        number_of_entries_per_bin_per_scale = []
        average_time_spent_per_bin_on_scale = []
        std_time_spent_per_bin_on_scale = []
        relative_time_spent_per_bin_per_scale = []

        for n in range(self.number_of_scales):
            number_of_entries = []
            average_time_spent = []
            std_time_spent = []
            relative_time = []
            for j in np.arange(bins, self.time[-1], bins):
                indices_in_period = np.where((self.time > j-bins) & (self.time < j))[0]
                num_entries = sum(1 for key, group in groupby(self.presence_indicator_per_scale[n][indices_in_period[0]:indices_in_period[-1]]) if key == 1)
                lengths_per_moment_on_scale_in_seconds = [len(list(group)) for key, group in groupby(self.presence_indicator_per_scale[n][indices_in_period[0]:indices_in_period[-1]]) if key == 1]
                lengths_per_moment_on_scale_in_seconds = np.array(lengths_per_moment_on_scale_in_seconds) * (self.time[1]-self.time[0])
                rel_time = np.sum(lengths_per_moment_on_scale_in_seconds)/bins

                number_of_entries.append(num_entries)
                average_time_spent.append(np.mean(lengths_per_moment_on_scale_in_seconds))
                std_time_spent.append(np.std(lengths_per_moment_on_scale_in_seconds))
                relative_time.append(rel_time)

            number_of_entries_per_bin_per_scale.append(np.array(number_of_entries))
            average_time_spent_per_bin_on_scale.append(np.array(average_time_spent))
            relative_time_spent_per_bin_per_scale.append(np.array(relative_time))
            std_time_spent_per_bin_on_scale.append(std_time_spent)

        self.number_of_entries_per_bin_per_scale = np.array(number_of_entries_per_bin_per_scale)
        self.average_time_spent_per_bin_per_scale = np.array(average_time_spent_per_bin_on_scale)
        self.std_time_sent_per_bin_per_scale = np.array(std_time_spent_per_bin_on_scale)
        self.relative_time_sent_per_bin_per_scale = np.array(relative_time_spent_per_bin_per_scale)

        if produce_graph:
            fig, axs = plt.subplots(nrows=self.number_of_scales, ncols=1, figsize=(13,7))
            for n in range(self.number_of_scales):
                axs[n].plot(self.raw_time, self.raw_data_per_scale[n], color=self.colors[n])
                axs[n].plot(self.raw_time, self.presence_indicator_per_scale[n], color="k")
                axs[n].fill_between(self.raw_time, np.amax(self.raw_data_per_scale[n]), where= self.presence_indicator_per_scale[n] == 1, color=self.colors[n], alpha=0.5)

            plt.xlabel("Time [h]", fontsize=16)
            axs[0].legend()
            axs[0].set_ylabel("Weight [g]", fontsize=16)
            axs[1].set_ylabel("Weight [g]", fontsize=16)
            axs[2].set_ylabel("Weight [g]", fontsize=16)
            fig.tight_layout()

            if is_saved:
                today = datetime.today().strftime('%Y-%m-%d')
                plt.savefig(self.directory+today+"-Time_series_with_location_indicator-"+str(bins)+".png", format="png", dpi=600)
            plt.show()

            fig, axs = plt.subplots(ncols=1, nrows=3, figsize=(15,9))
            x = np.arange(bins, self.time[-1], bins)
            i = 0
            for n in range(self.number_of_scales):
                axs[0].bar(x+i, self.number_of_entries_per_bin_per_scale[n], color=self.colors[n], width=0.1, alpha=0.75, label="Scale "+str(n))
                axs[1].bar(x+i, self.average_time_spent_per_bin_per_scale[n], yerr=self.std_time_sent_per_bin_per_scale[n], error_kw={'ecolor':self.colors[n] ,'elinewidth': 3,'linestyle': '--','capthick': 5}, color=self.colors[n], width=0.1, alpha=0.75)
                axs[2].bar(x+i, self.relative_time_sent_per_bin_per_scale[n], color=self.colors[n], width=0.1, alpha=0.75)
                i += 0.12

            plt.xlabel("Time bins [h]", fontsize=16)
            axs[0].legend(fontsize=16)
            axs[0].set_ylabel("Number of entries", fontsize=16)
            axs[1].set_ylabel("Average time spent per \n presence bout [h]", fontsize=16)
            axs[2].set_ylabel("Relative time [h/h]", fontsize=16)
            axs[0].set_ylim(bottom=0)
            axs[1].set_ylim(bottom=0)
            axs[2].set_ylim(bottom=0)
            axs[0].set_xticks(x+0.12, labels=x, fontsize=13)
            axs[1].set_xticks(x+0.12, labels=x, fontsize=13)
            axs[2].set_xticks(x+0.12, labels=x, fontsize=13)
            fig.tight_layout()
            if is_saved:
                plt.savefig(self.directory+today+"-Entries_Averagetimeperbout_Relativetime_"+str(bins)+".png", format="png", dpi=600, transparent=True)
            plt.show()


    def compute_location_on_scale_accuracy(self, directory_ground_truth:str, filenames:list, delay_in_seconds:int=0, evaluate_only_between_these_hours:list=None, bins:float=0.5, first_day: bool=False, produce_graph: bool=False, is_saved:bool=False):
        """
        This function needs ground truth data, potentially done by watching a video while recording the weight data, to compare the ground truth (video, manual annotations) with the identification of location with the weight data. 
        Data is formatted to obtain one numpy array per scale having the size of the raw_time data. Elements are 0s when the mouse is not on the scale and 1s when the mouse is on the scale. 
        These numpy arrays of 0s and 1s are compared together. 
        A plot of the time series of weight per scale is done at the end with the ground truth moments in grey. 
        """
        self.compute_location_on_scale(bins=bins, first_day=first_day)

        if evaluate_only_between_these_hours is not None:
            indices_only_between_these_hours = np.where((self.raw_time > evaluate_only_between_these_hours[0]) & (self.raw_time < evaluate_only_between_these_hours[1]))[0]
            time = self.raw_time[indices_only_between_these_hours[:-1]]
            presence_indicator_per_scale = self.presence_indicator_per_scale[:,indices_only_between_these_hours[0]:indices_only_between_these_hours[-1]]
            raw_data_per_scale = []
            for n in range(self.number_of_scales):
                raw_data_per_scale.append(self.raw_data_per_scale[n][indices_only_between_these_hours[0]:indices_only_between_these_hours[-1]])
            raw_data_per_scale = np.array(raw_data_per_scale)
        else:
            time = self.raw_time
            presence_indicator_per_scale = self.presence_indicator_per_scale
            raw_data_per_scale = self.raw_data_per_scale


        # get start times and the delay, the time the event happens, of all scales
        start_times_in_hours = []
        delays_in_hours = []
        for file in filenames:
            data_location_scale = pd.read_csv(directory_ground_truth + file) # get the raw data
            start_times_scale = data_location_scale["Start"].to_numpy() # get the start times
            delay_scale = data_location_scale["Delta"].to_numpy() # get the delays 

            start_times_scale_hours = self.format_time_in_hours(start_times_scale) # format the start times in hours, floats 
            delay_scale_hours = self.format_seconds_in_hours(delay_scale) # format the delays in hours, float

            start_times_scale_hours = start_times_scale_hours - (delay_in_seconds/3600) # add delay between video and weight data measurements
            start_times_in_hours.append(start_times_scale_hours) 
            delays_in_hours.append(delay_scale_hours)

        # produce a numpy array indicating when the mouse is on the scale.
        # 0s are when the mouse is NOT on the scale and 1s is when the mouse is on the scale
        on_scales_truth_indicator = np.zeros(shape=(3, time.shape[0]))
        for i in range(len(start_times_in_hours[0])):
            indices_during_event = np.where((time > start_times_in_hours[0][i]) & (time < start_times_in_hours[0][i]+delays_in_hours[0][i]))[0]
            on_scales_truth_indicator[0, indices_during_event] = 1

        for i in range(len(start_times_in_hours[1])):
            indices_during_event = np.where((time > start_times_in_hours[1][i]) & (time < start_times_in_hours[1][i]+delays_in_hours[1][i]))[0]
            on_scales_truth_indicator[1, indices_during_event] = 1

        for i in range(len(start_times_in_hours[2])):
            indices_during_event = np.where((time > start_times_in_hours[2][i]) & (time < start_times_in_hours[2][i]+delays_in_hours[2][i]))[0]
            on_scales_truth_indicator[2, indices_during_event] = 1

        for i in range(len(start_times_in_hours[3])):
            indices_during_event = np.where((time > start_times_in_hours[3][i]) & (time < start_times_in_hours[3][i]+delays_in_hours[3][i]))[0]
            on_scales_truth_indicator[0, indices_during_event] = 1
            on_scales_truth_indicator[1, indices_during_event] = 1

        for i in range(len(start_times_in_hours[4])):
            indices_during_event = np.where((time > start_times_in_hours[4][i]) & (time < start_times_in_hours[4][i]+delays_in_hours[4][i]))[0]
            on_scales_truth_indicator[1, indices_during_event] = 1
            on_scales_truth_indicator[2, indices_during_event] = 1

        # compute total time accuracy by counting the numbers of 1s in the ground truth and comparing to the total number of 1s in the location indicators found in weight data
        total_error_per_scale = []
        for n in range(self.number_of_scales):
            indices_presence_truth = np.where(on_scales_truth_indicator[n] == 1)[0]
            total_number_of_presence_indices_truth = indices_presence_truth.shape[0]

            indices_presence = np.where(presence_indicator_per_scale[n] == 1)[0]
            total_number_of_presence = indices_presence.shape[0]
            total_error = ((total_number_of_presence_indices_truth/time.shape[0])-(total_number_of_presence/time.shape[0]))*(time[1]-time[0])*3600*1000
            total_error_per_scale.append(total_error)
            print(f"Scale {n+1} : Total error of {total_error} ms.")

        # compute the precision error by comparing each location event. 
        mean_precision_per_scale = []
        std_precision_per_scale = []
        for n in range(self.number_of_scales):
            indices_presence_starts_truth = np.where(np.diff(np.pad(on_scales_truth_indicator[n], (1, 1), 'constant')) == 1)[0] # identify when all 1s start
            indices_presence_ends_truth = np.where(np.diff(np.pad(on_scales_truth_indicator[n], (1, 1), 'constant')) == -1)[0] # identify when all 1s end
            length_presence_events_truth = indices_presence_ends_truth - indices_presence_starts_truth # get the number of 1s per presence event

            indices_presence_starts = np.where(np.diff(np.pad(presence_indicator_per_scale[n], (1, 1), 'constant')) == 1)[0] # identify when all 1s start
            indices_presence_ends = np.where(np.diff(np.pad(presence_indicator_per_scale[n], (1, 1), 'constant')) == -1)[0] # identify when all 1s end
            length_presence_events = indices_presence_ends - indices_presence_starts # get the number of 1s per presence event

            # Make both arrays have the same number of groups by padding with zeros
            max_length = max(len(length_presence_events_truth), len(length_presence_events))
            length_presence_events_truth = np.pad(length_presence_events_truth, (0, max_length - len(length_presence_events_truth)), 'constant')
            length_presence_events = np.pad(length_presence_events, (0, max_length - len(length_presence_events)), 'constant')

            precision_per_presence_event = np.abs(length_presence_events_truth - length_presence_events)
            mean_precision = np.mean(precision_per_presence_event)*(time[1]-time[0])*3600
            std_precision = np.std(precision_per_presence_event)*(time[1]-time[0])*3600
            mean_precision_per_scale.append(mean_precision)
            std_precision_per_scale.append(std_precision)

            print(f"Unprecision : {mean_precision} + {std_precision} s")

        fig, axs = plt.subplots(nrows=self.number_of_scales, ncols=1, figsize=(13,7))
        for n in range(self.number_of_scales):
            axs[n].plot(time, raw_data_per_scale[n], color=self.colors[n])
            axs[n].plot(time, presence_indicator_per_scale[n], color="k")
            axs[n].fill_between(time, np.amax(raw_data_per_scale[n]), where= presence_indicator_per_scale[n] == 1, color=self.colors[n], alpha=0.5)
            axs[n].fill_between(time, 50, where=on_scales_truth_indicator[n] == 1, color="grey", alpha=0.5)
            axs[n].set_title("Total error : {0:.2f} ms and event precision : {1:.2f} +- {2:.2f} s".format(total_error_per_scale[n], mean_precision_per_scale[n], std_precision_per_scale[n]))

        plt.xlabel("Time [h]", fontsize=16)
        axs[0].legend()
        axs[0].set_ylabel("Weight [g]", fontsize=16)
        axs[1].set_ylabel("Weight [g]", fontsize=16)
        axs[2].set_ylabel("Weight [g]", fontsize=16)
        fig.tight_layout()

        if is_saved:
            today = datetime.today().strftime('%Y-%m-%d')
            if evaluate_only_between_these_hours is not None:
                plt.savefig(self.directory+today+"-TotalError_and_EventPrecision"+str(bins)+"-range"+str(evaluate_only_between_these_hours[0])+"to"+str(evaluate_only_between_these_hours[1])+"hours.png", format="png", dpi=600, transparent=True)
            else:
                plt.savefig(self.directory+today+"-TotalError_and_EventPrecision"+str(bins)+".png", format="png", dpi=600, transparent=True)
        plt.show()


    def retreive_indicator_behaviour_data_per_scale(self, directory:str, delay_in_seconds:int, include_not_annotated_data:bool=False):
        """
        Format ground truth data to have indicators of when the behavioural event is happening. 
        0 : when the event is not happening
        1 : when the event is happening
        Produces a dictionnary of indicators per scale of when the behavioural event is happening. 
        """
        filenames = os.listdir(directory)
        behaviour_indicator_per_scale = {}
        for name in filenames:
            data = pd.read_csv(directory + name) # get the raw data
            start_times_scale = data["Start"].to_numpy() # get the start times
            delay_scale = data["Delta"].to_numpy() # get the delays 
            scale_indicator = data["On scale"].to_numpy()
            start_times_scale_hours = self.format_time_in_hours(start_times_scale) # format the start times in hours, floats 
            delay_scale_hours = self.format_seconds_in_hours(delay_scale) # format the delays in hours, float
            start_times_scale_hours = start_times_scale_hours - (delay_in_seconds/3600) # add delay between video and weight data measurements

            # here, we make an array of the size of self.raw_time, where 0 is when there is no grooming and 1 is when there is grooming
            event_indicator = np.zeros(shape=(self.number_of_scales, self.raw_time.shape[0]))
            for i in range(start_times_scale_hours.shape[0]):
                indices_during_event = np.where((self.raw_time > start_times_scale_hours[i]) & (self.raw_time < start_times_scale_hours[i]+delay_scale_hours[i]))[0]
                event_indicator[int(scale_indicator[i])-1][indices_during_event] = 1

            position = name.find("-")
            behaviour_name = name[:position]
            behaviour_indicator_per_scale[behaviour_name] = event_indicator

        if include_not_annotated_data:
            indicator_when_not_doing_behaviour = np.zeros(shape=(self.number_of_scales, self.raw_time.shape[0])) 
            for key in behaviour_indicator_per_scale.keys():
                indicators = behaviour_indicator_per_scale[key]
                for n in range(self.number_of_scales):
                    indicator_when_not_doing_behaviour = np.where((indicator_when_not_doing_behaviour == 0) & (indicators != 0), 1, indicator_when_not_doing_behaviour)
            behaviour_indicator_per_scale["Not labelled"] = indicator_when_not_doing_behaviour
        
        self.behaviour_indicator_per_scale = behaviour_indicator_per_scale


    def retreive_indicator_behaviour_data(self, directory:str, delay_in_seconds:int):
        """
        Format ground truth data to have indicators of when the behavioural event is happening. 
        0 : when the event is not happening
        1 : when the event is happening
        Produces a dictionnary of indicators per scale of when the behavioural event is happening. 
        """
        self.retreive_indicator_behaviour_data_per_scale(directory=directory, delay_in_seconds=delay_in_seconds)
        behaviour_indicator = {}
        for key in self.behaviour_indicator_per_scale.keys():
            behaviour_indicator[key] = np.sum(self.behaviour_indicator_per_scale[key], axis=0)
        
        self.behaviour_indicator = behaviour_indicator



    def produce_behaviour_dataset_per_scale(self, directory:str, delay_in_seconds:int):
        """
        Uses groung truth annotations of all different behaviours and format in 2 second events.
        Returns:
            - the weight measurements of each 10 datapoints (shape = (-1,10))
            - the scale indicator on which this moments is measured (shape = -1)
            - the targets, same as the labels, but int instead of str
            - the labels of different behaviours (shape= -1)
        """
        self.retreive_indicator_behaviour_data_per_scale(directory=directory, delay_in_seconds=delay_in_seconds)
        i = 0
        two_second_data = np.array([])
        on_scale = np.array([])
        targets = np.array([])
        labels = np.array([])
        for key in self.behaviour_indicator_per_scale.keys():
            indicator = self.behaviour_indicator_per_scale[key]
            for n in range(self.number_of_scales):
                indices = np.where(indicator[n] == 1)[0]
                weight_truth = self.raw_data_per_scale[n][indices]
                new_size = (weight_truth.size // 190) * 190 # 190 data points is about 2 seconds at 80 Hz
                trim_weight_truth = weight_truth[:new_size]
                trim_weight_truth = np.reshape(trim_weight_truth, (-1, 190))
                two_second_data = np.array(list(two_second_data) + list(trim_weight_truth))
                on_scale = np.array(list(on_scale) + list(np.repeat(n, trim_weight_truth.shape[0])))
                targets = np.array(list(targets) + list(np.repeat(i, trim_weight_truth.shape[0])))
                labels = np.array(list(labels) + list(np.repeat(key, trim_weight_truth.shape[0])))
            i += 1

        return two_second_data, on_scale, targets, labels


    def produce_behaviour_dataset(self, directory:str, delay_in_seconds:int):
        """
        Uses groung truth annotations of all different behaviours and format in 2 second events, which is approximately 10 datapoints. 
        Returns:
            - the weight measurements of each 10 datapoints (shape = (-1,10))
            - the scale indicator on which this moments is measured (shape = -1)
            - the targets, same as the labels, but int instead of str
            - the labels of different behaviours (shape= -1)
        """
        self.retreive_indicator_behaviour_data(directory=directory, delay_in_seconds=delay_in_seconds)
        
        i = 0
        two_second_data = np.array([])
        targets = np.array([])
        labels = np.array([])
        for key in self.behaviour_indicator.keys():
            indicator = self.behaviour_indicator[key]
            indices = np.where(indicator == 1)[0]
            weight_truth = self.raw_data[indices]
            new_size = (weight_truth.size // 800) * 800 # 190 data points is about 2 seconds at 80 Hz
            trim_weight_truth = weight_truth[:new_size]
            trim_weight_truth = np.reshape(trim_weight_truth, (-1, 800))
            two_second_data = np.array(list(two_second_data) + list(trim_weight_truth))
            targets = np.array(list(targets) + list(np.repeat(i, trim_weight_truth.shape[0])))
            labels = np.array(list(labels) + list(np.repeat(key, trim_weight_truth.shape[0])))
            i += 1

        return two_second_data, targets, labels



    def pca(self, dataset, number_of_PCs:int, targets, labels, on_scale, PCs_to_plot=[0,1,2], label_per_scale:bool=False):
        """
        Performs PCA on dataset. 
        number_of_PCs: number of PCs for the PCA.
        targets: list of the length of the number of samples in the dataset. Identifies the group of each sample with ints
        labels: list of the length of the number of samples in the dataset. Identifies the group of each sample with an actual label, str. 
        on_scale: list of the length of the number of samples in the dataset. Identifies on which scale this behaviour was done. 
        PCs_to_plot: Defines the axes of the plot in PCA space. 
        plot_per_scale: Defines if the scatter plot of the dataset in PCA space is labeled per scale or per labels. 
        """
        # 1 : Plot data in PCA space 
        pca = PCA(n_components=number_of_PCs)
        fit = pca.fit(dataset)
        projected_data = pca.transform(dataset)
        eigenvalues = fit.explained_variance_ratio_
        eigenvectors = fit.components_

        fig = plt.figure(figsize=(8,8))
        ax = fig.add_subplot(111, projection="3d")

        if label_per_scale:
            colors = np.where(on_scale == 0, "b", "k")
            colors = np.where(on_scale == 1, "r", colors)
            colors = np.where(on_scale == 2, "g", colors)
            x = PCs_to_plot[0]
            y = PCs_to_plot[1]
            z = PCs_to_plot[2]
            ax.scatter(projected_data[:,x], projected_data[:,y], projected_data[:,z], c=colors, alpha=0.4)
            legend_handles = [plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='b', markersize=10, label='Scale 0'), plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='r', markersize=10, label='Scale 1'), plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='g', markersize=10, label='Scale 2')]
            ax.legend(handles=legend_handles, loc='upper right')

        else:
            # setting the colors for each label
            unique_labels = sorted(list(set(labels)))
            cmap = cm.get_cmap("jet", len(unique_labels))  # Use any colormap you like
            color_map = {label: cmap(i) for i, label in enumerate(unique_labels)}
            colors = [color_map[label] for label in labels]

            x = PCs_to_plot[0]
            y = PCs_to_plot[1]
            z = PCs_to_plot[2]
            ax.scatter(projected_data[:,x], projected_data[:,y], projected_data[:,z], c=colors, alpha=0.5)
        
            for label in unique_labels:
                ax.scatter([], [], color=color_map[label], label=label)
            ax.legend(title="Labels behaviour")

        ax.set_xlabel("PC"+str(x) + " ({:.2f} %)".format(eigenvalues[x]*100), fontsize=14)
        ax.set_ylabel("PC"+str(y) + " ({:.2f} %)".format(eigenvalues[y]*100), fontsize=14)
        ax.set_zlabel("PC"+str(z) + " ({:.2f} %)".format(eigenvalues[z]*100), fontsize=14)
        plt.show()

        # 2 : Plot 5 first PCs
        fig = plt.figure(figsize=(8,10))
        colormap = get_cmap('plasma')
        colors = [colormap(i / (10 - 1)) for i in range(10)]
        j = 0
        for i in range(10):
            plt.plot(np.arange(0, dataset.shape[1]), eigenvectors[i] + j, label="PC" + str(i), alpha=0.7, color=colors[i], linewidth=4)
            j -= 1
        plt.legend(ncol=5, loc="upper center", bbox_to_anchor=(0.5, 1.1))
        plt.xlabel("Timestamp", fontsize=15)
        plt.tick_params(left=False, labelleft=False)
        plt.tight_layout()
        plt.show()


    def fft_behaviour(self, dataset, labels, plot:bool=False):
        """
        Plot fft of each sample for each behaviour type in the dataset. 
        """
        fft_of_behaviours = {}
        for label in np.unique(labels):
            indices_of_label = np.where(labels == label)[0]
            data_of_label = dataset[indices_of_label, :]
            fft_of_behaviours[label] = np.fft.fft(data_of_label)
        self.fft_of_behaviours = fft_of_behaviours

        if plot:
            fig, axs = plt.subplots(len(self.fft_of_behaviours.keys()), 1, figsize=(10,10))
            j = 0
            for label in np.unique(labels):
                x = np.arange(0, self.fft_of_behaviours[label].shape[1])/80
                for i in range(self.fft_of_behaviours[label].shape[0]):
                    freqs = np.fft.fftfreq(self.fft_of_behaviours[label][i].shape[0], d=x[1]-x[0])
                    axs[j].plot(freqs[:len(freqs)//2], np.abs(self.fft_of_behaviours[label][i])[:len(freqs)//2], linewidth=1)
                    axs[j].set_title(label)
                    axs[j].set_ylim(0, 600)
                    axs[j].set_xlabel("Frequency [Hz]")
                    axs[j].set_ylabel("Amplitude")
                j += 1

            plt.tight_layout()
            plt.show()










        







































