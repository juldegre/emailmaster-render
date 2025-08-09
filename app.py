def background_loop():
    while True:
        try:
            run_once()
        except Exception as e:
            print("[loop] error:", e, flush=True)
        time.sleep(INTERVAL_MIN * 60)

@app.route("/health")
def health():
    return "OK", 200

if __name__ == "__main__":
    t = threading.Thread(target=background_loop, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=PORT)
