"""
Automated test matrix: compiles, uploads, runs and records every experiment.

    python analysis/run_matrix.py                 # all 9 runs
    python analysis/run_matrix.py --runs 7 8 9    # just these
    python analysis/run_matrix.py --list          # show the matrix
    python analysis/run_matrix.py --tx COM3 --rx COM14

Close the Arduino IDE serial monitor first - Windows gives one program
exclusive access to a COM port.

For each run it:
  1. copies firmware/shared/rf_config.h into both sketch folders
  2. compiles each sketch with that run's -D flags
  3. uploads to the right board (skipped if that board already has the
     identical binary from the previous run)
  4. resets the receiver, then the transmitter a moment later
  5. captures both serial streams until the receiver prints its summary
  6. parses the CSV line and writes it into results/results.csv

Nothing here transmits interference. Denied channels are emulated in
firmware - see firmware/shared/rf_config.h.
"""

import argparse
import csv
import datetime
import os
import shutil
import subprocess
import sys
import threading
import time

try:
    import serial
except ImportError:
    sys.exit("pyserial missing:  pip install pyserial")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FW = os.path.join(ROOT, "firmware")
RESULTS = os.path.join(ROOT, "results")
SHARED_H = os.path.join(FW, "shared", "rf_config.h")

CLI = os.path.join(os.environ.get("LOCALAPPDATA", ""),
                   "Programs", "Arduino IDE", "resources", "app",
                   "lib", "backend", "resources", "arduino-cli.exe")
FQBN = "esp32:esp32:esp32"

BUILD_ROOT = os.path.join(os.environ.get("TEMP", "."), "dcs_builds")

# Which -D flags each sketch actually reads. Anything not listed here is
# left out of its build, so sketches that ignore a flag are not
# needlessly recompiled and re-uploaded when it changes.
SKETCH_DEFINES = {
    "01_fixed_tx":     [],
    "02_fixed_rx":     ["DENY_MASK"],
    "03_fhss_tx":      [],
    "04_fhss_rx":      ["DENY_MASK", "RESYNC_ENABLED", "ADAPTIVE_RUN"],
    "05_adaptive_tx":  ["DENY_MASK", "JAM_RSSI_THRESHOLD", "COOLDOWN_CYCLES"],
}

# DENY_MASK bit i denies hopFrequencies[i].
#   0x01 -> 433.05   0x04 -> 433.85   0x14 -> 433.85 + 434.65
RUNS = [
    dict(id=1, tx="01_fixed_tx", rx="02_fixed_rx", d={},
         label="Fixed frequency, nothing denied",
         expect="~0% loss - the control"),
    dict(id=2, tx="01_fixed_tx", rx="02_fixed_rx", d={"DENY_MASK": 0x01},
         label="Fixed frequency, its one channel denied",
         expect="100% loss - a fixed link has nowhere to go"),
    dict(id=3, tx="03_fhss_tx", rx="04_fhss_rx", d={"RESYNC_ENABLED": 0},
         label="Basic FHSS, nothing denied",
         expect="low loss, even spread across all 5 channels"),
    dict(id=4, tx="03_fhss_tx", rx="04_fhss_rx",
         d={"RESYNC_ENABLED": 0, "DENY_MASK": 0x04},
         label="Basic FHSS, 1 denied, no recovery",
         expect="collapse - RX stranded on the denied channel"),
    dict(id=5, tx="03_fhss_tx", rx="04_fhss_rx",
         d={"RESYNC_ENABLED": 1, "DENY_MASK": 0x04},
         label="Basic FHSS + rendezvous, 1 denied",
         expect="partial loss, repeated resync events"),
    dict(id=6, tx="03_fhss_tx", rx="04_fhss_rx",
         d={"RESYNC_ENABLED": 1, "DENY_MASK": 0x14},
         label="Basic FHSS + rendezvous, 2 denied",
         expect="roughly double run 5"),
    dict(id=7, tx="05_adaptive_tx", rx="04_fhss_rx",
         d={"RESYNC_ENABLED": 1, "ADAPTIVE_RUN": 1},
         label="Adaptive FHSS, nothing denied",
         expect="close to run 3 plus sensing overhead; real RSSI readings"),
    dict(id=8, tx="05_adaptive_tx", rx="04_fhss_rx",
         d={"RESYNC_ENABLED": 1, "ADAPTIVE_RUN": 1, "DENY_MASK": 0x04},
         label="Adaptive FHSS, 1 denied",
         expect="low loss, 0 packets on the denied channel"),
    dict(id=9, tx="05_adaptive_tx", rx="04_fhss_rx",
         d={"RESYNC_ENABLED": 1, "ADAPTIVE_RUN": 1, "DENY_MASK": 0x14},
         label="Adaptive FHSS, 2 denied",
         expect="slightly worse than run 8, far better than run 6"),
]

