import urllib.request
import time
import pandas as pd
import datetime as dt
import tkinter as tk
import os

NBR_OF_IPS = 3

INITIAL_IP = 101

IP_HEADER = "192.168.0."

ALL_IPS = []

window = tk.Tk()
status = tk.Label(text='Waiting')
status.pack(ipadx=100, ipady=50)


def initialize_ips():
    for i in range(NBR_OF_IPS):
        ALL_IPS.append(IP_HEADER + str(INITIAL_IP+i))
    print(ALL_IPS)


def create_log_file(path_to_file, file_title, start_time, data, web_code):
    '''
    Creates a log file at the specified path, with the specified information.
    
        Parameters:
            path_to_file (string): The path where the file was saved.
            file_title (string): The name of the file fetched.
            start_time (float): The time in milliseconds since epoch where we started to fetch the file.
            data (array): The data fetched.
            web_code (string): The web code returned by the server.
    '''
    log_path = os.path.join(path_to_file, 'logs')
    os.makedirs(log_path, exist_ok=True)
    f = open(os.path.join(log_path, dt.datetime.now().strftime("%d_%m_%Y-%H_%M_%S") + '.log'), 'w')
    
    
    f.writelines(['File fetched : ' + file_title + '\n',
                    'Time to fetch : ' + str(time.time()-start_time) + 's\n',
                    'Number of characters : ' + str(len(data)) + '\n',
                    'Web code : ' + web_code])
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
        path_to_file = os.path.join(os.path.expanduser('~'), 'Documents', 'SmartCageData', str(ALL_IPS[index]))
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
        create_log_file(path_to_file, 'not applicable', start, data, code)
        return False

    else:
        html_data = web_url.read()
        decoded_message = html_data.decode().split('\r\n')
        file_title = decoded_message[0]
        
        print(html_data)
        status.config(text="Waiting")
        
        
        create_log_file(path_to_file, file_title, start, html_data, str(web_url.getcode()))
        
        f = open(os.path.join(path_to_file, file_title), 'w')
        f.write(''.join(decoded_message[1:]))
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
        window.after(30000, fetch_loop, index)


def start_fetch_loop():
    '''
    This method is to delay starting the fetching loop.
    With Tkinter we can delay calling a method by a number of milliseconds.
    '''
    for i in range(len(ALL_IPS)):
        fetch_loop(i)

button = tk.Button(text='Refresh', command=refresh)
button.pack(pady=50)

initialize_ips()

print((60 - dt.datetime.now().second + 10) * 1000)

window.after((60 - dt.datetime.now().second + 10) * 1000, start_fetch_loop)

window.mainloop()
