from flask import Flask, request
import os

app = Flask(__name__)
SAVE_PATH = "FILL_SAVE_PATH_HERE"

@app.route('/upload', methods=['POST'])
def upload_file():
    # 1. Get the IP of the ESP32 (e.g., 172.16.6.11)
    esp_ip = request.remote_addr
    
    # 2. Extract the custom filename we will send from the ESP32
    filename = request.headers.get('X-Filename', 'data.csv')
    
    # 3. Create the destination folder if it doesn't exist
    device_path = os.path.join(SAVE_PATH, esp_ip)
    os.makedirs(device_path, exist_ok=True)
    
    # 4. Save the raw CSV data
    file_path = os.path.join(device_path, filename)
    with open(file_path, 'wb') as f:
        f.write(request.data)
        
    print(f"[{esp_ip}] File saved successfully: {filename}")
    return "Success", 200

if __name__ == '__main__':
    # Listens on port 5000 across the local network
    app.run(host='0.0.0.0', port=5000)