CSV_HEADER = ["run_id", "mode", "resync", "denied_count", "sent", "received",
              "lost", "loss_pct", "avg_rssi", "resync_events", "avg_lqi",
              "notes"]


def log(msg, indent=0):
    print(" " * indent + msg, flush=True)


def defines_for(sketch, run_defines):
    """Only the flags this sketch actually reads, in a stable order."""
    keys = SKETCH_DEFINES.get(sketch, [])
    return {k: run_defines[k] for k in keys if k in run_defines}


def compile_sketch(sketch, defines):
    sketch_dir = os.path.join(FW, sketch)
    shutil.copy(SHARED_H, os.path.join(sketch_dir, "rf_config.h"))

    tag = "_".join(f"{k}{v}" for k, v in sorted(defines.items())) or "default"
    build_path = os.path.join(BUILD_ROOT, f"{sketch}__{tag}")

    cmd = [CLI, "compile", "--fqbn", FQBN, "--build-path", build_path]
    if defines:
        flags = " ".join(f"-D{k}={v}" for k, v in sorted(defines.items()))
        cmd += ["--build-property", f"compiler.cpp.extra_flags={flags}"]
    cmd.append(sketch_dir)

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        log("COMPILE FAILED", 4)
        log((res.stderr or res.stdout)[-1500:], 6)
        return None
    return build_path


def settle_port(port):
    """
    Normalise the DTR/RTS lines and let Windows fully release the handle.

    esptool drives those two lines to walk the ESP32 into its bootloader.
    If we have just had the port open for a capture, Windows can still be
    holding the handle, or the lines can be left asserted - either way
    esptool resets the board but it boots the sketch instead, and the
    upload fails with "wrong boot mode / not in download mode".
    """
    try:
        s = serial.Serial(port, 115200, timeout=0.1)
        s.dtr = False
        s.rts = False
        time.sleep(0.15)
        s.close()
    except Exception:
        pass           # nothing had it open, which is the good case
    time.sleep(0.8)    # let the driver release before esptool grabs it


def upload(sketch, build_path, port, attempts=3):
    cmd = [CLI, "upload", "--fqbn", FQBN, "--port", port,
           "--input-dir", build_path, os.path.join(FW, sketch)]

    for attempt in range(1, attempts + 1):
        settle_port(port)
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            return True

        output = (res.stderr or "") + (res.stdout or "")
        boot_mode = "boot mode" in output.lower() or "download mode" in output.lower()

        if attempt < attempts:
            log(f"upload attempt {attempt} failed"
                f"{' (wrong boot mode)' if boot_mode else ''}, retrying...", 4)
            time.sleep(1.5 * attempt)
            continue

        log("UPLOAD FAILED after all attempts", 4)
        log(output[-1200:], 6)
        if boot_mode:
            log("the board would not enter download mode. Close the Arduino "
                "IDE serial monitor; if it persists, hold BOOT while this "
                "retries.", 4)
        return False
    return False


def reset_board(ser):
    """Pulse EN low via RTS, leaving GPIO0 high so it boots the sketch."""
    ser.dtr = False
    ser.rts = True
    time.sleep(0.12)
    ser.rts = False


