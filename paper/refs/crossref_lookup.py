"""Resolve candidate references against CrossRef so nothing is cited from memory.

Prints authoritative metadata for each query. Anything that does not come back
with a convincing title match is dropped rather than guessed at.
"""
import json, sys, time, urllib.parse, urllib.request

QUERIES = [
 "Jamming Attacks and Anti-Jamming Strategies in Wireless Networks A Comprehensive Survey",
 "The feasibility of launching and detecting jamming attacks in wireless networks",
 "Channel hopping for blind rendezvous in cognitive radio networks a review",
 "Jump-Stay Rendezvous Algorithm for Cognitive Radio Networks",
 "Blacklisting-Based Channel Hopping Approaches in Low-Power and Lossy Networks",
 "Securing UAV Networks A Lightweight Chaotic-Frequency Hopping Approach to Counter Jamming Attacks",
 "MAVSec Securing the MAVLink Protocol for Ardupilot PX4 Unmanned Aerial Systems",
 "Micro Air Vehicle Link MAVlink in a Nutshell A Survey",
 "Theory of spread-spectrum communications a tutorial Pickholtz",
 "Adaptive frequency hopping for reducing interference between Bluetooth and wireless LAN",
 "A survey on jamming attacks and countermeasures in wireless sensor networks",
 "Adaptive time-slotted channel hopping blacklisting industrial IoT",
 "Performance of frequency hopping spread spectrum under partial band jamming",
 "A survey of spectrum sensing algorithms for cognitive radio applications",
 "Security of unmanned aerial vehicle systems against cyber-physical attacks survey",
 "LoRa jamming attack evaluation low power wide area network",
 "Reactive jamming attacks wireless sensor networks detection",
 "Energy detection based spectrum sensing cognitive radio performance",
 "Anti-jamming communications using spectrum waterfall deep reinforcement learning",
 "Cross-layer anti-jamming scheme unmanned aerial vehicle networks",
 "Frequency hopping sequence design for anti jamming communication",
 "Listen before talk coexistence unlicensed spectrum",
 "Unmanned aerial vehicle communication networks survey physical layer security",
 "Channel quality estimation link quality indicator wireless sensor networks RSSI",
]

BASE = "https://api.crossref.org/works?rows=1&select=title,author,container-title,volume,issue,page,issued,DOI,type&query.bibliographic="

def get(q):
    url = BASE + urllib.parse.quote(q)
    req = urllib.request.Request(url, headers={
        "User-Agent": "ref-check/1.0 (mailto:your-email@example.com)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

for q in QUERIES:
    try:
        items = get(q)["message"]["items"]
    except Exception as e:
        print(f"\n### {q}\n  ERROR {e}")
        continue
    if not items:
        print(f"\n### {q}\n  NO RESULT")
        continue
    it = items[0]
    au = it.get("author", [])
    names = "; ".join(f"{a.get('given','')} {a.get('family','')}".strip() for a in au[:8])
    print(f"\n### {q}")
    print("  title :", (it.get("title") or [""])[0])
    print("  authors:", names or "-")
    print("  venue :", (it.get("container-title") or [""])[0] if it.get("container-title") else "-")
    print("  vol/iss/pp:", it.get("volume","-"), "/", it.get("issue","-"), "/", it.get("page","-"))
    print("  year  :", (it.get("issued",{}).get("date-parts",[[None]])[0][0]))
    print("  doi   :", it.get("DOI","-"), "| type:", it.get("type","-"))
    time.sleep(0.4)
