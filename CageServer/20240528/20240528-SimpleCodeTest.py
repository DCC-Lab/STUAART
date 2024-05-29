import urllib.request
import time
import pandas as pd
import datetime as dt
import sys
import tkinter as tk

ALL_IPS = ["192.168.0.101"]

window = tk.Tk()
status = tk.Label(text='Waiting')
status.pack(ipadx=100, ipady=50)


def fetch_data(data_for_server):
    for i in range(0, len(ALL_IPS)):
        total_characters = 0
        start = time.time()
        
        try:
            status.config(text="Loading " + ALL_IPS[i])
            web_url = urllib.request.urlopen(
                "http://"+ALL_IPS[i]+"/", data=data_for_server)
        except urllib.error.URLError:
            html_data = 0
            total_characters += 0
            size_of_data = 0
            status.config(text="URL ERROR " + web_url)
            print("Network Error, " + web_url)

        else:
            html_data = web_url.read()
            # sys.getsizeof() returns the size of the object in bytes
            size_of_data = sys.getsizeof(html_data)
            total_characters += len(html_data)
            # 200 if the connection was done well
            end = time.time()
            now = dt.datetime.now()
            data = [now.date(), now.strftime("%H:%M:%S"), end -
                    start, total_characters, size_of_data, web_url.getcode()]
            data_df = pd.DataFrame(data).T
            number_list = html_data.decode().split('\r\n')
            message = ''
            for number in number_list:
                if number.isnumeric():                    
                    message += chr(int(number))
            print(message)
            


def refresh():
    fetch_data("refresh\n\n".encode('utf-8'))


button = tk.Button(text='Refresh', command=refresh)
button.pack(pady=50)

window.mainloop()


nb_of_tests = 4000
data = {}

for j in range(0, nb_of_tests):
    time_to_wait = 30
    status.config(text="Waiting")
    time.sleep(time_to_wait)
    fetch_data(None)
    print(j)