class Capture:
    """Reads both ports onto one timeline until the summary appears."""

    def __init__(self, tx_port, rx_port, logfile):
        self.lines = []
        self.csv_line = None
        self.logfile = logfile
        self.lock = threading.Lock()
        self.start = time.time()
        self.stop = threading.Event()
        self.tx = serial.Serial(tx_port, 115200, timeout=0.2)
        self.rx = serial.Serial(rx_port, 115200, timeout=0.2)

    def _pump(self, ser, name):
        buf = b""
        while not self.stop.is_set():
            try:
                chunk = ser.read(256)
            except Exception:
                break
            if not chunk:
                continue
            buf += chunk
            while b"\n" in buf:
                raw, buf = buf.split(b"\n", 1)
                line = raw.decode("utf-8", errors="replace").rstrip("\r")
                if not line.strip():
                    continue
                stamp = time.time() - self.start
                entry = f"[{stamp:7.2f}s] {name:<6} | {line}"
                with self.lock:
                    self.lines.append(entry)
                    self.logfile.write(entry + "\n")
                    self.logfile.flush()
                    if line.startswith("CSV,"):
                        self.csv_line = line

    def run(self, tx_port, rx_port, timeout):
        t1 = threading.Thread(target=self._pump, args=(self.tx, tx_port), daemon=True)
        t2 = threading.Thread(target=self._pump, args=(self.rx, rx_port), daemon=True)
        t1.start()
        t2.start()

        # Receiver first so it is already listening, transmitter after.
        reset_board(self.rx)
        time.sleep(2.5)
        reset_board(self.tx)

        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.csv_line:
                time.sleep(0.5)        # let the last lines land
                break
            time.sleep(0.2)

        self.stop.set()
        t1.join(timeout=1.5)
        t2.join(timeout=1.5)

        # Leave both lines deasserted so the next upload's auto-reset works.
        for ser in (self.tx, self.rx):
            try:
                ser.dtr = False
                ser.rts = False
            except Exception:
                pass
            ser.close()
        time.sleep(1.0)
        return self.csv_line


def summarise(lines):
    """A few extra facts pulled from the log for the notes column."""
    per_channel = [l.split("|", 1)[1].strip() for l in lines if " MHz : " in l]
    sensed = sum(1 for l in lines if "sensed " in l)
    occupied = sum(1 for l in lines if "OCCUPIED" in l)
    denied = sum(1 for l in lines if "[denied]" in l)
    resync = sum(1 for l in lines if "lost sync" in l)
    bits = []
    if denied:
        bits.append(f"{denied} denied drops")
    if occupied:
        bits.append(f"{occupied} occupied detections")
    if sensed:
        bits.append(f"{sensed} channel senses")
    if resync:
        bits.append(f"{resync} resyncs")
    return "; ".join(bits), per_channel


