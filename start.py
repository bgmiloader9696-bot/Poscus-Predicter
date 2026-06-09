import threading
import os
import sys
import time
import subprocess

def run_flask():
    port = os.environ.get("PORT", "5000")
    print(f"[FLASK] Starting on port {port}...")
    while True:
        ret = os.system(f"gunicorn app:app --bind 0.0.0.0:{port} --workers 1 --timeout 120 --keep-alive 5")
        print(f"[FLASK] Crashed (code {ret}), restarting in 3s...")
        time.sleep(3)

def run_bot():
    print("[BOT] Starting Telegram bot...")
    while True:
        ret = os.system("python bot.py")
        print(f"[BOT] Crashed (code {ret}), restarting in 5s...")
        time.sleep(5)

if __name__ == "__main__":
    # Start Flask in background thread
    t1 = threading.Thread(target=run_flask, daemon=True)
    t1.start()

    # Give Flask 2 sec to bind port (Render needs port open fast)
    time.sleep(2)

    # Start bot in background thread
    t2 = threading.Thread(target=run_bot, daemon=True)
    t2.start()

    print("[START] Both Flask + Bot running!")

    # Keep main thread alive forever
    while True:
        time.sleep(60)
        print("[HEALTH] Flask + Bot still running...")
