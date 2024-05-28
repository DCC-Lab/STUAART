import urllib.request
import time
import pandas as pd
import datetime as dt
import sys
import random
import tkinter as tk

ALL_IPS = ["172.16.13.10"]

window = tk.Tk()
status = tk.Label(text='Waiting')
status.pack()


def fetch_data(data_for_server):
    for i in range(0, len(ALL_IPS)):
        total_characters = 0
        try:
            status.config(text="Loading " + ALL_IPS[i])
            web_url = urllib.request.urlopen(
                "http://"+ALL_IPS[i]+"/", data=data_for_server)
        except urllib.error.URLError:
            html_data = 0
            total_characters += 0
            size_of_data = 0
            print("Network Error, " + web_url)

        else:
            html_data = web_url.read()
            # sys.getsizeof() returns the size of the object in bytes
            size_of_data = sys.getsizeof(html_data)
            total_characters += len(html_data)
            # 200 if the connection was done well
            end = time.time()
            now = dt.datetime.now()
            data = [now.date(), now.strftime("%H:%M:%S"), time_to_wait, end -
                    start, total_characters, size_of_data, web_url.getcode()]
            data_df = pd.DataFrame(data).T
            print(data_df)
            print(html_data)


def refresh():
    fetch_data("refresh")


button = tk.Button(text='Refresh', command=refresh)
button.pack()

window.mainloop()


nb_of_tests = 4000
data = {}

for j in range(0, nb_of_tests):
    time_to_wait = 30
    status.config(text="Waiting")
    time.sleep(time_to_wait)
    start = time.time()
    fetch_data(None)
    print(j)
