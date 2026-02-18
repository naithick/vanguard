#!/usr/bin/env python3
"""
GreenRoute Mesh v2 — Starter

Starts the Flask backend + ngrok tunnel in one command.
Prints the public URL you need to paste into the ESP32 firmware.

Usage:
    python start.py              # start backend on :5001 + ngrok tunnel
    python start.py --port 5002  # different port
    python start.py --no-ngrok   # local only (no tunnel)
"""

import os
import sys
import subprocess
import signal
import time
import json
import urllib.request

PORT = 5001
NGROK_PROC = None
FLASK_PROC = None


def get_ngrok_url():
    """Poll ngrok's local API to get the public URL."""
    for _ in range(20):
        try:
            resp = urllib.request.urlopen("http://127.0.0.1:4040/api/tunnels")
            data = json.loads(resp.read())
            for t in data.get("tunnels", []):
                if t.get("proto") == "https":
                    return t["public_url"]
        except Exception:
            time.sleep(0.5)
    return None


def cleanup(*_):
    """Kill child processes on exit."""
    global NGROK_PROC, FLASK_PROC
    if FLASK_PROC:
        FLASK_PROC.terminate()
    if NGROK_PROC:
        NGROK_PROC.terminate()
    sys.exit(0)


def main():
    global NGROK_PROC, FLASK_PROC, PORT

    import argparse
    parser = argparse.ArgumentParser(description="Start GreenRoute backend + ngrok")
    parser.add_argument("--port", type=int, default=5001)
    parser.add_argument("--no-ngrok", action="store_true")
    args = parser.parse_args()
    PORT = args.port

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    venv_python = os.path.join(os.path.dirname(__file__), "venv", "bin", "python")
    if not os.path.exists(venv_python):
        venv_python = sys.executable

    # ── Start ngrok ───────────────────────────────────────────────────────
    if not args.no_ngrok:
        print(f"\n🌐  Starting ngrok tunnel → localhost:{PORT} ...")
        NGROK_PROC = subprocess.Popen(
            ["ngrok", "http", str(PORT), "--log=stdout"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(2)

        url = get_ngrok_url()
        if url:
            print(f"\n{'='*60}")
            print(f"  NGROK URL:  {url}")
            print(f"  INGEST:     {url}/api/ingest")
            print(f"{'='*60}")
            print(f"\n  Paste this into your ESP32 firmware:")
            print(f'  const char* serverURL = "{url}/api/ingest";')
            print(f"{'='*60}\n")
        else:
            print("⚠  Could not get ngrok URL (is ngrok authenticated?)")
            print("   Run: ngrok config add-authtoken <YOUR_TOKEN>")

    # ── Start Flask ───────────────────────────────────────────────────────
    print(f"🚀  Starting Flask backend on :{PORT} ...")
    env = os.environ.copy()
    env["PORT"] = str(PORT)

    FLASK_PROC = subprocess.Popen(
        [venv_python, os.path.join(os.path.dirname(__file__), "app.py")],
        env=env,
    )

    try:
        FLASK_PROC.wait()
    except KeyboardInterrupt:
        cleanup()


if __name__ == "__main__":
    main()
