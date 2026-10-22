#!/usr/bin/env python3
"""One-process launcher for people who don't want Docker or systemd.

Starts the dashboard, opens it in the browser, and keeps the telemetry logger running.
On a brand-new install there is no account yet: the dashboard shows its login page, and
the logger is started as soon as that login has written creds.json.

    python tools/run.py            # dashboard on http://localhost:8088
    python tools/run.py 9000       # different port

Ctrl+C stops both.
"""
import json
import os
import subprocess
import sys
import threading
import time
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("CARLINKO_DATA") or HERE
CREDS = os.path.join(DATA, "creds.json")
PORT = next((a for a in sys.argv[1:] if a.isdigit()), "8088")


def has_car():
    try:
        c = json.load(open(CREDS))
        return bool(c.get("vehicle_id") and c.get("device_sn"))
    except Exception:
        return False


def run_logger(stop):
    while not stop.is_set():
        if not has_car():
            stop.wait(3)                       # waiting for the web login to finish
            continue
        print("[run] starting logger", flush=True)
        p = subprocess.Popen([sys.executable, "-u", os.path.join(HERE, "logger.py"), "--adaptive"], cwd=HERE)
        while p.poll() is None and not stop.is_set():
            stop.wait(1)
        if stop.is_set():
            p.terminate()
            return
        print(f"[run] logger exited ({p.returncode}), restarting in 15 s", flush=True)
        stop.wait(15)


def main():
    stop = threading.Event()
    web = subprocess.Popen([sys.executable, "-u", os.path.join(HERE, "server.py"), PORT], cwd=HERE)
    threading.Thread(target=run_logger, args=(stop,), daemon=True).start()
    time.sleep(2)
    url = f"http://localhost:{PORT}"
    print(f"\n  Dashboard: {url}\n  Leave this window open. Ctrl+C to stop.\n", flush=True)
    webbrowser.open(url)
    try:
        web.wait()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        web.terminate()


if __name__ == "__main__":
    main()
