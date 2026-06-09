import threading, os, subprocess, sys

def run_flask():
    os.system("python app.py")

def run_bot():
    os.system("python bot.py")

if __name__ == "__main__":
    t1 = threading.Thread(target=run_flask, daemon=True)
    t2 = threading.Thread(target=run_bot)
    t1.start()
    t2.start()
    t2.join()
