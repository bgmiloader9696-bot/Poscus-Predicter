from flask import Flask, send_from_directory, jsonify
import os
import threading
import time
import urllib.request

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')

@app.route('/ping')
def ping():
    return jsonify({"status": "alive"})

# Serve ALL static files including PNGs explicitly
@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory(BASE_DIR, filename)

# Self-ping every 10 min
def self_ping():
    while True:
        time.sleep(600)
        try:
            url = os.environ.get('RENDER_EXTERNAL_URL', 'http://localhost:5000')
            urllib.request.urlopen(f"{url}/ping", timeout=10)
        except:
            pass

if __name__ == '__main__':
    t = threading.Thread(target=self_ping, daemon=True)
    t.start()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
