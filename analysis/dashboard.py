"""
Live ground-station dashboard.

    python analysis/dashboard.py                    # COM3 + COM14
    python analysis/dashboard.py --tx COM3 --rx COM14 --port 8080

Then open http://localhost:8080

Reads both boards' serial output, keeps a live picture of the link, and
serves it to a web page that polls a few times a second. The page can
also deny a channel on the fly, which is what makes this demonstrable in
front of an audience rather than just readable.

Requires the runtime-denial firmware (boards must accept "DENY <mask>"
on serial). Without it everything still displays; only the click-to-jam
buttons do nothing.

Nothing here transmits interference - denial is emulated in firmware.
Close the Arduino IDE serial monitor before running.
"""

import argparse
import json
import os
import re
import sys
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

try:
    import serial
except ImportError:
    raise SystemExit("pyserial missing:  pip install pyserial")

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = os.path.join(HERE, "dashboard.html")

CHANNELS = [433.05, 433.45, 433.85, 434.25, 434.65]

# Packets kept in the rolling delivery window, and how many of the newest
# are excluded from the figure - a transmission the receiver has not had
# time to report yet is not a loss.
WINDOW = 25
SETTLE = 2

# No valid packet for this long means the link is down, not merely lossy.
LINK_DOWN_AFTER = 4.0


def channel_index(mhz):
    """Map a printed frequency back to its hop index, tolerating rounding."""
    try:
        val = float(mhz)
    except (TypeError, ValueError):
        return None
    for i, c in enumerate(CHANNELS):
        if abs(c - val) < 0.02:
            return i
    return None


class LinkState:
    """Everything the page needs, rebuilt continuously from serial text."""

    def __init__(self):
        self.lock = threading.Lock()
        self.reset()

    def reset(self):
        self.channels = [
            dict(mhz=c, rssi=None, denied=False, blacklisted=False,
                 rx_count=0, last_seen=0.0)
            for c in CHANNELS
        ]
        self.tx_hop = None
        self.rx_hop = None
        self.mode = "waiting"
        self.sent = 0
        self.received = 0
        self.total = 100
        self.loss_pct = 0.0
        self.last_rssi = None
        self.last_lqi = None
        self.resyncs = 0
        self.denied_drops = 0
        self.occupied_events = 0
        self.events = deque(maxlen=60)
        self.loss_trace = deque(maxlen=120)
        self.complete = False
        self.pinned = False
        self.started = time.time()

        # Rolling delivery window. The board's own tally only resets once
        # per 100 packets, so on its own it takes two minutes to reflect a
        # channel being denied or released - far too slow to demonstrate
        # live. This tracks the last WINDOW transmissions directly.
        self.window = deque(maxlen=WINDOW)
        # Bounded, so a receipt that is never claimed cannot survive a
        # sequence-number wrap and credit the wrong packet later.
        self.early = deque(maxlen=8)
        self.last_rx_at = 0.0

    def event(self, kind, text):
        self.events.appendleft(
            dict(t=round(time.time() - self.started, 1), kind=kind, text=text))

    # ---- rolling delivery window -------------------------------------
    # The two boards are on separate serial streams, and the transmitter
    # prints only after SendData() returns - so the receiver's line for a
    # packet frequently arrives first. A receipt that has no window entry
    # yet is held briefly and applied when the transmitter catches up.
    def note_sent(self, seq):
        got = seq in self.early
        if got:
            self.early.remove(seq)
        elif self.last_rx_at == 0.0:
            # Opening the serial ports resets both boards, and the
            # receiver spends the first few seconds finding the schedule.
            # Those packets are an artefact of the USB reset, not of the
            # radio link, so the window starts at the first real receipt.
            return
        self.window.append([seq, got])

    def note_received(self, seq):
        self.last_rx_at = time.time()
        for entry in reversed(self.window):
            if entry[0] == seq:
                entry[1] = True
                return
        self.early.append(seq)

    def live_delivery(self):
        """Delivered fraction over the window, ignoring packets still in
        flight. Returns (delivered, counted) or None when too few."""
        usable = list(self.window)[:-SETTLE] if len(self.window) > SETTLE \
            else []
        if len(usable) < 5:
            return None
        return sum(1 for _, got in usable if got), len(usable)

    def link_down(self):
        return (self.last_rx_at > 0
                and time.time() - self.last_rx_at > LINK_DOWN_AFTER)

    def apply_mask(self, mask):
        """Set which channels are blocked, and clear what the old mask
        left behind.

        A released channel kept its SKIPPED badge and the synthetic
        -35 dBm reading from while it was blocked, so it still looked
        busy on screen long after it had been let go.
        """
        for i in range(len(CHANNELS)):
            denied = bool((mask >> i) & 1)
            if self.channels[i]["denied"] and not denied:
                self.channels[i]["blacklisted"] = False
                self.channels[i]["rssi"] = None
            self.channels[i]["denied"] = denied

    def clear_blacklists(self):
        for c in self.channels:
            if not c["denied"]:
                c["blacklisted"] = False

    def push_trace(self):
        """The trace plots the live windowed loss, so it responds within
        seconds of a channel being denied rather than within minutes."""
        live = self.live_delivery()
        if live is not None:
            self.loss_trace.append(round((1 - live[0] / live[1]) * 100, 1))

    def snapshot(self):
        with self.lock:
            live = self.live_delivery()
            return dict(
                live_delivered=None if live is None else live[0],
                live_window=None if live is None else live[1],
                live_loss_pct=None if live is None
                else round((1 - live[0] / live[1]) * 100, 1),
                link_down=self.link_down(),
                channels=self.channels,
                tx_hop=self.tx_hop,
                rx_hop=self.rx_hop,
                mode=self.mode,
                sent=self.sent,
                received=self.received,
                total=self.total,
                loss_pct=round(self.loss_pct, 2),
                last_rssi=self.last_rssi,
                last_lqi=self.last_lqi,
                resyncs=self.resyncs,
                denied_drops=self.denied_drops,
                occupied_events=self.occupied_events,
                events=list(self.events),
                loss_trace=list(self.loss_trace),
                complete=self.complete,
                pinned=self.pinned,
                uptime=round(time.time() - self.started, 1),
            )


