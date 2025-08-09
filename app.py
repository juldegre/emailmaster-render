import os, threading, time
from flask import Flask, jsonify
from email_core import run_email_master as run_once

PORT = int(os.getenv("PORT", "10000"))
INTERVAL_MIN = int(os.getenv("CHECK_INTERVAL_MINUTES", "5"))

app = Flask(__name__)  # <-- créer l'app AVANT les routes

@app.get("/")
@app.get("/health")
def health():
    return "OK", 200

@app.get("/cron")
def cron():
    processed = run_once()
    return jsonify({"status": "done", "processed": processed})

def background_loop():
    while True:
        try:
            run_once()
        except Exception as e:
            print("[loop] error:", e, flush=True)
        time.sleep(INTERVAL_MIN * 60)

if __name__ == "__main__":
    t = threading.Thread(target=background_loop, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=PORT)
