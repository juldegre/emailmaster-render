from flask import Flask, jsonify
import os, email_core

app = Flask(__name__)

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

@app.route("/cron")
def cron():
    email_core.run_email_master()
    return jsonify({"status": "emails processed"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
