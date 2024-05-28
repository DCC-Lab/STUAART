import urllib.request
import time
import pandas as pd
import datetime as dt
import sys
import random

nb_of_tests = 4000
data = {}

for j in range(0,nb_of_tests):
	time_to_wait = random.randrange(1, 30, 1)
	time.sleep(time_to_wait)
	start = time.time()
	all_IPs = ["172.16.13.10"]
	total_characters = 0
	result_connection = []

	for i in range(0, len(all_IPs)):
		try:
			weburl = urllib.request.urlopen("http://"+all_IPs[i]+"/")
		except urllib.error.URLError:
			html_data = 0
			total_characters += 0
			size_of_data = 0
			result_connection.append(0) # 0 if the connection didn't work
			
		else:
			html_data = weburl.read()
			size_of_data = sys.getsizeof(html_data) # sys.getsizeof() returns the size of the object in bytes
			total_characters += len(html_data)
			result_connection.append(int(weburl.getcode())) # 200 if the connection was done well

	end = time.time()
	now = dt.datetime.now()
	data[j] = [now.date(), now.strftime("%H:%M:%S"), time_to_wait, end-start, total_characters, size_of_data, result_connection]
	print(j)
	data_df = pd.DataFrame(data).T
	print(data_df)
	#data_df.to_csv("/Users/valeriepineaunoel/Documents/PhD/Cage intelligente/20230926-TestTheTimeItTakesToAccessDataFrom2Firebeetle/"+str(now.date())+"-1Firebeetle"+str(nb_of_tests)+"tests.csv")
