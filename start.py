import os
import time
import subprocess
import sys

if __name__ == "__main__":
    print("[START] Poscus Predicter - Starting Flask...", flush=True)
    port = os.environ.get("PORT", "10000")
    print(f"[FLASK] Starting gunicorn on port {port}...", flush=True)
    
    while True:
        try:
            ret = subprocess.call([
                "gunicorn", "app:app",
                "--bind", f"0.0.0.0:{port}",
                "--workers", "1",
                "--threads", "2",
                "--timeout", "120",
                "--keep-alive", "5",
                "--log-level", "info"
            ])
            print(f"[FLASK] Gunicorn stopped (code {ret}), restarting in 3s...", flush=True)
        except Exception as e:
            print(f"[FLASK] Error: {e}, restarting in 3s...", flush=True)
        time.sleep(3)
