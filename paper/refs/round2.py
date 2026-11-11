import json, time, urllib.parse, urllib.request
QUERIES = [
 "Yucek Arslan survey of spectrum sensing algorithms for cognitive radio applications",
 "IEEE 802.15.4e time slotted channel hopping TSCH performance evaluation industrial",
 "Elsts adaptive channel selection blacklisting 6TiSCH internet of things",
 "Follower jamming frequency hopping spread spectrum partial band noise jamming performance analysis",
 "Bluetooth and WLAN coexistence adaptive frequency hopping measurement interference 2.4 GHz",
 "Counter unmanned aircraft systems detection mitigation survey drone",
 "LoRaWAN interference coexistence sub-GHz ISM band measurement",
 "Multi armed bandit channel selection anti jamming wireless",
 "Software defined radio testbed evaluation anti jamming frequency hopping experiment",
 "Packet delivery ratio model wireless link reliability analytical Markov",
 "Deep reinforcement learning UAV trajectory anti jamming communication",
 "Secure hopping sequence generation chaotic map wireless communication",
 "Clear channel assessment CCA energy detection threshold IEEE 802.15.4 performance",
 "Drone telemetry long range radio link 433 MHz 915 MHz performance measurement",
]
BASE=("https://api.crossref.org/works?rows=1&select=title,author,container-title,"
      "volume,issue,page,issued,DOI,type&query.bibliographic=")
for q in QUERIES:
    try:
        req=urllib.request.Request(BASE+urllib.parse.quote(q),
            headers={"User-Agent":"ref-check/1.0 (mailto:your-email@example.com)"})
        with urllib.request.urlopen(req,timeout=30) as r:
            items=json.load(r)["message"]["items"]
    except Exception as e:
        print(f"\n### {q}\n  ERROR {e}"); continue
    if not items: print(f"\n### {q}\n  NO RESULT"); continue
    it=items[0]; au=it.get("author",[])
    names="; ".join(f"{a.get('given','')} {a.get('family','')}".strip() for a in au[:8])
    print(f"\n### {q}")
    print("  title :",(it.get("title") or [""])[0])
    print("  authors:",names or "-")
    print("  venue :",(it.get("container-title") or ["-"])[0])
    print("  v/i/pp:",it.get("volume","-"),"/",it.get("issue","-"),"/",it.get("page","-"))
    print("  year  :",it.get("issued",{}).get("date-parts",[[None]])[0][0])
    print("  doi   :",it.get("DOI","-"),"| type:",it.get("type","-"))
    time.sleep(0.4)
