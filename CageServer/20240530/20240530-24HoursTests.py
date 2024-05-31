import urllib.request
import time
import pandas as pd
import datetime as dt
import tkinter as tk
import os

ALL_IPS = ["192.168.0.101"]

window = tk.Tk()
status = tk.Label(text='Waiting')
status.pack(ipadx=100, ipady=50)


def create_log_file(pathToFile, fileTitle, startTime, data, webCode):
    logPath = os.path.join(pathToFile, 'logs')
    os.makedirs(logPath, exist_ok=True)
    f = open(os.path.join(logPath, dt.datetime.now().strftime("%d_%m_%Y-%H_%M_%S") + '.log'), 'w')
    
    
    f.writelines(['File fetched : ' + fileTitle + '\n',
                    'Time to fetch : ' + str(time.time()-startTime) + 's\n',
                    'Number of characters : ' + str(len(data)) + '\n',
                    'Web code : ' + webCode])
    f.close()


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
        pathToFile = os.path.join(os.path.expanduser('~'), 'Documents', 'SmartCageData', str(ALL_IPS[index]))
        status.config(text="Loading " + ALL_IPS[index])
        web_url = urllib.request.urlopen(
            "http://"+ALL_IPS[index]+"/", data=data_for_server, timeout=3)
    except:
        status.config(text="URL ERROR")
        print("Network Error")
        data = ''
        code = '404'
        if 'web_url' in locals():
            data = web_url.read()
            code = str(web_url.getcode())
        create_log_file(pathToFile, 'error', start, data, code)
        return False

    else:
        html_data = web_url.read()
        decodedMessage = html_data.decode().split('\r\n')
        fileTitle = decodedMessage[0]
        
        print(html_data)
        status.config(text="Waiting")
        
        
        create_log_file(pathToFile, fileTitle, start, html_data, str(web_url.getcode()))
        
        f = open(os.path.join(pathToFile, fileTitle), 'w')
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
        window.after(60000, fetch_loop, index)
    else :
        window.after(1000, fetch_loop, index)


def start_fetch_loop():
    for i in range(len(ALL_IPS)):
        fetch_loop(i)

button = tk.Button(text='Refresh', command=refresh)
button.pack(pady=50)

print((60 - dt.datetime.now().second + 10) * 1000)

window.after((60 - dt.datetime.now().second + 10) * 1000, start_fetch_loop)

window.mainloop()
