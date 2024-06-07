import urllib.request
import time
import pandas as pd
import datetime as dt
import tkinter as tk
import os
import paramiko
from Constants import *

NBR_OF_IPS = 1
IP_HEADER = "192.168.0."
INITIAL_IP = 101

ALL_IPS = []

window = tk.Tk()
status_Label = tk.Label(text='Waiting')
status_Label.pack(ipadx=100, ipady=50)


def initialize_ips():
    '''
    Creates an array of IP addresses based on IP_HEADER, INITIAL_IP and NBR_OF_IPS.
    NBR_OF_IPS tells this method how many ips you want to create,
    IP_HEADER gives the sub-address where to create the IP and
    INITIAL_IP is the first IP that will be used for a smart cage.
    '''
    for i in range(NBR_OF_IPS):
        ALL_IPS.append(IP_HEADER + str(INITIAL_IP+i))
    print(ALL_IPS)


def save_to_caffeine_server(subfolder, local_file_path, file_title):
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh_client.connect(SERVER_HOST, username=SERVER_USERNAME, password=SERVER_PASSWORD)
    
    sftp = ssh_client.open_sftp()
    
    remote_path = f"{SERVER_PATH}/{subfolder}/"
    
    try:
        sftp.chdir(remote_path)  # Test if remote_path exists
    except IOError:
        sftp.mkdir(remote_path)  # Create remote_path
        
    sftp.put(local_file_path, remote_path + file_title)
    sftp.close()
    ssh_client.close()


def create_log_file(path_to_file, ip, file_title, start_time, data, status):
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
    log_title = dt.datetime.now().strftime("%Y_%m_%d-%H_%M_%S") + '.log'
    local_file_path = os.path.join(log_path, log_title)
    f = open(local_file_path, 'w')
    
    
    f.writelines(['File fetched : ' + file_title + '\n',
                    'Time to fetch : ' + str(time.time()-start_time) + 's\n',
                    'Number of characters : ' + str(len(data)) + '\n',
                    'Web code : ' + status])
    f.close()
    
    save_to_caffeine_server(f'{ip}/logs', local_file_path, file_title)


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
    ip = str(ALL_IPS[index])

    try:
        start = time.time()
        path_to_file = os.path.join(os.path.expanduser('~'), 'Documents', 'SmartCageData', ip)
        # status_Label.config(text="Loading " + ALL_IPS[index])
        web_url = urllib.request.urlopen(
            "http://"+ALL_IPS[index]+"/", data=data_for_server, timeout=3)
    except:
        status_Label.config(text="URL ERROR")
        print("Network Error")
        data = ''
        status = '404'
        if 'web_url' in locals():
            data = web_url.read()
            status = f'{web_url.status} {web_url.reason}'
        create_log_file(path_to_file, ip, 'not applicable', start, data, status)
        return False

    else:
        html_data = web_url.read()
        decoded_message = html_data.decode().split('\r\n')
        file_title = decoded_message[0]
        
        # print(html_data)
        # status_Label.config(text="Waiting")
        
        create_log_file(path_to_file, ip, file_title, start, html_data, f'{web_url.status} {web_url.reason}')
        
        local_file_path = os.path.join(path_to_file, file_title)
        
        f = open(local_file_path, 'w')
        f.write('\n'.join(decoded_message[1:]))
        f.close()
        
        save_to_caffeine_server(ip, local_file_path, file_title)
        
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
    Loops infinitely with spaces of 60000 milliseconds between each data fetch.
    Fetches data from the server, if it fails, retries faster (30000 milliseconds).
    '''
    if (fetch_data(None, index)):
        window.after(6 * 60 * 60 * 1000, fetch_loop, index)
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

time_till_midnight = (24 - dt.datetime.now().hour) * 1000 * 60 * 60 + (30 - dt.datetime.now().minute) * 1000 * 60

print(time_till_midnight)

window.after(time_till_midnight, start_fetch_loop)

window.mainloop()