STATE = LinkState()

# --- line patterns -------------------------------------------------------
RE_SENSED = re.compile(r"sensed ([\d.]+) MHz -> RSSI (-?\d+)")
RE_OCCUPIED = re.compile(r">> ([\d.]+) MHz OCCUPIED")
RE_TX_HOP = re.compile(
    r"TX(?:\[FIXED\])?: SEQ:(\d+),NEXT:\d+ \| CURRENT: ([\d.]+) MHz")
RE_TX_FIXED = re.compile(r"TX: SEQ:(\d+)\s*$")
RE_MODE = re.compile(r"MODE NOW (FIXED|HOP)")
# LQI group is optional so logs recorded before it was added still parse.
RE_RX_HOP = re.compile(
    r"RX: SEQ:(\d+),NEXT:(\d+) \| FREQ: ([\d.]+) MHz \| RSSI: (-?\d+) dBm"
    r"(?: \| LQI: (\d+))? \| Received: (\d+)")
RE_RX_FIXED = re.compile(r"RX SEQ:(\d+) \| RSSI:(-?\d+) dBm \| Received:(\d+)")
RE_DENIED = re.compile(r"\[denied\] dropped a packet on ([\d.]+) MHz")
RE_RESYNC = re.compile(r"lost sync - returning to rendezvous")
RE_DENYSET = re.compile(r"DENY MASK NOW (\d+)")


