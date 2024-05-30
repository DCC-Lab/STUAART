import urllib.request
import time
import pandas as pd
import datetime as dt
import sys
import tkinter as tk
import os

ALL_IPS = ["192.168.0.101"]

window = tk.Tk()
status = tk.Label(text='Waiting')
status.pack(ipadx=100, ipady=50)


def fetch_data(data_for_server, index):
    '''
    Fetches the data from index'th ip listed in ALL_IPS.
    Returns False if there is an error while fetching the data.
    Returns True if it succeeds writing the file.
    
        Parameters:
            data_for_server (bytes): Data to send to the server.
            index (int): The index in the array of ips to fetch the data from.

        Returns:
            (bool): Whether the data was successfully saved.
    '''

    try:
        start = time.time()
        status.config(text="Loading " + ALL_IPS[index])
        web_url = urllib.request.urlopen(
            "http://"+ALL_IPS[index]+"/", data=data_for_server)
    except:
        status.config(text="URL ERROR")
        print("Network Error")
        return False

    else:
        html_data = web_url.read()
        print(html_data)
        status.config(text="Waiting")
        pathToFile = os.path.join(os.path.expanduser('~'), 'Documents', 'SmartCageData', str(ALL_IPS[index]))
        logPath = os.path.join(pathToFile, 'logs')
        os.makedirs(logPath, exist_ok=True)
        f = open(os.path.join(logPath, dt.datetime.now().strftime("%d_%m_%Y-%H_%M_%S") + '.log'), 'w')
        f.writelines(['Time to fetch : ' + str(time.time()-start) + 'ms\n',
                      'Number of characters : ' + str(len(html_data)) + '\n',
                      'Web code : ' + str(web_url.getcode())])
        f.close()
        decodedMessage = html_data.decode().split('\r\n')
        f = open(os.path.join(pathToFile, decodedMessage[0]), 'w')
        f.write(''.join(decodedMessage[1:]))
        return True


def refresh():
    '''
    Method called by the refresh button in the UI.
    Gives to the servers 'refresh' in bytes as data.
    '''
    for i in range(len(ALL_IPS)):
        fetch_data("refresh\n\n".encode('utf-8'), i)

def fetch_loop(index):
    '''
    Loops infinitely with spaces of 10000 milliseconds between each data fetch.
    Fetches data from the server, if it fails, retries faster (1000 milliseconds).
    '''
    if (fetch_data(None, index)):
        window.after(10000, fetch_loop, index)
    else :
        window.after(1000, fetch_loop, index)


button = tk.Button(text='Refresh', command=refresh)
button.pack(pady=50)

for i in range(len(ALL_IPS)):
    fetch_loop(i)

window.mainloop()
