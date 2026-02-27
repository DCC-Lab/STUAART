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
    ip = str(ALL_IPS[index])
    try:
        start = time.time()
        path_to_file = os.path.join(os.path.expanduser('~'), 'Documents', 'SmartCageData', ip)
        os.makedirs(path_to_file, exist_ok=True)
        
        url = f"http://{ip}/{data_for_server}" # ou ta logique d'URL
        print(f"Connexion à l'Arduino ({ip})...")
        
        web_url = urllib.request.urlopen(url, timeout=10)
        html_data = web_url.read()
        print(f"Données reçues de l'Arduino ({len(html_data)} octets)")

        decoded_message = html_data.decode().split('\r\n')
        file_title = decoded_message[0]
        local_file_path = os.path.join(path_to_file, file_title)

        # On écrit le fichier LOCALEMENT d'abord
        with open(local_file_path, 'w') as f:
            f.write('\n'.join(decoded_message[1:]))
        print(f"Fichier écrit sur le Mac : {local_file_path}")

        # Ensuite on tente Caffeine
        print("Tentative d'envoi vers Caffeine...")
        save_to_caffeine_server([ip], local_file_path, file_title)
        print("Succès total : Arduino -> Mac -> Caffeine")
        
        return True
    except Exception as e:
        print(f"ERREUR : {e}")
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
    '''
    On formate la date pour qu'elle corresponde EXACTEMENT au snprintf de l'Arduino.
    selected_date (yyyy.mm.dd) devient /yyyy.mm.dd.csv
    '''
    selected_date = calendar.get_date()
    # On s'assure d'avoir le slash au début car ton snprintf l'inclut
    # filename = f"/{selected_date}.csv" 
    filename = "/2026.02.22.csv"
    
    for i in range(len(ALL_IPS)):
        # IMPORTANT: On ne passe pas d'argument 'data' ici pour forcer un GET
        threading.Thread(target=fetch_data, args=(filename, i)).start()


# UI Buttons
calendar_fetch_button = tk.Button(text='Fetch selected date', command=fetch_date)
calendar_fetch_button.pack(pady=5)

refresh_button = tk.Button(text='Force Refresh All', command=refresh)
refresh_button.pack(pady=10)

# Lancement des threads de fond
start_threads()

window.mainloop()