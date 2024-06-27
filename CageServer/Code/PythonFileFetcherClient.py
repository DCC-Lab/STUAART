import urllib.request
import time
import pandas as pd
import datetime as dt
import tkinter as tk
import os
import paramiko
from Constants import *
import threading

NBR_OF_IPS = 1
IP_HEADER = "192.168.0."
INITIAL_IP = 101

ALL_IPS = []

WAIT_THREADS = []

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
    '''
    Saves the file located at local_file_path to the server via ssh, under the subfolder with the given file_title.
    
        Parameters:
            subfolder (string): The path where the file should be saved on the server.
            local_file_path (string): The path where the file is saved locally.
            file_title (string): The name to be given to the file on the server.
    '''
    try:
        # print(subfolder)
        # print(local_file_path)
        # print(file_title)
        
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
        print('success')
    except Exception as e:
        print('Failed to save to server. Exception is : ', e)


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
    
    save_to_caffeine_server(f'{ip}/logs', local_file_path, log_title)


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
    Loops infinitely with spaces of 12 hours between each data fetch.
    Fetches data from the server, if it fails, retries faster (1 hour).
    '''
    if (fetch_data(None, index)):
        time.sleep(12 * 60 * 60)
        fetch_loop(index)
    else:
        time.sleep(60 * 60)
        fetch_loop(index)


def start_fetch_loop(time_delay):
    '''
    This method is to delay starting the fetching loop.
    It creates a thread for every IP so the downloads take place in parallel.
    '''
    for i in range(len(ALL_IPS)):
        WAIT_THREADS.append(threading.Timer(time_delay, fetch_loop, [i]))
        WAIT_THREADS[i].daemon = True
        WAIT_THREADS[i].start()

button = tk.Button(text='Refresh', command=refresh)
button.pack(pady=50)

initialize_ips()

time_till_midnight = (24 - dt.datetime.now().hour) * 60 * 60 + (30 - dt.datetime.now().minute) * 60

print(time_till_midnight)

start_fetch_loop(time_till_midnight)

window.mainloop()
