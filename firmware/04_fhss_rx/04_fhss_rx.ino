/*
 * RUN 3-9 RECEIVER - shared by the basic and adaptive transmitters.
 *
 * Follows the hop schedule carried in each packet's NEXT field. It does
 * not need to know whether the transmitter is choosing channels blindly
 * or by sensing them - it just goes where it is told. That is why the
 * adaptive upgrade needed no receiver changes at all.
 *
 * ---------------------------------------------------------------------
 * RENDEZVOUS RECOVERY  (RESYNC_ENABLED)
 * ---------------------------------------------------------------------
 * The hop schedule travels inside the packets, so a packet lost on a
 * denied channel also costs the receiver its next-hop instruction: the
 * transmitter moves on, the receiver stays put, and the link is gone.
 * Run 4 measured exactly that - 1 packet out of 100.
 *
 * With recovery on, a receiver that has heard nothing valid for
 * RESYNC_AFTER_MS returns to the agreed rendezvous channel and waits.
 * The transmitter passes through it once per cycle, so the link comes
 * back within roughly NUM_HOPS packets.
 *
 * ---------------------------------------------------------------------
 * EMULATED CHANNEL DENIAL
 * ---------------------------------------------------------------------
 * No interference is transmitted anywhere in this project. Packets that
 * arrive while tuned to a channel set in DENY_MASK are discarded on
 * arrival, taking their NEXT instruction with them.
 */

#include <ELECHOUSE_CC1101_SRC_DRV.h>
#include "rf_config.h"

byte buffer[61];
bool received[TOTAL_PACKETS];

unsigned long receivedPackets = 0;
unsigned long deniedDrops = 0;
unsigned long resyncCount = 0;
unsigned long perChannelRx[NUM_HOPS];

long rssiSum = 0;
unsigned long rssiSamples = 0;

/*
 * LQI is the CC1101's correlation-error measure, read from register
 * 0x33. Bit 7 is the CRC_OK flag, so the metric is the low 7 bits, and
 * LOWER IS BETTER - it counts how badly the sync word correlated.
 *
 * It matters here because it moves independently of RSSI. Flying
 * further away lowers RSSI while LQI degrades gently; another
 * transmitter occupying the channel corrupts correlation (LQI climbs)
 * without the wanted signal getting any weaker. Two signals separate
 * those two causes where one signal cannot.
 */
long lqiSum = 0;
unsigned long lqiSamples = 0;

int currentHop = 0;
unsigned long lastGoodPacket = 0;
unsigned long lastActivity = 0;
bool testComplete = false;

// Demo mode only: the sequence number wraps, so the tally restarts with
// it to give rolling 100-packet statistics.
unsigned long lastSeqSeen = 0;
bool haveSeq = false;

void resetTally() {
  for (int i = 0; i < TOTAL_PACKETS; i++) received[i] = false;
  for (int i = 0; i < NUM_HOPS; i++) perChannelRx[i] = 0;
  receivedPackets = 0;
  rssiSum = 0;
  rssiSamples = 0;
  lqiSum = 0;
  lqiSamples = 0;
}

void tuneTo(int hop) {
  currentHop = hop;
  ELECHOUSE_cc1101.setMHZ(hopFrequencies[currentHop]);
  ELECHOUSE_cc1101.SetRx();
}

void printResults() {
  unsigned long lost = TOTAL_PACKETS - receivedPackets;
  float lossPct = ((float)lost / (float)TOTAL_PACKETS) * 100.0;
  float avgRssi = rssiSamples ? ((float)rssiSum / (float)rssiSamples) : 0;
  float avgLqi = lqiSamples ? ((float)lqiSum / (float)lqiSamples) : 0;

  int deniedCount = 0;
  for (int i = 0; i < NUM_HOPS; i++) if (CHANNEL_DENIED(i)) deniedCount++;

  Serial.println();
  Serial.println("================================");
  Serial.println("       FHSS TEST COMPLETE");
  Serial.println("================================");
  Serial.print("Mode             : ");
  Serial.print(ADAPTIVE_RUN ? "ADAPTIVE" : "BASIC");
  Serial.println(RESYNC_ENABLED ? " + resync" : " (no resync)");
  Serial.print("Denied channels  : ");
  Serial.println(deniedCount);
  Serial.print("Packets sent     : ");
  Serial.println(TOTAL_PACKETS);
  Serial.print("Packets received : ");
  Serial.println(receivedPackets);
  Serial.print("Packets lost     : ");
  Serial.println(lost);
  Serial.print("Packet loss      : ");
  Serial.print(lossPct, 2);
  Serial.println(" %");
  Serial.print("Denied drops     : ");
  Serial.println(deniedDrops);
  Serial.print("Resync events    : ");
  Serial.println(resyncCount);
  Serial.print("Average RSSI     : ");
  if (rssiSamples) {
    Serial.print(avgRssi, 1);
    Serial.println(" dBm");
  } else {
    Serial.println("n/a (no packets)");
  }
  Serial.print("Average LQI      : ");
  if (lqiSamples) {
    Serial.print(avgLqi, 1);
    Serial.println("  (lower is better)");
  } else {
    Serial.println("n/a (no packets)");
  }

  Serial.println("--------------------------------");
  Serial.println("Packets received per channel:");
  for (int i = 0; i < NUM_HOPS; i++) {
    Serial.print("  ");
    Serial.print(hopFrequencies[i], 2);
    Serial.print(" MHz : ");
    Serial.print(perChannelRx[i]);
    if (CHANNEL_DENIED(i)) Serial.print("   <- denied");
    Serial.println();
  }
  Serial.println("================================");

  Serial.println();
  Serial.print("CSV,");
  Serial.print(ADAPTIVE_RUN ? "ADAPTIVE" : "BASIC");
  Serial.print(",");
  Serial.print(RESYNC_ENABLED ? 1 : 0);
  Serial.print(",");
  Serial.print(deniedCount);
  Serial.print(",");
  Serial.print(TOTAL_PACKETS);
  Serial.print(",");
  Serial.print(receivedPackets);
  Serial.print(",");
  Serial.print(lost);
  Serial.print(",");
  Serial.print(lossPct, 2);
  Serial.print(",");
  if (rssiSamples) Serial.print(avgRssi, 1);
  else Serial.print("NA");
  Serial.print(",");
  Serial.print(resyncCount);
  Serial.print(",");
  if (lqiSamples) Serial.println(avgLqi, 1);
  else Serial.println("NA");
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println();
  Serial.println("================================");
  Serial.println("           FHSS RX");
  Serial.println("================================");

  for (int i = 0; i < TOTAL_PACKETS; i++) received[i] = false;
  for (int i = 0; i < NUM_HOPS; i++) perChannelRx[i] = 0;

  ELECHOUSE_cc1101.setSpiPin(SCK_PIN, MISO_PIN, MOSI_PIN, CSN_PIN);
  ELECHOUSE_cc1101.Init();

  if (!ELECHOUSE_cc1101.getCC1101()) {
    Serial.println("CC1101 ERROR!");
    while (1);
  }

  applyRadioConfig();
  tuneTo(0);

  Serial.println("CC1101 OK");
  printRunConfig(ADAPTIVE_RUN ? "FHSS RX (adaptive run)" : "FHSS RX (basic run)");
  Serial.print("Resync           : ");
  Serial.println(RESYNC_ENABLED ? "ON" : "OFF");
  Serial.println("Waiting for packets...");
  Serial.println();

  lastGoodPacket = millis();
  lastActivity = millis();
}