def handle_line(line, source):
    s = STATE
    with s.lock:
        # Matched case-insensitively: the banner says "ADAPTIVE FHSS TX"
        # but the role line says "adaptive FHSS TX", and the lower-case
        # one arrives second and would otherwise reset this to "basic".
        upper = line.upper()
        if "FHSS TX" in upper or "FIXED FREQUENCY TX" in upper:
            s.mode = ("adaptive" if "ADAPTIVE" in upper
                      else "fixed" if "FIXED" in upper else "basic")
            s.event("info", f"transmitter: {s.mode}")
            return

        if "TEST COMPLETE" in line:
            s.complete = True
            s.event("info", "run complete")
            return

        m = RE_SENSED.search(line)
        if m:
            idx = channel_index(m.group(1))
            if idx is not None:
                s.channels[idx]["rssi"] = int(m.group(2))
                s.channels[idx]["last_seen"] = time.time()
            return

        m = RE_OCCUPIED.search(line)
        if m:
            idx = channel_index(m.group(1))
            if idx is not None:
                s.channels[idx]["blacklisted"] = True
                s.occupied_events += 1
                s.event("block", f"{CHANNELS[idx]:.2f} MHz occupied - avoiding")
            return

        m = RE_TX_HOP.search(line)
        if m:
            s.sent = int(m.group(1)) + 1
            s.note_sent(int(m.group(1)))
            idx = channel_index(m.group(2))
            if idx is not None:
                s.tx_hop = idx
                # Reaching a channel clears its stale blacklist flag.
                s.channels[idx]["blacklisted"] = False
            s.push_trace()
            return

        m = RE_TX_FIXED.search(line)
        if m:
            s.sent = int(m.group(1)) + 1
            s.note_sent(int(m.group(1)))
            s.tx_hop = 0
            s.push_trace()
            return

        m = RE_RX_HOP.search(line)
        if m:
            idx = channel_index(m.group(3))
            s.received = int(m.group(6))
            s.last_rssi = int(m.group(4))
            if m.group(5) is not None:
                s.last_lqi = int(m.group(5))
            s.note_received(int(m.group(1)))
            if idx is not None:
                s.rx_hop = idx
                s.channels[idx]["rx_count"] += 1
            s.loss_pct = max(0.0, (s.sent - s.received) / max(s.sent, 1) * 100)
            s.push_trace()
            return

        m = RE_RX_FIXED.search(line)
        if m:
            s.received = int(m.group(3))
            s.last_rssi = int(m.group(2))
            s.note_received(int(m.group(1)))
            s.rx_hop = 0
            s.channels[0]["rx_count"] += 1
            s.loss_pct = max(0.0, (s.sent - s.received) / max(s.sent, 1) * 100)
            s.push_trace()
            return

        m = RE_DENIED.search(line)
        if m:
            idx = channel_index(m.group(1))
            s.denied_drops += 1
            if idx is not None:
                s.channels[idx]["denied"] = True
            s.loss_pct = max(0.0, (s.sent - s.received) / max(s.sent, 1) * 100)
            return

        if RE_RESYNC.search(line):
            s.resyncs += 1
            s.event("warn", "lost sync - returning to rendezvous")
            return

        m = RE_MODE.search(line)
        if m:
            s.pinned = (m.group(1) == "FIXED")
            s.mode = "fixed (pinned)" if s.pinned else "adaptive"
            s.event("info", f"link mode: {s.mode}")
            return

        m = RE_DENYSET.search(line)
        if m:
            s.apply_mask(int(m.group(1)))
            s.event("info", f"deny mask now 0x{int(m.group(1)):02X}")
            return


class Boards:
    """Owns both serial ports: pumps lines in, sends commands out."""

    def __init__(self, tx_port, rx_port):
        self.ports = {}
        self.failed = []
        self.lock = threading.Lock()
        for name, port in (("TX", tx_port), ("RX", rx_port)):
            try:
                self.ports[name] = self._open(port)
                print(f"  {name}: {port} open")
            except Exception as exc:
                print(f"  {name}: {port} FAILED - {exc}")
                self.failed.append((name, port, exc))

    @staticmethod
    def _open(port):
        """Open without rebooting the board.

        The ESP32 auto-reset circuit is driven from DTR and RTS, so a
        plain serial.Serial(port) pulses EN and restarts the sketch -
        which cost about a minute of resynchronising every time the
        dashboard was started. Deasserting both lines before opening
        leaves the running link undisturbed.
        """
        s = serial.Serial()
        s.port = port
        s.baudrate = 115200
        s.timeout = 0.2
        s.dtr = False
        s.rts = False
        s.open()
        return s

    def start(self):
        for name, ser in self.ports.items():
            threading.Thread(target=self._pump, args=(name, ser),
                             daemon=True).start()

    def _pump(self, name, ser):
        buf = b""
        while True:
            try:
                chunk = ser.read(256)
            except Exception:
                return
            if not chunk:
                continue
            buf += chunk
            while b"\n" in buf:
                raw, buf = buf.split(b"\n", 1)
                line = raw.decode("utf-8", errors="replace").rstrip("\r")
                if line.strip():
                    handle_line(line, name)

    def send(self, text):
        with self.lock:
            for ser in self.ports.values():
                try:
                    ser.write((text + "\n").encode())
                except Exception:
                    pass


