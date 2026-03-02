import matplotlib.pyplot as plt 
import numpy as np 
import pandas as pd 

def convert_time_in_seconds(data_in_milliseconds):
	data_in_seconds = data_in_milliseconds/1000
	return data_in_seconds

def convert_time_in_minutes(data_in_milliseconds):
	data_in_minutes = data_in_milliseconds/1000/60
	return data_in_minutes

def plot_data(time, data, directory, is_saved=False):
	plt.figure(figsize=(10,7))
	plt.scatter(time/1000/60, data[:, 0], label="scale 1")
	plt.scatter(time/1000/60, data[:, 1], label="scale 2")
	plt.scatter(time/1000/60, data[:, 2], label="scale 3")
	plt.plot(time/1000/60, data[:, 0])
	plt.plot(time/1000/60, data[:, 1])
	plt.plot(time/1000/60, data[:, 2])

	plt.xlabel("Time [min]")
	plt.ylabel("Weight [g]")
	plt.legend()

	if is_saved:
		plt.savefig(directory + "/Weight_over_time.png", format="png")
	plt.show()

def calculate_frequency_of_acquisition(time):
	time_in_seconds = convert_time_in_seconds(data_in_milliseconds=time)

	# Define 1-second bins from 0 to the last second
	max_time = np.ceil(np.amax(time_in_seconds))
	bins = np.arange(0, max_time + 1, 1)

	# Count how many points fall into each 1-second bin
	counts, _ = np.histogram(time_in_seconds, bins=bins)
	counts_without_zero = counts[counts != 0]
	mean_counts = np.mean(counts_without_zero)
	stdev_counts = np.std(counts_without_zero)

	return mean_counts, stdev_counts, counts.shape


def compute_sampling_rate(time):
	"""
	Computes the sampling rate according to the time array. 
	"""
	time_in_seconds = convert_time_in_seconds(data_in_milliseconds=time)

	dt = np.diff(time_in_seconds) # convert the time in seconds
	# Compute the average sampling rate
	fs_mean = 1 / np.mean(dt)

	# You can also check the variability:
	fs_std = np.std(1 / dt)

	print(f"Estimated mean sampling rate: {fs_mean:.3f} Hz")
	print(f"Standard deviation of sampling rate: {fs_std:.3f} Hz")
	print(f"Min: {1/np.max(dt):.3f} Hz, Max: {1/np.min(dt):.3f} Hz")

	return 1/np.min(dt), fs_mean


def remove_outliers(data, max_threshold=50, min_threshold=-50):
	data[:, 1:] = np.where((data[:, 1:] > min_threshold) & (data[:, 1:] < max_threshold), data[:, 1:], 0)
	number_of_outliers = data[:, 1:][data[:, 1:] == 0].shape[0]
	print("Number of outliers : ", number_of_outliers)

	return data


def compute_number_of_slow_acquisition(time_in_milliseconds, expected_acquisition_rate=80, is_saved=False):
	dt = np.diff(time_in_milliseconds) 

	expected_dt = 1000 / expected_acquisition_rate

	all_thresholds = []
	all_number_of_pauses = []
	all_mean_pause_duration_seconds = []
	for i in range(1, 40, 1):
		threshold = i/2 * expected_dt
		num_pauses = np.sum(dt > threshold) # gives True when the delay is higher than the threshold. Counts the number of True. 
		pause_durations = dt[dt > threshold]
		mean_pause_duration = np.mean(pause_durations/1000)

		print(f"Expected Δt: {expected_dt:.2f} ms")
		print(f"Number of slow acquisitions: {num_pauses}")
		print(f"Average pause duration: {np.mean(pause_durations):.1f} ms")
		print(" ")

		all_thresholds.append(threshold)
		all_number_of_pauses.append(num_pauses)
		all_mean_pause_duration_seconds.append(mean_pause_duration)

	fig = plt.figure(figsize=(10,7))
	ax1 = fig.add_subplot(1,2,1)
	ax2 = fig.add_subplot(1,2,2)

	ax1.plot(all_thresholds, all_number_of_pauses)
	ax1.set_xlabel("Delay cutoff [ms]", fontsize=18)
	ax1.set_ylabel("Number of slowdowns", fontsize=18)

	ax2.plot(all_thresholds, all_mean_pause_duration_seconds, color="red")
	ax2.set_xlabel("Delay cutoff [ms]", fontsize=18)
	ax2.set_ylabel("Average slowdown durations [s]", fontsize=18)

	if is_saved:
		plt.savefig(directory + "/Number_and_average_slowdown.png", format="png")
	plt.show()



def identify_buffer_flushes(time, data, remove=False):
	indices_of_buffer_flushes = np.where(time == "--")[0]
	
	dt = np.diff(time[indices_of_buffer_flushes-1].astype(int))
	mean_dt = np.mean(dt)
	stdev_dt = np.std(dt)

	print(f"Mean time between buffer flushes : {mean_dt/1000:.4f} +- {stdev_dt/1000:.4f} seconds.")

	indices_before_and_after_flushes = np.sort(np.concatenate((time[indices_of_buffer_flushes-1].astype(int), time[indices_of_buffer_flushes+1].astype(int))))
	indices_before_and_after_flushes_reshaped = np.reshape(indices_before_and_after_flushes, (-1, 2))
	dt_flush = np.diff(indices_before_and_after_flushes_reshaped, axis=1)
	mean_dt_flush = np.mean(dt_flush)
	stdev_dt_flush = np.std(dt_flush)

	print(f"Mean time to flush buffer in SD card : {mean_dt_flush/1000:.4f} +- {stdev_dt_flush/1000:.4f} seconds.")

	if remove:
		weight_data_without_flushes = np.delete(data, indices_of_buffer_flushes, axis=0)
		time_without_flushes = np.delete(time, indices_of_buffer_flushes)
		return time_without_flushes.astype(float), weight_data_without_flushes.astype(float)
	else:
		return time, data



if __name__ == "__main__":
	directory = '/Users/valeriepineaunoel/Desktop/'
	filename = "2026.02.22.csv"
	data = pd.read_csv(directory+filename).to_numpy()
	time = data[:, 0]
	weight_data = data[:, 1:]
	
	time, weight_data = identify_buffer_flushes(time=time, data=weight_data, remove=True)

	frequency, stdev, number_of_points = calculate_frequency_of_acquisition(time=time)
	print(f"FREQUENCY : {frequency:.4f} +- {stdev:.4f} (done with {number_of_points} seconds)")
	max_sampling_rate, sampling_rate = compute_sampling_rate(time=time)

	# plot_data(time=time, data=weight_data, directory=directory, is_saved=False)



