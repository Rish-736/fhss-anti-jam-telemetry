"""
Flash both boards with the continuous demo firmware for the dashboard.

    python analysis/flash_demo.py                 # both boards
    python analysis/flash_demo.py --only rx       # just the receiver
    python analysis/flash_demo.py --tx COM3 --rx COM14

Why this exists separately from run_matrix.py --demo
----------------------------------------------------
Some ESP32 DevKit boards have a weak or missing auto-reset circuit, so
the usual DTR/RTS dance never walks them into the bootloader and every
upload dies with "Wrong boot mode detected (0x13)". The COM14 board in
this project is one of them.

The fix is to hold its BOOT button, but a normal upload gives you about
two seconds to do that. This script retries for a full minute, so you
can press BOOT and keep holding until it takes.

The firmware it writes is the DEMO build: DEMO_MODE=1 makes the
sequence number wrap instead of stopping at 100, so the link runs
indefinitely and the dashboard never goes dead mid-demonstration.
"""

import argparse
import os
import shutil
import subprocess
import sys
import time

try:
    import serial
except ImportError:
    raise SystemExit("pyserial missing:  pip install pyserial")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FW = os.path.join(ROOT, "firmware")
SHARED_H = os.path.join(FW, "shared", "rf_config.h")

CLI = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs",
                   "Arduino IDE", "resources", "app", "lib", "backend",
                   "resources", "arduino-cli.exe")
FQBN = "esp32:esp32:esp32"
BUILD_ROOT = os.path.join(os.environ.get("TEMP", "."), "dcs_builds")

# Exactly what run_matrix.py --demo builds, kept in step with it.
TARGETS = {
    "tx": ("05_adaptive_tx", {"DEMO_MODE": 1}),
    "rx": ("04_fhss_rx", {"DEMO_MODE": 1, "RESYNC_ENABLED": 1,
                          "ADAPTIVE_RUN": 1}),
}

RETRY_SECONDS = 90


def log(msg, indent=0):
    print(" " * indent + msg, flush=True)


def compile_sketch(sketch, defines):
    shutil.copy(SHARED_H, os.path.join(FW, sketch, "rf_config.h"))
    tag = "_".join(f"{k}{v}" for k, v in sorted(defines.items())) or "default"
    build_path = os.path.join(BUILD_ROOT, f"{sketch}__{tag}")

    cmd = [CLI, "compile", "--fqbn", FQBN, "--build-path", build_path]
    flags = " ".join(f"-D{k}={v}" for k, v in sorted(defines.items()))
    if flags:
        cmd += ["--build-property", f"compiler.cpp.extra_flags={flags}"]
    cmd.append(os.path.join(FW, sketch))

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        log("COMPILE FAILED", 4)
        log((res.stderr or res.stdout)[-1200:], 6)
        return None
    return build_path


def into_bootloader(port):
    """Drive the classic EN / GPIO0 sequence over DTR and RTS.

    Harmless on a board whose auto-reset works, and occasionally enough
    on a board whose auto-reset is merely slow.
    """
    try:
        s = serial.Serial(port, 115200)
    except Exception:
        return
    try:
        s.setDTR(False)
        s.setRTS(True)          # EN low: hold in reset
        time.sleep(0.12)
        s.setDTR(True)          # GPIO0 low
        time.sleep(0.05)
        s.setRTS(False)         # EN high while GPIO0 is still low
        time.sleep(0.12)
        s.setDTR(False)         # release GPIO0
    finally:
        s.close()
    time.sleep(0.25)


def port_free(port):
    try:
        serial.Serial(port).close()
        return True
    except Exception:
        return False


