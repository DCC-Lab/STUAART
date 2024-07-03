import numpy as np
import matplotlib.pyplot as plt

class Data(np.ndarray):

    def __new__(cls, data: np.ndarray, time: np.ndarray):
        obj = np.asarray(data).view(cls)
        return obj

    def __init__(self, data: np.ndarray, time: np.ndarray):
        super().__init__()
        self.weight_threshold = 0
        self.outliers_threshold = 0
        self.time = time

        # relative to every points considered as weight measurements
        self.peaks = [0]
        self.peak_times = [0]

        # relative to average of neighbor points considered as weight measurements
        # relative to intervals over weight_threshold
        self.peak_averages = [0]
        self.peak_average_times = [0]

        self.baseline = np.zeros(self.shape)

    def find_offset(self, tolerance: float=0.2):
        """
        This function can be used to calculate the first offset of the signal. The code
        goes trough the signal starting from start and verifies if it is stable. Stability is
        established using a weight tolerance (default is 0.2g). When the signal goes beyond this king of variation,
        the previous values are averaged to calculate the initial offset.

        Arguments:
            - tolerance: range of weight around previous value considered as stable. default is 0.2g
        """
        # declare list to store old values to average for calculation of offset
        offset_values = [self[0]]
        # store previous value. first previous value is the value at first time tick
        last_value = self[0]

        # loop on signal starting at second time tick
        for value in self[1:]:
            # verify if difference between to consecutive values is less than tolerance
            if abs(value - last_value) > tolerance:
                # break loop when stability criteria is not met
                break
            # append value to list if stability criteria is met
            offset_values.append(value)
            # reassign last_value to current value for next iteration
            last_value = value
        
        # return mean of stable values
        return np.mean(np.array(offset_values))

    def shift_data_to_zero(self):
        """
        This function calculates the initial offset of the data to subtract it from all points.
        We are now sure the weight is zero when the mouse in not on the scale. The number of data points
        to average for initial offset depends on when the first weight measurement is recorded.
        """

        #get offset
        offset = self.find_offset()

        # substract offset from data to shift if back to zero
        shifted_data = self - offset

        #update the weight values 
        # self[:] = np.abs(shifted_data)
        self[:] = np.abs(shifted_data)

        # return the object in case it needs to be stored in main
        return self

    def find_baseline(self, n_values: int=50, threshold: float=2):
        """
        This function goes through the weight values to identify the drifting baseline of the signal.
        The self.baseline is associated to an array containing the offset at each time tick.
        The stability is verified by looking at n_values in the past from current time increment
        and looking if they are over a threshold.

        Arguments:
            - n_values: number of stable values needed to assert stability before updating the offset
            - threshold: threshold for weight considered as "empty"
        """
        # iteration increment
        i = 1
        # offset initialize as the first weight value
        offset = self.find_offset()

        # looping on all weight values
        while i < len(self):
            # time of the current weight value
            time = self.time[i]
            # weight value
            value = self[i]
            if value > threshold:
                #if value is over the threshold, we go look n_values further in time because stability 
                # won't be reached until then.
                # baseline needs to be tracked at each time stamp to substract it from weight values
                # saving unchanged baseline for next time ticks
                self.baseline[i: i+n_values] = offset

                # adding n_values to the iteration increment to go n_values further in time
                i += n_values
                # going to next iteration
                continue
            
            else:
                # else cas is if present value is under threshold
                # get old values to verify if they are also under 
                # the threshold before setting their average as the new baseline

                # handling the case where the current index of value is smaller
                # than number of values to average
                if i >= n_values:
                    # averaging from current value to n_values in the past
                    old_values = self[i - n_values:i]
                else:
                    # averaging from start to current value
                    old_values = self[0:i]
                
                # verify if all old_values are under (threshold + current offset)
                # since the drift causes the whole curve to shift up or down,
                # old_values need to be compared to threshold + offset
                if np.all(np.abs(old_values) < (threshold + offset)):
                    # change offset value if the previous_values are under threshold
                    offset = np.mean(old_values)
                    # print(f'offset change: {offset}')

                # save baseline value for time tick
                self.baseline[i] = offset

                # go to next iteration increment
                i +=1

    def subtract_baseline(self):
        """
        Subtract the self.baseline array to the weight values
        Updates object
        """
        self[:] = self - self.baseline
        return self

    def remove_outliers(self) -> np.array:
        """
        Removes the data higher or lower than self.outliers_threshold. 
        """
        self[:] = np.where(self < self.outliers_threshold[0], 0, self)
        self[:] = np.where(self > self.outliers_threshold[1], 0, self)
        return self

    def set_outliers_threshold(self, threshold: float):
        self.outliers_threshold = threshold
    
    def get_weight_threshold(self):
        """
        Calculate the weight threshold used to identify if a value should be considered as a weight measurement.
        A simple method is used for now. The average of the values above the average of the signal is used. This 
        is meant to be used after filtering and shifting the signal to zero.
        """
        filtered_signal = self[self > np.mean(self)]
        filtered_signal = filtered_signal[filtered_signal > np.mean(filtered_signal)]
        threshold = np.mean(filtered_signal)
        return threshold

    def set_weight_threshold(self):
        self.weight_threshold = self.get_weight_threshold()

    def __find_peaks_index_intervalls(self) -> list:
        """
        This function finds the start and end index for all period of time where the
        weight measurement is above self.weight_threshold.
        """
        # empty list to store index
        peaks_index = []
        # iteration increment variable
        i = 0

        # looping on all values
        while i < len(self):
            # current weight value
            value = self[i]

            if value > self.weight_threshold:
                # if current value is above weight_threshold
                # we verify if neighbors are also over the threshold with a loop
                for j, neighbor in enumerate(self[i:]):
                    if neighbor > self.weight_threshold:
                        continue
                    else:
                        # when we reached the first neighbor under the threshold
                        # we append to the list storing the start and end index of
                        # the interval identified as over the self.weight_threshold.
                        peaks_index.append((i,j+i))

                        # go to the end of the intervall in time for next iteration
                        i += j
                        break

            # go to next value
            i += 1

        return peaks_index

    def find_all_peaks_values(self) -> tuple:
        """
        Find weight values above the self.weight_threshold and their index to store them
        in appropriate class variable.
        """
        index_above_threshold = np.asarray(self > self.weight_threshold).nonzero()
        self.peak_times, self.peaks =  self.time[index_above_threshold], self[index_above_threshold]

    def __find_signal_average_at_peaks(self, peaks_index_intervalls: list) -> tuple:
        """
        Find the average value for the peak intervalls with their index obtained with __find_peaks_index_intervalls().
        Weight values are averaged over the intervalls and the middle index is attributed to the average value.
        """
        peak_averages = []
        peak_times = []
        for start_index, end_index in peaks_index_intervalls:
            mean_index = int(np.mean([start_index, end_index]))
            peak_average = np.mean(self[start_index: end_index])
            peak_averages.append(peak_average)
            peak_times.append(self.time[mean_index])

        return np.array(peak_times), np.array(peak_averages)

    def find_peak_average_values(self):
        """
        Calculate the average of each intervall above weight_threshold and their associate time tick.
        Set these two array to the approriate class variable.
        """
        peaks_index_intervalls = self.__find_peaks_index_intervalls()
        peak_times, peak_averaged_values = self.__find_signal_average_at_peaks(peaks_index_intervalls)
        self.peak_average_times, self.peak_averages = peak_times, peak_averaged_values

    def plot_baseline(self):
        plt.plot(self.time, self.baseline, color='black', label='Baseline')
        plt.title('Baseline')
        plt.show()

    def plot_signal(self, threshold: bool=True, peaks: bool=True, baseline: bool=True, color: str="k", is_saved:bool=False, real_data=None):
        # number of data points over the weight_threshold
        print(f"Number of peaks identified {len(self.peaks)}")
        # number of intervals where the data points are all over the weight_threshold
        # an intervall is probably made of many data points
        print(f"Number of peak intervals identified {len(self.peak_averages)}")
        # average of all data points over weight threshold
        print(f"Peaks average is {np.mean(self.peaks)}")
        # average of intervall means
        print(f"Peak intervals average is {np.mean(self.peak_averages)}")

        fig = plt.figure(figsize=(13,3))

        if real_data is not None:
            plt.scatter(real_data[0], real_data[1], marker="*", edgecolors="k", color="y", label="Real weight", s=100)
        plt.plot(self.time, self, color=color, label='Signal')

        if threshold:
            plt.plot([0, np.max(self.time)], [self.weight_threshold, self.weight_threshold], color='red', linestyle='dashed', label='Threshold')
        if peaks:
            plt.scatter(self.peak_times, self.peaks, color='k')
        if baseline:
            plt.plot(self.time, self.baseline, color='k', label='Baseline', linestyle="--", linewidth = 2)

        plt.xlabel("Time [h]", fontsize=14)
        plt.ylabel("Weight [g]", fontsize=14) 
        plt.legend()

        if is_saved:
            filename = input("Please enter the name of your file :")
            plt.savefig(str(filename) + ".png", format="png", transparent=True)
        plt.show()

    def plot_peak_averages(self):
        average = np.mean(self.peak_averages)
        plt.scatter(self.peak_average_times, self.peak_averages, color='black', label="Peaks")
        plt.plot([0, max(self.peak_average_times)], [average, average], color='red', linestyle='dashed', label=f'Average of peak averages = {average:.2f}')
        plt.xlabel("Time [h]")
        plt.ylabel("Raw output [-]")
        plt.title("Peak averages")
        plt.legend()
        plt.show()

    def plot_all_peaks(self):
        average = np.mean(self.peaks)
        plt.scatter(self.peak_times, self.peaks, color='black', label="Peaks")
        plt.plot([0, max(self.peak_times)], [average, average], color='red', linestyle='dashed', label=f'Average of all peaks = {average:.2f}')
        plt.xlabel("Time [h]")
        plt.ylabel("Raw output [-]")
        plt.title("All peaks")
        plt.legend()
        plt.show()