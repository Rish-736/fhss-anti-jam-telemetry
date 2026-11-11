"""Reference list for the paper.

Every literature entry was resolved against the CrossRef REST API (see
refs/crossref_lookup.py, refs/round2.py and refs/recent.py). Primary
sources (datasheets, patents, the gazette notification) are cited from
the documents themselves. Nothing here is written from memory: where a
lookup did not return a convincing match, the reference was dropped
rather than guessed at.

Entries carry a stable ``key``. The body text cites them as ``[@key]``
and build_paper.py resolves those to numbers at build time, so the
ordering below can change without touching a single citation.

Ordering, as requested by the faculty guide:
  1. the base paper this work departs from, first;
  2. then the literature, newest first;
  3. then primary sources (datasheets, patents, regulation), newest
     first, so that the literature at the top reads as current.
"""

BASE_KEY = "atheeq24"

# ---------------------------------------------------------------------
# kind: "lit" = peer-reviewed literature, "primary" = datasheet, patent
# or statutory instrument.
# ---------------------------------------------------------------------
ENTRIES = [
    dict(key="atheeq24", year=2024, kind="lit", text=
         "C. Atheeq, Z. Gulzar, M. S. Al Reshan, H. Alshahrani, "
         "A. Sulaiman, and A. Shaikh, “Securing UAV networks: A "
         "lightweight chaotic-frequency hopping approach to counter "
         "jamming attacks,” *IEEE Access*, vol. 12, "
         "pp. 38685–38699, 2024, doi: 10.1109/ACCESS.2024.3375343."),

    # ---------------- 2026 ----------------
    dict(key="he26", year=2026, kind="lit", text=
         "Z. He, S. Feng, C. Qu, B. Tang, C. Pei, and L. Bai, "
         "“Sliding window sub-channel detection based on adaptive "
         "threshold for high-speed frequency hopping signals,” *IEEE "
         "Access*, vol. 14, pp. 44562–44574, 2026, doi: "
         "10.1109/ACCESS.2026.3674783."),

    dict(key="chang26", year=2026, kind="lit", text=
         "Y.-B. Chang, F.-Y. Li, and M.-J. Tsai, “Time-efficient "
         "channel hopping sequence with maximum rendezvous diversity in "
         "cognitive radio networks,” *IEEE Trans. Commun.*, vol. 74, "
         "no. 1, pp. 291–306, Jan. 2026, doi: "
         "10.1109/TCOMM.2025.3624171."),

    dict(key="jo26", year=2026, kind="lit", text=
         "E. Jo and H. Baek, “Channel restoration scheme to improve "
         "performance of adaptive-fast frequency hopping remapping,” "
         "*J. Korean Inst. Commun. Inf. Sci.*, vol. 51, no. 1, "
         "pp. 232–240, Jan. 2026, doi: 10.7840/kics.2026.51.1.232."),

    dict(key="oh26", year=2026, kind="lit", text=
         "C. Oh and S. Kang, “LSTM-based early jamming threat "
         "detection scheme for drone ad-hoc networks,” *Appl. Sci.*, "
         "vol. 16, no. 6, p. 3046, 2026, doi: 10.3390/app16063046."),

    # ---------------- 2025 ----------------
    dict(key="cheng25", year=2025, kind="lit", text=
         "S. Cheng, X. Ling, and L. Zhu, “Deep reinforcement "
         "learning-based anti-jamming approach for fast frequency "
         "hopping systems,” *IEEE Open J. Commun. Soc.*, vol. 6, "
         "pp. 961–971, 2025, doi: 10.1109/OJCOMS.2025.3529982."),

    dict(key="songl25", year=2025, kind="lit", text=
         "L. Song, D. Guo, T. Hu, and J. Yang, “Deep reinforcement "
         "learning-based anti-jamming rate adaptation and frequency "
         "selection algorithm,” *IEEE Trans. Consum. Electron.*, "
         "vol. 71, pp. 11782–11790, 2025, doi: "
         "10.1109/TCE.2025.3627267."),

    dict(key="xie25", year=2025, kind="lit", text=
         "W. Xie, H. Yang, and Z. Xiong, “Resource allocation for "
         "UAV-assisted anti-jamming semantic D2D networks: A graph "
         "reinforcement learning approach,” *Comput. Netw.*, "
         "vol. 269, p. 111463, 2025, doi: 10.1016/j.comnet.2025.111463."),

    dict(key="ayegun25", year=2025, kind="lit", text=
         "O. M. Ayegun, K. F. Akingbade, J. J. Popoola, and B. C. "
         "Ubochi, “Leveraging on artificial intelligence for "
         "universal jamming attack detection in unmanned aerial "
         "vehicles,” *Comput. Electr. Eng.*, vol. 127, p. 110602, "
         "2025, doi: 10.1016/j.compeleceng.2025.110602."),

    dict(key="cibecchini25", year=2025, kind="lit", text=
         "S. Cibecchini, F. Chiti, and L. Pierucci, “A lightweight "
         "AI-based approach for drone jamming detection,” *Future "
         "Internet*, vol. 17, no. 1, p. 14, 2025, doi: "
         "10.3390/fi17010014."),

    dict(key="vasfi25", year=2025, kind="lit", text=
         "M. Asadi Vasfi and B. Shahgholi Ghahfarokhi, "
         "“Channel-hopping sequence generation for blind rendezvous "
         "in cognitive radio-enabled Internet of Things,” *Comput. "
         "Commun.*, vol. 243, p. 108318, 2025, doi: "
         "10.1016/j.comcom.2025.108318."),

    dict(key="lora25", year=2025, kind="lit", text=
         "G. Hochet Derevianckine, A. Guitton, O. Iova, B. Ning, and "
         "F. Valois, “Hate or love in the 2.4 GHz ISM band: The "
         "story of LoRa and IEEE 802.11g,” *ACM Trans. Internet "
         "Things*, vol. 7, pp. 1–30, 2025, doi: 10.1145/3743688."),

    dict(key="wang25", year=2025, kind="lit", text=
         "S. Wang, D. Liu, L. Yin, X. Wang, Z. Ke, and Z. Du, "
         "“Dual-mode anti-jamming strategy for UAV "
         "communications,” in *Proc. 8th Int. Conf. Electron. "
         "Technol. (ICET)*, Wuhan, China, 2025, pp. 131–136, doi: "
         "10.1109/ICET64964.2025.11102942."),

    # ---------------- 2023 and earlier ----------------
    dict(key="jiao23", year=2023, kind="lit", text=
         "J. Jiao, C. Liu, J. He, and M. Peng, “Deep reinforcement "
         "learning assisted trajectory design for UAV communication "
         "systems against malicious jamming,” in *Proc. IEEE 23rd "
         "Int. Conf. Commun. Technol. (ICCT)*, Wuxi, China, 2023, "
         "pp. 979–984, doi: 10.1109/ICCT59356.2023.10419848."),

    dict(key="pirayesh22", year=2022, kind="lit", text=
         "H. Pirayesh and H. Zeng, “Jamming attacks and anti-jamming "
         "strategies in wireless networks: A comprehensive survey,” "
         "*IEEE Commun. Surveys Tuts.*, vol. 24, no. 2, "
         "pp. 767–809, 2nd Quart. 2022, doi: "
         "10.1109/COMST.2022.3159185."),

    dict(key="cena22", year=2022, kind="lit", text=
         "G. Cena, S. Scanzio, and A. Valenzano, “Ultra-low power "
         "wireless sensor networks based on time slotted channel hopping "
         "with probabilistic blacklisting,” *Electronics*, vol. 11, "
         "no. 3, p. 304, Jan. 2022, doi: 10.3390/electronics11030304."),

    dict(key="koubaa19", year=2019, kind="lit", text=
         "A. Koubaa, A. Allouch, M. Alajlan, Y. Javed, A. Belghith, and "
         "M. Khalgui, “Micro air vehicle link (MAVlink) in a "
         "nutshell: A survey,” *IEEE Access*, vol. 7, "
         "pp. 87658–87680, 2019, doi: 10.1109/ACCESS.2019.2924410."),

    dict(key="allouch19", year=2019, kind="lit", text=
         "A. Allouch, O. Cheikhrouhou, A. Koubaa, M. Khalgui, and "
         "T. Abbes, “MAVSec: Securing the MAVLink protocol for "
         "Ardupilot/PX4 unmanned aerial systems,” in *Proc. 15th "
         "Int. Wireless Commun. Mobile Comput. Conf. (IWCMC)*, Tangier, "
         "Morocco, 2019, pp. 621–628, doi: "
         "10.1109/IWCMC.2019.8766667."),

    dict(key="kotsiou19", year=2019, kind="lit", text=
         "V. Kotsiou, G. Z. Papadopoulos, D. Zorbas, P. Chatzimisios, "
         "and F. Théoleyre, “Blacklisting-based channel hopping "
         "approaches in low-power and lossy networks,” *IEEE Commun. "
         "Mag.*, vol. 57, no. 2, pp. 48–53, Feb. 2019, doi: "
         "10.1109/MCOM.2018.1800362."),

    dict(key="tan19", year=2019, kind="lit", text=
         "X. J. Tan and Y. Yuan, “Efficient channel hopping for "
         "blind rendezvous in multi-radio cognitive radio networks,” "
         "in *Proc. IEEE Global Commun. Conf. (GLOBECOM)*, Waikoloa, HI, "
         "USA, 2019, pp. 1–6, doi: "
         "10.1109/GLOBECOM38437.2019.9014326."),

    dict(key="liu18", year=2018, kind="lit", text=
         "X. Liu, Y. Xu, L. Jia, Q. Wu, and A. Anpalagan, "
         "“Anti-jamming communications using spectrum waterfall: A "
         "deep reinforcement learning approach,” *IEEE Commun. "
         "Lett.*, vol. 22, no. 5, pp. 998–1001, May 2018, doi: "
         "10.1109/LCOMM.2018.2815018."),

    dict(key="elsts17", year=2017, kind="lit", text=
         "A. Elsts, X. Fafoutis, R. Piechocki, and I. Craddock, "
         "“Adaptive channel selection in IEEE 802.15.4 TSCH "
         "networks,” in *Proc. Global Internet Things Summit "
         "(GIoTS)*, Geneva, Switzerland, 2017, pp. 1–6, doi: "
         "10.1109/GIOTS.2017.8016246."),

    dict(key="lv17", year=2017, kind="lit", text=
         "S. Lv, L. Xiao, Q. Hu, X. Wang, C. Hu, and L. Sun, "
         "“Anti-jamming power control game in unmanned aerial "
         "vehicle networks,” in *Proc. IEEE Global Commun. Conf. "
         "(GLOBECOM)*, Singapore, 2017, pp. 1–6, doi: "
         "10.1109/GLOCOM.2017.8253988."),

    dict(key="jaitly17", year=2017, kind="lit", text=
         "S. Jaitly, H. Malhotra, and B. Bhushan, “Security "
         "vulnerabilities and countermeasures against jamming attacks in "
         "wireless sensor networks: A survey,” in *Proc. Int. Conf. "
         "Comput., Commun. Electron. (Comptelix)*, Jaipur, India, 2017, "
         "pp. 559–564, doi: 10.1109/COMPTELIX.2017.8004033."),

    dict(key="petnga16", year=2016, kind="lit", text=
         "L. Petnga and H. Xu, “Security of unmanned aerial "
         "vehicles: Dynamic state estimation under cyber-physical "
         "attacks,” in *Proc. Int. Conf. Unmanned Aircraft Syst. "
         "(ICUAS)*, Arlington, VA, USA, 2016, pp. 811–819, doi: "
         "10.1109/ICUAS.2016.7502663."),

    dict(key="song16", year=2016, kind="lit", text=
         "Y. Song, K. W. Sung, and Y. Han, “Coexistence of Wi-Fi and "
         "cellular with listen-before-talk in unlicensed spectrum,” "
         "*IEEE Commun. Lett.*, vol. 20, no. 1, pp. 161–164, "
         "Jan. 2016, doi: 10.1109/LCOMM.2015.2504509."),

    dict(key="palattella15", year=2015, kind="lit", text=
         "M. R. Palattella and L. A. Grieco, *Using IEEE 802.15.4e "
         "Time-Slotted Channel Hopping (TSCH) in the Internet of Things "
         "(IoT): Problem Statement*, RFC 7554, May 2015, doi: "
         "10.17487/RFC7554."),

    dict(key="lin11", year=2011, kind="lit", text=
         "Z. Lin, H. Liu, X. Chu, and Y.-W. Leung, “Jump-stay based "
         "channel-hopping algorithm with guaranteed rendezvous for "
         "cognitive radio networks,” in *Proc. IEEE INFOCOM*, "
         "Shanghai, China, 2011, pp. 2444–2452, doi: "
         "10.1109/INFCOM.2011.5935066."),

    dict(key="yucek09", year=2009, kind="lit", text=
         "T. Yucek and H. Arslan, “A survey of spectrum sensing "
         "algorithms for cognitive radio applications,” *IEEE "
         "Commun. Surveys Tuts.*, vol. 11, no. 1, pp. 116–130, "
         "1st Quart. 2009, doi: 10.1109/SURV.2009.090109."),

    dict(key="moon06", year=2006, kind="lit", text=
         "S. Moon, “An adaptive frequency hopping method in the "
         "Bluetooth baseband,” in *Proc. 1st Int. Symp. Wireless "
         "Pervasive Comput. (ISWPC)*, Phuket, Thailand, 2006, "
         "pp. 1–4, doi: 10.1109/ISWPC.2006.1613638."),

    dict(key="xu05", year=2005, kind="lit", text=
         "W. Xu, W. Trappe, Y. Zhang, and T. Wood, “The feasibility "
         "of launching and detecting jamming attacks in wireless "
         "networks,” in *Proc. 6th ACM Int. Symp. Mobile Ad Hoc "
         "Netw. Comput. (MobiHoc)*, Urbana-Champaign, IL, USA, 2005, "
         "pp. 46–57, doi: 10.1145/1062689.1062697."),

    dict(key="sikora05", year=2005, kind="lit", text=
         "A. Sikora and V. F. Groza, “Coexistence of IEEE 802.15.4 "
         "with other systems in the 2.4 GHz-ISM-band,” in *Proc. "
         "IEEE Instrum. Meas. Technol. Conf. (IMTC)*, Ottawa, ON, "
         "Canada, 2005, vol. 3, pp. 1786–1791, doi: "
         "10.1109/IMTC.2005.1604479."),

    dict(key="kim01", year=2001, kind="lit", text=
         "Y. Kim, B. Zhen, and K. Jang, “The hybrid of "
         "listen-before-talk and adaptive frequency hopping for "
         "coexistence of Bluetooth and IEEE 802.11 WLAN,” in "
         "*Wireless LANs and Home Networks*. Singapore: World "
         "Scientific, 2001, pp. 263–272, doi: "
         "10.1142/9789812799562_0024."),

    dict(key="lo91", year=1991, kind="lit", text=
         "C. M. Lo, E. Masry, and L. B. Milstein, “Performance "
         "analysis of fast frequency-hopped DBPSK spread spectrum "
         "communications in partial-band noise jamming,” in *Proc. "
         "IEEE Mil. Commun. Conf. (MILCOM)*, McLean, VA, USA, 1991, "
         "pp. 576–580, doi: 10.1109/MILCOM.1991.258321."),

    dict(key="pickholtz82", year=1982, kind="lit", text=
         "R. L. Pickholtz, D. L. Schilling, and L. B. Milstein, "
         "“Theory of spread-spectrum communications — A "
         "tutorial,” *IEEE Trans. Commun.*, vol. 30, no. 5, "
         "pp. 855–884, May 1982, doi: 10.1109/TCOM.1982.1095533."),

    # ---------------- primary sources ----------------
    dict(key="esp32", year=2026, kind="primary", text=
         "*ESP32 Series Datasheet*, version 5.3, Espressif Systems, "
         "Shanghai, China. Accessed: Oct. 15, 2026. [Online]. "
         "Available: "
         "https://documentation.espressif.com/esp32_datasheet_en.pdf"),

    dict(key="gsr22", year=2022, kind="primary", text=
         "*Use of Low Power Radio Frequency Devices in the Frequency "
         "Band 433.05 to 434.79 MHz (Exemption from Licence) Rules, "
         "2022*, G.S.R. 347(E), Ministry of Communications, Government "
         "of India, Gazette of India, May 9, 2022."),

    dict(key="cc1101", year=2013, kind="primary", text=
         "*CC1101 Low-Power Sub-1 GHz RF Transceiver*, Texas "
         "Instruments, Dallas, TX, USA, Datasheet SWRS061I, Nov. 2013."),

    dict(key="voglewede12", year=2012, kind="primary", text=
         "P. E. Voglewede, E. M. Leiby III, M. W. Chamberlain, P. Lang, "
         "F. C. Kellerman, and D. E. Stephens, “Signal jamming "
         "avoidance method for a frequency hopping communication "
         "system,” U.S. Patent 8 165 242 B2, Apr. 24, 2012."),

    dict(key="marcoccia01", year=2001, kind="primary", text=
         "R. R. Marcoccia and G. R. Sosnowski, “Method and "
         "transceiver using an improved protocol for a frequency hop "
         "communication system,” U.S. Patent 6 169 761 B1, "
         "Jan. 2, 2001."),
]


def ordered():
    """Base paper first, then literature newest first, then primary
    sources newest first. Ties break on the entry's own key so the
    order is deterministic across builds."""
    base = [e for e in ENTRIES if e["key"] == BASE_KEY]
    assert len(base) == 1, "exactly one base paper expected"
    rest = [e for e in ENTRIES if e["key"] != BASE_KEY]
    lit = sorted((e for e in rest if e["kind"] == "lit"),
                 key=lambda e: (-e["year"], e["key"]))
    pri = sorted((e for e in rest if e["kind"] == "primary"),
                 key=lambda e: (-e["year"], e["key"]))
    return base + lit + pri


ORDERED = ordered()
REFS = [e["text"] for e in ORDERED]
NUM = {e["key"]: i for i, e in enumerate(ORDERED, 1)}