def upload(sketch, build_path, port):
    cmd = [CLI, "upload", "--fqbn", FQBN, "--port", port,
           "--input-dir", build_path, os.path.join(FW, sketch)]

    deadline = time.time() + RETRY_SECONDS
    attempt = 0
    boot_mode_seen = False

    while time.time() < deadline:
        attempt += 1
        into_bootloader(port)
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            log(f"uploaded on attempt {attempt}", 4)
            return True

        out = ((res.stderr or "") + (res.stdout or "")).lower()
        if "boot mode" in out or "download mode" in out:
            if not boot_mode_seen:
                boot_mode_seen = True
                log("", 0)
                log("*" * 64, 2)
                log("This board is not entering download mode.", 2)
                log("", 2)
                log("TRY THIS FIRST - it is usually a wedged USB adapter,", 2)
                log("not a broken board:", 2)
                log("  1. unplug this board's USB cable", 2)
                log("  2. plug it back in (a different USB port is even", 2)
                log("     better), wait two seconds", 2)
                log("  3. run this command again", 2)
                log("", 2)
                log("IF THAT DOES NOT WORK, do it by hand while this", 2)
                log("keeps retrying:", 2)
                log("  1. press and HOLD the BOOT button", 2)
                log("  2. with BOOT still held, tap EN (or RST) once", 2)
                log("  3. release EN, but KEEP HOLDING BOOT", 2)
                log("  4. keep holding until this prints 'uploaded'", 2)
                log("", 2)
                log(f"Retrying for {RETRY_SECONDS}s...", 2)
                log("*" * 64, 2)
                log("", 0)
            else:
                log(f"attempt {attempt} - still not in download mode, "
                    f"{max(0, int(deadline - time.time()))}s left", 4)
        elif "access is denied" in out or "permission" in out:
            log(f"attempt {attempt} - port busy. Close the Arduino IDE "
                f"serial monitor and any running dashboard.py.", 4)
        else:
            tail = [l for l in
                    ((res.stderr or "") + (res.stdout or "")).splitlines()
                    if l.strip()]
            log(f"attempt {attempt} - {tail[-1] if tail else 'failed'}", 4)
        time.sleep(0.8)

    log("GAVE UP after %ds" % RETRY_SECONDS, 4)
    return False


def verify(port, want_lqi):
    """Read the banner back and confirm the right firmware is running."""
    log(f"verifying {port}...", 2)
    try:
        s = serial.Serial(port, 115200, timeout=0.3)
    except Exception as exc:
        log(f"could not open {port}: {exc}", 4)
        return False

    text = ""
    t = time.time()
    while time.time() - t < 12:
        chunk = s.read(512)
        if chunk:
            text += chunk.decode("utf-8", "replace")
        if want_lqi and "LQI:" in text:
            break
        if not want_lqi and text.count("TX: SEQ:") >= 3:
            break
    s.close()

    ok = True
    if want_lqi:
        if "LQI:" in text:
            log("receiver is reporting LQI", 4)
        else:
            log("no LQI field seen - old receiver firmware?", 4)
            ok = False
    else:
        n = text.count("TX: SEQ:")
        log(f"transmitter sent {n} packets in the sample window", 4)
        ok = n > 0
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tx", default="COM3")
    ap.add_argument("--rx", default="COM14")
    ap.add_argument("--only", choices=["tx", "rx"],
                    help="flash only one of the two boards")
    ap.add_argument("--no-verify", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(CLI):
        sys.exit(f"arduino-cli not found at:\n  {CLI}")
    os.makedirs(BUILD_ROOT, exist_ok=True)

    roles = [args.only] if args.only else ["tx", "rx"]
    ports = {"tx": args.tx, "rx": args.rx}

    for role in roles:
        port = ports[role]
        if not port_free(port):
            sys.exit(f"\n{port} is in use. Close the Arduino IDE serial "
                     f"monitor and any running dashboard.py, then retry.\n")

    failures = []
    for role in roles:
        sketch, defines = TARGETS[role]
        port = ports[role]
        log(f"\n{role.upper()}: {sketch} -> {port}")
        build = compile_sketch(sketch, defines)
        if not build:
            failures.append(role)
            continue
        if not upload(sketch, build, port):
            failures.append(role)
            continue
        if not args.no_verify:
            time.sleep(1.0)
            verify(port, want_lqi=(role == "rx"))

    print()
    if failures:
        log("FAILED: " + ", ".join(f.upper() for f in failures))
        log("Unplug and replug that board, then run:", 2)
        log(f"python analysis/flash_demo.py --only {failures[0]}", 4)
        sys.exit(1)

    log("both boards are running the continuous demo firmware.")
    log("now start the dashboard:", 2)
    log(f"python analysis/dashboard.py --tx {args.tx} --rx {args.rx}", 4)
    print()


if __name__ == "__main__":
    main()