void loop() {
  pollSerialCommands();

  if (testComplete) {
    printResults();
    while (1);
  }

  if (!DEMO_MODE && millis() - lastActivity > IDLE_TIMEOUT_MS) {
    Serial.println();
    Serial.println("(idle timeout reached - ending run)");
    testComplete = true;
    return;
  }

  if (ELECHOUSE_cc1101.CheckRxFifo(100)) {
    if (ELECHOUSE_cc1101.CheckCRC()) {

      int len = ELECHOUSE_cc1101.ReceiveData(buffer);
      buffer[(len < (int)sizeof(buffer)) ? len : (int)sizeof(buffer) - 1] = '\0';

      lastActivity = millis();

      // Discard anything heard on a denied channel - including its NEXT
      // instruction. Losing the schedule is what makes in-band hop
      // announcement fragile, and that is the point of run 4.
      if (CHANNEL_DENIED(currentHop)) {
        deniedDrops++;
        Serial.print("   [denied] dropped a packet on ");
        Serial.print(hopFrequencies[currentHop], 2);
        Serial.print(" MHz  (drops: ");
        Serial.print(deniedDrops);
        Serial.println(")");
        return;
      }

      if (strncmp((char*)buffer, "SEQ:", 4) == 0) {
        char *comma = strchr((char*)buffer, ',');
        if (comma != NULL) {

          unsigned long seq = strtoul((char*)buffer + 4, NULL, 10);
          int nextHop = atoi(comma + 6);

          // Bounds check: a corrupted payload that slips past CRC must
          // not be allowed to poison the statistics.
          if (seq < TOTAL_PACKETS) {

            if (DEMO_MODE && haveSeq && seq < lastSeqSeen) resetTally();
            lastSeqSeen = seq;
            haveSeq = true;

            if (!received[seq]) {
              received[seq] = true;
              receivedPackets++;
              perChannelRx[currentHop]++;

              int rssi = ELECHOUSE_cc1101.getRssi();
              rssiSum += rssi;
              rssiSamples++;

              int lqi = ELECHOUSE_cc1101.getLqi() & 0x7F;   // drop CRC_OK bit
              lqiSum += lqi;
              lqiSamples++;

              Serial.print("RX: ");
              Serial.print((char*)buffer);
              Serial.print(" | FREQ: ");
              Serial.print(hopFrequencies[currentHop], 2);
              Serial.print(" MHz | RSSI: ");
              Serial.print(rssi);
              Serial.print(" dBm | LQI: ");
              Serial.print(lqi);
              Serial.print(" | Received: ");
              Serial.print(receivedPackets);
              Serial.print("/");
              Serial.println(TOTAL_PACKETS);
            }

            lastGoodPacket = millis();

            if (!DEMO_MODE && seq == TOTAL_PACKETS - 1) {
              testComplete = true;
              return;
            }

            if (nextHop >= 0 && nextHop < NUM_HOPS) {
              tuneTo(nextHop);
            }
          }
        }
      }
    }
  }

  // Nothing valid for a while means the hop schedule was lost. Go back
  // to the agreed channel and wait for the transmitter to come past.
  if (RESYNC_ENABLED && (millis() - lastGoodPacket > RESYNC_AFTER_MS)) {
    resyncCount++;
    Serial.print("!! lost sync - returning to rendezvous ");
    Serial.print(hopFrequencies[RENDEZVOUS_HOP], 2);
    Serial.println(" MHz");

    tuneTo(RENDEZVOUS_HOP);
    lastGoodPacket = millis();   // wait a full window before retrying
  }
}
