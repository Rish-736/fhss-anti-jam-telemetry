"""Find recent (2025+) papers on the paper's topics, with verified metadata.

Queries the CrossRef REST API with a publication-date filter so that only
genuinely recent work comes back. Nothing here is written from memory.
"""
import json
import time
import urllib.parse
import urllib.request

QUERIES = [
    "UAV unmanned aerial vehicle anti-jamming frequency hopping",
    "drone telemetry link jamming resilience experimental",
    "adaptive frequency hopping channel blacklisting interference avoidance",
    "frequency hopping spread spectrum anti jamming reinforcement learning UAV",
    "jamming detection mitigation unmanned aerial system spectrum",
    "LoRa sub-GHz ISM band interference jamming measurement",
    "channel hopping rendezvous synchronisation loss wireless link",
    "clear channel assessment spectrum sensing low power radio testbed",
    "UAV swarm communication security physical layer jamming",
    "COTS software defined radio experimental evaluation jamming resilience",
]

BASE = ("https://api.crossref.org/works?rows=4&sort=relevance"
        "&filter=from-pub-date:2025-01-01,type:journal-article"
        "&select=title,author,container-title,volume,issue,page,issued,DOI,type"
        "&query.bibliographic=")

seen = set()
for q in QUERIES:
    try:
        req = urllib.request.Request(
            BASE + urllib.parse.quote(q),
            headers={"User-Agent": "ref-check/1.0 (mailto:your-email@example.com)"})
        with urllib.request.urlopen(req, timeout=30) as r:
            items = json.load(r)["message"]["items"]
    except Exception as e:
        print("\n### %s\n  ERROR %s" % (q, e))
        continue
    print("\n### %s" % q)
    for it in items:
        doi = it.get("DOI", "")
        if doi in seen:
            continue
        seen.add(doi)
        au = it.get("author", [])
        names = "; ".join(
            ("%s %s" % (a.get("given", ""), a.get("family", ""))).strip()
            for a in au[:6])
        print("  -", (it.get("title") or [""])[0][:95])
        print("     au :", (names or "-")[:95])
        print("     in :", (it.get("container-title") or ["-"])[0][:70],
              "| v", it.get("volume", "-"), "| pp", it.get("page", "-"),
              "|", it.get("issued", {}).get("date-parts", [[None]])[0][0])
        print("     doi:", doi)
    time.sleep(0.4)
