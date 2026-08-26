"""Run dashboard + logger in one process tree (single-container / one-shot deploys).

Starts logger.py --adaptive and server.py in parallel, forwards SIGTERM/SIGINT to
both, and exits if either child dies so the supervisor (Docker/systemd) can restart.

Usage:
  python entrypoint.py [port]          # default port 8088
  docker run ...                       # Dockerfile CMD points here
"""
import os
import signal
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
_kids = []


def _stop(*_):
    for p in _kids:
        if p.poll() is None:
            p.send_signal(signal.SIGTERM)
    deadline = time.time() + 10
    for p in _kids:
        remaining = max(0, deadline - time.time())
        try:
            p.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            p.kill()
    # Prefer a non-zero exit if a child already failed.
    codes = [p.returncode for p in _kids if p.returncode not in (None, 0, -signal.SIGTERM)]
    sys.exit(codes[0] if codes else 0)


def main():
    port = "8088"
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = sys.argv[1]

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    py = sys.executable
    _kids.append(subprocess.Popen(
        [py, "-u", os.path.join(HERE, "logger.py"), "--adaptive"],
        cwd=HERE,
    ))
    _kids.append(subprocess.Popen(
        [py, "-u", os.path.join(HERE, "server.py"), port],
        cwd=HERE,
    ))
    print(f"entrypoint: logger + server on :{port}  (pid {[p.pid for p in _kids]})",
          flush=True)

    while True:
        for p in _kids:
            rc = p.poll()
            if rc is not None:
                print(f"entrypoint: child pid={p.pid} exited ({rc}); shutting down",
                      flush=True)
                _stop()
        time.sleep(1)


if __name__ == "__main__":
    main()
