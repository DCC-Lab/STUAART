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
        try:
            status.config(text="Loading " + ALL_IPS[i])
            web_url = urllib.request.urlopen(
                "http://"+ALL_IPS[i]+"/", data=data_for_server)
        except urllib.error.URLError:
            status.config(text="URL ERROR " + web_url)
            print("Network Error, " + web_url)
            return False

        else:
            html_data = web_url.read()
            # sys.getsizeof() returns the size of the object in bytes
            # 200 if the connection was done well
            number_list = html_data.decode().split('\r\n')
            message = ''
            for number in number_list:
                if number.isnumeric():                    
                    message += chr(int(number))
            print(message)
            status.config(text="Waiting")
            return True


def refresh():
    fetch_data("refresh\n\n".encode('utf-8'))

def fetch_loop():
    if (fetch_data(None)):
        window.after(10000, fetch_loop)
    else :
        window.after(1000, fetch_loop)


button = tk.Button(text='Refresh', command=refresh)
button.pack(pady=50)

fetch_loop()

window.mainloop()