def write_result(run, csv_line, note):
    rows = {}
    path = os.path.join(RESULTS, "results.csv")
    if os.path.exists(path):
        with open(path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                rows[row["run_id"]] = row

    parts = csv_line.split(",")[1:]          # drop the "CSV" marker
    mode, resync, denied, sent, recv, lost, loss, rssi, resync_ev = parts[:9]
    lqi = parts[9] if len(parts) > 9 else ""   # only the FHSS receiver emits it

    rows[str(run["id"])] = dict(
        run_id=str(run["id"]), mode=mode, resync=resync, denied_count=denied,
        sent=sent, received=recv, lost=lost, loss_pct=loss, avg_rssi=rssi,
        resync_events=resync_ev, avg_lqi=lqi, notes=note or run["label"])

    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_HEADER)
        w.writeheader()
        for key in sorted(rows, key=lambda x: int(x)):
            w.writerow(rows[key])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tx", default="COM3")
    ap.add_argument("--rx", default="COM14")
    ap.add_argument("--runs", nargs="*", type=int)
    ap.add_argument("--timeout", type=float, default=200)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--demo", action="store_true",
                    help="flash both boards in continuous demo mode for the "
                         "dashboard, then exit")
    args = ap.parse_args()

    if args.demo:
        if not os.path.exists(CLI):
            sys.exit(f"arduino-cli not found at:\n  {CLI}")
        os.makedirs(BUILD_ROOT, exist_ok=True)

        demo = [
            ("TX", "05_adaptive_tx", args.tx, {"DEMO_MODE": 1}),
            ("RX", "04_fhss_rx", args.rx,
             {"DEMO_MODE": 1, "RESYNC_ENABLED": 1, "ADAPTIVE_RUN": 1}),
        ]
        for role, sketch, port, d in demo:
            log(f"{role}: compiling {sketch} (demo mode)")
            build = compile_sketch(sketch, d)
            if not build:
                sys.exit(1)
            log(f"{role}: uploading to {port}")
            if not upload(sketch, build, port):
                sys.exit(1)

        log("\nboards are running continuously. now start the dashboard:")
        log(f"  python analysis/dashboard.py --tx {args.tx} --rx {args.rx}\n")
        return

    if args.list:
        for r in RUNS:
            flags = " ".join(f"{k}={v}" for k, v in sorted(r["d"].items())) or "-"
            print(f"  run {r['id']}: {r['label']}")
            print(f"           {r['tx']} + {r['rx']}   [{flags}]")
            print(f"           expect: {r['expect']}")
        return

    if not os.path.exists(CLI):
        sys.exit(f"arduino-cli not found at:\n  {CLI}")

    os.makedirs(RESULTS, exist_ok=True)
    os.makedirs(BUILD_ROOT, exist_ok=True)

    # Fail early and clearly rather than halfway through the matrix.
    for port in (args.tx, args.rx):
        try:
            serial.Serial(port, 115200, timeout=0.1).close()
        except Exception as exc:
            sys.exit(f"\ncannot open {port}: {exc}\n"
                     "Close the Arduino IDE serial monitor (and any other "
                     "program holding the port), then run this again.\n")

    selected = [r for r in RUNS if not args.runs or r["id"] in args.runs]
    log(f"\n{len(selected)} run(s) queued   TX={args.tx}  RX={args.rx}\n")

    loaded = {}        # port -> (sketch, defines tuple) currently flashed
    done, failed = [], []

    for run in selected:
        log("=" * 62)
        log(f"RUN {run['id']}: {run['label']}")
        log(f"expect: {run['expect']}", 8)
        log("=" * 62)

        ok = True
        for role, sketch, port in (("TX", run["tx"], args.tx),
                                   ("RX", run["rx"], args.rx)):
            d = defines_for(sketch, run["d"])
            key = (sketch, tuple(sorted(d.items())))

            if loaded.get(port) == key:
                log(f"{role}: {sketch} already flashed, skipping", 2)
                continue

            flags = " ".join(f"-D{k}={v}" for k, v in sorted(d.items())) or "no flags"
            log(f"{role}: compiling {sketch} ({flags})", 2)
            build = compile_sketch(sketch, d)
            if not build:
                ok = False
                break

            log(f"{role}: uploading to {port}", 2)
            if not upload(sketch, build, port):
                ok = False
                break
            loaded[port] = key

        if not ok:
            failed.append(run["id"])
            continue

        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        logpath = os.path.join(RESULTS, f"run{run['id']}_{stamp}.log")

        log("running... (~2.5 min)", 2)
        with open(logpath, "w", encoding="utf-8") as fh:
            cap = Capture(args.tx, args.rx, fh)
            csv_line = cap.run(args.tx, args.rx, args.timeout)

        if not csv_line:
            log("NO SUMMARY - run timed out", 2)
            log(f"log: {logpath}", 2)
            failed.append(run["id"])
            continue

        note, per_channel = summarise(cap.lines)
        write_result(run, csv_line, note)

        parts = csv_line.split(",")
        log(f"result: {parts[5]}/{parts[4]} received, {parts[7]}% loss, "
            f"RSSI {parts[8]} dBm", 2)
        if note:
            log(f"        {note}", 2)
        for pc in per_channel:
            log(f"        {pc}", 2)
        log(f"log: {os.path.basename(logpath)}", 2)
        done.append(run["id"])

    log("\n" + "=" * 62)
    log(f"completed: {done or 'none'}")
    if failed:
        log(f"failed   : {failed}")
    log("=" * 62)
    log("\nnow run:  python analysis/plot_results.py\n")


if __name__ == "__main__":
    main()