BOARDS = None


class Server(ThreadingHTTPServer):
    # ThreadingHTTPServer sets SO_REUSEADDR, which on Windows lets a
    # second instance bind the same port and serve a boardless page
    # beside the real one. Turning it off makes the second copy refuse
    # to start, which is what we want.
    allow_reuse_address = False
    daemon_threads = True


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass                      # keep the console clean

    def _send(self, code, body, ctype):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urlparse(self.path)

        if url.path in ("/", "/index.html"):
            try:
                with open(PAGE, encoding="utf-8") as fh:
                    return self._send(200, fh.read(), "text/html; charset=utf-8")
            except FileNotFoundError:
                return self._send(500, "dashboard.html is missing", "text/plain")

        if url.path == "/state":
            return self._send(200, json.dumps(STATE.snapshot()),
                              "application/json")

        if url.path == "/deny":
            q = parse_qs(url.query)
            try:
                mask = int(q.get("mask", ["0"])[0])
            except ValueError:
                return self._send(400, '{"error":"bad mask"}', "application/json")
            mask &= 0x1F
            if BOARDS:
                BOARDS.send(f"DENY {mask}")
            with STATE.lock:
                STATE.apply_mask(mask)
                STATE.event("info", f"operator set deny mask 0x{mask:02X}")
            return self._send(200, json.dumps(dict(ok=True, mask=mask)),
                              "application/json")

        if url.path == "/mode":
            q = parse_qs(url.query)
            want = q.get("m", ["hop"])[0].lower()
            fixed = want == "fixed"
            if BOARDS:
                BOARDS.send("MODE FIXED" if fixed else "MODE HOP")
            with STATE.lock:
                STATE.pinned = fixed
                STATE.mode = "fixed (pinned)" if fixed else "adaptive"
                # In fixed mode nothing is sensed, so a leftover SKIPPED
                # badge would never clear on its own.
                STATE.clear_blacklists()
            return self._send(200, json.dumps(dict(ok=True, fixed=fixed)),
                              "application/json")

        if url.path == "/reset":
            with STATE.lock:
                STATE.reset()
            return self._send(200, '{"ok":true}', "application/json")

        return self._send(404, "not found", "text/plain")


def main():
    global BOARDS
    ap = argparse.ArgumentParser()
    ap.add_argument("--tx", default="COM3")
    ap.add_argument("--rx", default="COM14")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--ports", action="store_true",
                    help="list the serial ports on this machine and exit")
    args = ap.parse_args()

    if args.ports:
        from serial.tools import list_ports
        found = list(list_ports.comports())
        if not found:
            print("\n  no serial ports found - are the boards plugged in?\n")
        else:
            print("\n  serial ports:")
            for p in found:
                busy = ""
                try:
                    serial.Serial(p.device).close()
                except Exception:
                    busy = "   [IN USE]"
                print(f"    {p.device:<8} {p.description}{busy}")
            print()
        return

    print("\nopening boards:")
    BOARDS = Boards(args.tx, args.rx)

    # Running a second copy was the single worst failure here: Python's
    # HTTP server sets SO_REUSEADDR, so on Windows two instances can both
    # bind 8080 while only the first holds the serial ports - the browser
    # then talks to the one with no boards and shows a dead link.
    if BOARDS.failed:
        print("\n  CANNOT START - serial port(s) unavailable:")
        for name, port, exc in BOARDS.failed:
            print(f"    {name}  {port}  ->  {exc}")
        print("\n  Usually one of:")
        print("    - another dashboard.py is already running")
        print("    - the Arduino IDE serial monitor is open")
        print("    - the board is unplugged, or on a different COM port")
        print("\n  Check with:  python analysis/dashboard.py --ports\n")
        sys.exit(1)

    BOARDS.start()

    try:
        srv = Server(("127.0.0.1", args.port), Handler)
    except OSError as exc:
        sys.exit(f"\n  port {args.port} is already in use ({exc}).\n"
                 f"  another dashboard is probably running.\n")
    print(f"\n  dashboard -> http://localhost:{args.port}\n")
    print("  Ctrl+C to stop\n")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
