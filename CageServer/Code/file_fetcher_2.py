import urllib.request
import time
import pandas as pd
import datetime as dt
import tkinter as tk
from tkcalendar import Calendar
import os
import paramiko
import threading

# --- CONFIGURATION ---
# Remplace ces valeurs par tes vraies informations de serveur
SERVER_HOST = "172.16.1.109"  # L'adresse IP de ton serveur "Caféine"
SERVER_USERNAME = "dcclab"
SERVER_PASSWORD = "microscope"
SERVER_PATH = "/Volumes/Goliath/vpineaunoel/stuaart/" # Chemin racine sur le serveur

# Liste manuelle des IPs de tes cages (plus besoin de initialize_ips)
ALL_IPS = ["172.16.6.6"] 

# ---------------------

window = tk.Tk()
window.title("Smart Cage Data Fetcher")
status_Label = tk.Label(text='Statut: En attente')
status_Label.pack(ipadx=100, ipady=20)

today = dt.datetime.now()
calendar = Calendar(window, selectmode='day', year=today.year, month=today.month, day=today.day, date_pattern='yyyy.mm.dd')
calendar.pack(ipadx=75, ipady=25, padx=20)

def save_to_caffeine_server(subfolders, local_file_path, file_title):
    try:
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_client.connect(SERVER_HOST, username=SERVER_USERNAME, password=SERVER_PASSWORD)
        sftp = ssh_client.open_sftp()
        
        remote_path = SERVER_PATH
        
        # Création récursive des dossiers sur le serveur
        for subfolder in subfolders:
            remote_path = f"{remote_path}/{subfolder}"
            try:
                sftp.chdir(remote_path)
            except IOError:
                sftp.mkdir(remote_path)
        
        sftp.put(local_file_path, f"{remote_path}/{file_title}")
        sftp.close()
        ssh_client.close()
        print(f"Succès: {file_title} envoyé au serveur.")
    except Exception as e:
        print(f'Erreur serveur (SSH/SFTP): {e}')

def create_log_file(path_to_file, ip, file_title, start_time, data, status):
    log_path = os.path.join(path_to_file, 'logs')
    os.makedirs(log_path, exist_ok=True)
    log_title = dt.datetime.now().strftime("%Y_%m_%d-%H_%M_%S") + '.log'
    local_log_path = os.path.join(log_path, log_title)
    
    with open(local_log_path, 'w') as f:
        f.writelines([
            f'File fetched : {file_title}\n',
            f'Time to fetch : {time.time()-start_time:.2f}s\n',
            f'Number of characters : {len(data)}\n',
            f'Web status : {status}'
        ])
    
    save_to_caffeine_server([ip, 'logs'], local_log_path, log_title)

def fetch_data(data_for_server, index):
    if index >= len(ALL_IPS): return False
    ip = ALL_IPS[index]
    start = time.time()
    path_to_file = os.path.join(os.path.expanduser('~'), 'Documents', 'SmartCageData', ip)
    os.makedirs(path_to_file, exist_ok=True)

    try:
        url = f"http://{ip}/"
        # On envoie la requête (POST si data_for_server est présent, sinon GET)
        req = urllib.request.Request(url, data=data_for_server, method='POST' if data_for_server else 'GET')
        with urllib.request.urlopen(req, timeout=5) as response:
            html_data = response.read()
            status = f'{response.status} {response.reason}'
            
            decoded_message = html_data.decode().split('\r\n')
            file_title = decoded_message[0] if decoded_message[0] else f"data_{dt.datetime.now().strftime('%H%M%S')}.csv"
            
            # Sauvegarde locale
            local_file_path = os.path.join(path_to_file, file_title)
            with open(local_file_path, 'w') as f:
                f.write('\n'.join(decoded_message[1:]))
            
            # Logs et serveur
            create_log_file(path_to_file, ip, file_title, start, html_data, status)
            save_to_caffeine_server([ip], local_file_path, file_title)
            return True

    except Exception as e:
        print(f"Erreur réseau pour l'IP {ip}: {e}")
        status_Label.config(text=f"Erreur: {ip}")
        return False

def refresh():
    for i in range(len(ALL_IPS)):
        threading.Thread(target=fetch_data, args=("refresh\n\n".encode('utf-8'), i)).start()

def fetch_loop(index):
    # Boucle de fond pour la collecte automatique
    while True:
        success = fetch_data(None, index)
        wait_time = 12 * 3600 if success else 3600 # 12h si succès, 1h si échec
        time.sleep(wait_time)

def start_threads():
    # Calcule le délai jusqu'à minuit pour le premier lancement
    now = dt.datetime.now()
    seconds_until_midnight = ((24 - now.hour - 1) * 3600) + ((60 - now.minute - 1) * 60) + (60 - now.second)
    
    print(f"Lancement automatique dans {seconds_until_midnight/3600:.2f} heures.")
    
    for i in range(len(ALL_IPS)):
        t = threading.Timer(seconds_until_midnight, fetch_loop, args=[i])
        t.daemon = True
        t.start()

def fetch_date():
    selected_date = calendar.get_date()
    for i in range(len(ALL_IPS)):
        threading.Thread(target=fetch_data, args=(f'/{selected_date}.csv'.encode('utf-8'), i)).start()

# UI Buttons
calendar_fetch_button = tk.Button(text='Fetch selected date', command=fetch_date)
calendar_fetch_button.pack(pady=5)

refresh_button = tk.Button(text='Force Refresh All', command=refresh)
refresh_button.pack(pady=10)

# Lancement des threads de fond
start_threads()

window.mainloop()