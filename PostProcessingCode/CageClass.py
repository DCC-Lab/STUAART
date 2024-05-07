import numpy as np
import matplotlib.pyplot as plt
import exceptions
import scipy.fft as fft


class Cage(np.ndarray):
    def __new__(cls, data_list: list, time: np.ndarray):
        array = np.array(data_list)
        cage_array = np.sum(array, axis=0)
        obj = np.asarray(cage_array).view(cls)
        return obj

    def __init__(self, data_list: list, time: np.ndarray):
        super().__init__()
        self.time = time

    def fft_filter(self, cutoff_freq: float=60):
        """ Low pass fft filter on the signal. A simple filter is implemented for now. A sharp cut is done
        at the cutoff frequency in fft spectrum. The signal is regenerated from the modified frequency spectrum.


        Arguments:
            - cutoff_frequency: cutoff frquency of the sharp low pass filter in fft spectrum
        """
        # # this code section is not used for now. uncomment if needed.
        # # generate frequencies array. this could be used to calculate cutoff frequency automatically. not implemented yet

        # get frequencies array [-max_freq, ..., 0, ... max_freq]
        freqs = fft.fftfreq(len(self), self.time[1] - self.time[0])

        # # consider only postive frequencies to calculate cutoff frequency more easily
        # positive_freqs = freqs[:len(freqs)//2]
        # # take median frequency as cutoff frequency (arbitrary)
        # cutoff_freq = freqs[len(freqs)//2]


        # take the fourier transform of the signal (self)
        transformed_array = fft.fft(self)
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
        self[:] = filtered_array
