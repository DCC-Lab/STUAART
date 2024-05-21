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
        """ 
            in progress, not satisfying yet
            i don't know if it will be useful
        """

        # rough filtering by removing any values over the specified threshold
        # get all index where condition is met
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
        mean = np.mean(self.data)
        outliers_index = []
        for i, value in enumerate(self.data):
            # only considering windows that are clear from start
            if i >= window_length:
                # slicing window of interest
                window_array = self.data[i - window_length: i]
                # getting maximum of the window
                maximum_in_window = np.max(window_array)
                # index of maximum
                maximum_index = np.argmax(window_array) + i - window_length

                # calculating the average difference from neighbors
                average_difference = np.sum(maximum_in_window - window_array)/(window_length - 1)
                # difference between maximum in window and average of all signal
                difference_max_with_mean = np.abs(maximum_in_window - mean)

                if average_difference < change_tolerance:
                    outliers_index.append(maximum_index)
        # delete data points considered as outliers
        self.data = np.delete(self.data, outliers_index)
        self.time = np.delete(self.time, outliers_index)

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

    def convolution_filter(self, length: int=10, iteration: int=1, kernel_type='average'):
        """ Convolution filter on the signal. This filter is meant to smooth up the signal
        and remove outliers without any threshold

        Arguments:
            - length: length of the kernel to convolve on signal. default is 10
            - iteration: number of consecutive convolutions to do. default is 1
            - kernel_type: distribution of weight function of the kernel array. default is a simple average. (every value is the same) 
        """
        # raise an error if number of iteration is not possible
        if iteration <= 0:
            raise ValueError("Number of iteration cannot be under 1")

        # for now, this if statement is useless but shows an approriate structure
        # for more kernel types, an example for gaussian is below
        if kernel_type == 'average':
            # create an array of approriate length of 1/length at every position
            # this is the specific case of moving average
            filtering_array = np.ones(length)/length
            # doing the convolution the specified number of times
            for i in range(iteration):
                # 'same' arg is used to get an array of same size as self.data
                # boundaries values are affected since the overlap between the kernel and data
                # is not perfect. These values will later be chopped off.
                self.data = np.convolve(self.data, filtering_array, mode='same')

        # not implemented yet
        # if kernel_type == 'gaussian':
            # filtering_array = a gaussian array
            # self.data = np.convolve(self.data, filtering_array, mode='same')

        # only keeping values not affected by boundary overlap
        self.data = self.data[length: len(self.data) - length]
        self.time = self.time[length: len(self.time) - length]

        # shifting time back to zero
        self.time -= self.time[0]

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
