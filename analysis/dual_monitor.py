"""
Watch both ESP32 boards at once, interleaved on one timeline.

    python analysis/dual_monitor.py                 # COM3 + COM14, runs until Ctrl+C
    python analysis/dual_monitor.py --seconds 30    # stop after 30s
    python analysis/dual_monitor.py --ports COM3 COM14

IMPORTANT: close the Arduino IDE serial monitor first. Windows gives one
program exclusive access to a COM port, so the IDE holding it will make
this fail with "Access is denied".

Every line is timestamped from a shared clock, so TX and RX events can be
lined up against each other. A copy is written to results/.
"""

import argparse
import datetime
import os
import sys
import threading
import time

try:
    import serial
except ImportError:
    sys.exit("pyserial missing:  pip install pyserial")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUTDIR = os.path.join(ROOT, "results")

COLORS = ["\033[96m", "\033[93m"]   # cyan, yellow
RESET = "\033[0m"

# Banner text -> which sketch is running. Lets the script tell you what is
# actually on each board instead of trusting the labels on the cables.
SKETCH_HINTS = [
    ("FIXED FREQUENCY TX", "fixed TX"),
    ("FIXED FREQUENCY RX", "fixed RX"),
    ("BASIC FHSS TX", "basic FHSS TX"),
    ("ADAPTIVE FHSS TX", "adaptive FHSS TX"),
    ("FHSS RX", "FHSS RX"),
]

lock = threading.Lock()
start = time.time()
detected = {}


def pump(port, baud, color, logfile, stop_event):
    try:
        ser = serial.Serial(port, baud, timeout=0.2)
    except Exception as exc:
        with lock:
            print(f"{color}[{port}] could not open: {exc}{RESET}")
        return

    # Pulse DTR/RTS low so the board restarts and we catch its banner.
    try:
        ser.dtr = False
        ser.rts = False
        time.sleep(0.1)
        ser.reset_input_buffer()
    except Exception:
        pass

    with lock:
        print(f"{color}[{port}] open at {baud} baud{RESET}")

    buf = b""
    while not stop_event.is_set():
        try:
            chunk = ser.read(256)
        except Exception as exc:
            with lock:
                print(f"{color}[{port}] read error: {exc}{RESET}")
            break

        if not chunk:
            continue

        buf += chunk
        while b"\n" in buf:
            raw, buf = buf.split(b"\n", 1)
            line = raw.decode("utf-8", errors="replace").rstrip("\r")
            if not line.strip():
                continue

            for needle, name in SKETCH_HINTS:
                if needle in line and detected.get(port) != name:
                    detected[port] = name
                    with lock:
                        print(f"{color}>>> {port} is running: {name}{RESET}")

            stamp = time.time() - start
            out = f"[{stamp:7.2f}s] {port:<6} | {line}"
            with lock:
                print(f"{color}{out}{RESET}")
                logfile.write(out + "\n")
                logfile.flush()

    ser.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ports", nargs=2, default=["COM3", "COM14"])
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--seconds", type=float, default=0,
                    help="stop after this many seconds (0 = until Ctrl+C)")
    args = ap.parse_args()

    os.makedirs(OUTDIR, exist_ok=True)
    name = datetime.datetime.now().strftime("dual_%Y%m%d_%H%M%S.log")
    path = os.path.join(OUTDIR, name)

    print(f"logging to {path}")
    print("close the Arduino IDE serial monitor if a port fails to open\n")

    stop_event = threading.Event()
    with open(path, "w", encoding="utf-8") as logfile:
        threads = [
            threading.Thread(target=pump,
                             args=(p, args.baud, COLORS[i % 2], logfile, stop_event),
                             daemon=True)
            for i, p in enumerate(args.ports)
        ]
        for t in threads:
            t.start()

        try:
            if args.seconds > 0:
                time.sleep(args.seconds)
            else:
                while any(t.is_alive() for t in threads):
                    time.sleep(0.2)
        except KeyboardInterrupt:
            print("\nstopping...")
        finally:
            stop_event.set()
            for t in threads:
                t.join(timeout=1.5)

    print(f"\nsaved: {path}")
    if detected:
        print("sketches detected:")
        for port, sketch in detected.items():
            print(f"  {port}: {sketch}")
    else:
        print("no banner seen - press the EN/reset button on both boards and rerun")


if __name__ == "__main__":
    main()
