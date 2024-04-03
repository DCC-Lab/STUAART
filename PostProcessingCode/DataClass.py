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

        # relative to average of neighbor points considered as weight measurments
        self.peak_averages = [0]
        self.peak_average_times = [0]

    def center_data_on_zero(self):
        """
        Raw signal is not centered on zero because the rest is non-zero. That's why we need to tare the load cell.
        This function substracts the first value of the signal
        
        """
        baseline = np.mean(self[0])
        centered_data = self - baseline
        self[:] = np.abs(centered_data)
        return self

    def find_baseline(self):
        for i, value in enumerate(self):
            stable_values = []

    def remove_outliers(self) -> np.array:
        self[:] = np.where(np.abs(self) > self.outliers_threshold, 0, self)
        return self

    def set_outliers_threshold(self, threshold: float):
        self.outliers_threshold = threshold
    
    def get_weight_threshold(self):
        filtered_signal = self[self > np.mean(self)]
        filtered_signal = filtered_signal[filtered_signal > np.mean(filtered_signal)]

        threshold = np.mean(filtered_signal)

        return threshold

    def set_weight_threshold(self):
        self.weight_threshold = self.get_weight_threshold()

    def __find_peaks_index_intervalls(self) -> list:
        peaks_index = []
        i = 0
        while i < len(self):
            value = self[i]
            if value > self.weight_threshold:
                for j, neighbor in enumerate(self[i:]):
                    if neighbor > self.weight_threshold:
                        continue
                    else:
                        peaks_index.append((i,j+i))
                        i += j
                        break
            i += 1

        return peaks_index

    def find_all_peaks_values(self) -> tuple:
        index_above_threshold = np.asarray(self > self.weight_threshold).nonzero()
        self.peak_times, self.peaks =  self.time[index_above_threshold], self[index_above_threshold]

    def __find_signal_average_at_peaks(self, peaks_index_intervalls: list) -> tuple:
        peak_averages = []
        peak_times = []
        i = 0
        for start_index, end_index in peaks_index_intervalls:
            mean_index = int(np.mean([start_index, end_index]))
            peak_average = np.mean(self[start_index: end_index])
            i+= 1

            peak_averages.append(peak_average)
            peak_times.append(self.time[mean_index])

        return np.array(peak_times), np.array(peak_averages)

    def find_peak_average_values(self):
        peaks_index_intervalls = self.__find_peaks_index_intervalls()
        peak_times, peak_averaged_values = self.__find_signal_average_at_peaks(peaks_index_intervalls)
        self.peak_average_times, self.peak_averages = peak_times, peak_averaged_values

    def plot_signal(self, threshold: bool=True, peaks: bool=True):

        print(f"Number of peaks identified {len(self.peaks)}")
        print(f"Number of peak intervalls identified {len(self.peak_averages)}")
        print(f"Peaks average is {np.mean(self.peaks)}")
        print(f"Peak intervalls average is {np.mean(self.peaks)}")

        plt.plot(self.time, self, color='black', label='Signal')
        if threshold:
            plt.plot([0, np.max(self.time)], [self.weight_threshold, self.weight_threshold], color='red', linestyle='dashed', label='Threshold')
        if peaks:
            plt.scatter(self.peak_times, self.peaks, color='red')
        plt.xlabel("Time [h]")
        plt.ylabel("Signal [-]") 
        plt.title("Signal")
        plt.legend()
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
