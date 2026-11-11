/*
 * RUN 1-2 RECEIVER - fixed frequency baseline.
 *
 * Sits on one channel and counts what arrives. Each sequence number is
 * recorded in an array, so loss is always measured against a clean
 * 100-packet denominator and a duplicate can never inflate the count.
 *
 * EMULATED DENIAL: with DENY_MASK set, the one operating channel is
 * treated as denied - every packet heard is discarded. Nothing is
 * transmitted to cause this; it reproduces what a fixed link experiences
 * when its only channel becomes unusable.
 */

#include <ELECHOUSE_CC1101_SRC_DRV.h>
#include "rf_config.h"

#define FIXED_DENIED CHANNEL_DENIED(0)

byte buffer[61];
bool received[TOTAL_PACKETS];

unsigned long receivedPackets = 0;
unsigned long deniedDrops = 0;

long rssiSum = 0;
unsigned long rssiSamples = 0;

// CC1101 correlation-error measure (register 0x33, low 7 bits).
// LOWER IS BETTER. It degrades under channel occupancy without the
// wanted signal weakening, which is what separates an occupied channel
// from simple distance.
long lqiSum = 0;
unsigned long lqiSamples = 0;

unsigned long lastActivity = 0;
bool testComplete = false;

// Demo mode only: the sequence number wraps, so the tally restarts with
// it to give rolling 100-packet statistics.
unsigned long lastSeqSeen = 0;
bool haveSeq = false;

void resetTally() {
  for (int i = 0; i < TOTAL_PACKETS; i++) received[i] = false;
  receivedPackets = 0;
  rssiSum = 0;
  rssiSamples = 0;
  lqiSum = 0;
  lqiSamples = 0;
}

void printResults() {
  unsigned long lost = TOTAL_PACKETS - receivedPackets;
  float lossPct = ((float)lost / (float)TOTAL_PACKETS) * 100.0;
  float avgRssi = rssiSamples ? ((float)rssiSum / (float)rssiSamples) : 0;
  float avgLqi = lqiSamples ? ((float)lqiSum / (float)lqiSamples) : 0;

  Serial.println();
  Serial.println("================================");
  Serial.println("      FIXED TEST COMPLETE");
  Serial.println("================================");
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
  Serial.println("================================");

  Serial.println();
  Serial.print("CSV,FIXED,0,");
  Serial.print(FIXED_DENIED ? 1 : 0);
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
  Serial.print(",0,");
  if (lqiSamples) Serial.println(avgLqi, 1);
  else Serial.println("NA");
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println();
  Serial.println("================================");
  Serial.println("    FIXED FREQUENCY RX TEST");
  Serial.println("================================");

  for (int i = 0; i < TOTAL_PACKETS; i++) received[i] = false;

  ELECHOUSE_cc1101.setSpiPin(SCK_PIN, MISO_PIN, MOSI_PIN, CSN_PIN);
  ELECHOUSE_cc1101.Init();

  if (!ELECHOUSE_cc1101.getCC1101()) {
    Serial.println("CC1101 ERROR!");
    while (1);
  }

  applyRadioConfig();
  ELECHOUSE_cc1101.setMHZ(FIXED_FREQUENCY);
  ELECHOUSE_cc1101.SetRx();

  Serial.println("CC1101 OK");
  printRunConfig("fixed RX");
  Serial.print("Frequency        : ");
  Serial.print(FIXED_FREQUENCY, 2);
  Serial.println(" MHz");
  Serial.println("Waiting for 100 packets...");
  Serial.println();

  lastActivity = millis();
}

void loop() {
  pollSerialCommands();

  if (testComplete) {
    printResults();
    while (1);
  }

  // A dead link still has to produce a result rather than hang.
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

      if (FIXED_DENIED) {
        deniedDrops++;
        Serial.print("   [denied] dropped a packet on ");
        Serial.print(FIXED_FREQUENCY, 2);
        Serial.print(" MHz  (drops: ");
        Serial.print(deniedDrops);
        Serial.println(")");
        return;
      }

      if (strncmp((char*)buffer, "SEQ:", 4) == 0) {
        unsigned long seq = strtoul((char*)buffer + 4, NULL, 10);

        // Bounds check: a corrupted payload that slips past CRC must not
        // be allowed to poison the statistics.
        if (seq >= TOTAL_PACKETS) return;

        if (DEMO_MODE && haveSeq && seq < lastSeqSeen) resetTally();
        lastSeqSeen = seq;
        haveSeq = true;

        if (!received[seq]) {
          received[seq] = true;
          receivedPackets++;

          int rssi = ELECHOUSE_cc1101.getRssi();
          rssiSum += rssi;
          rssiSamples++;

          int lqi = ELECHOUSE_cc1101.getLqi() & 0x7F;   // drop CRC_OK bit
          lqiSum += lqi;
          lqiSamples++;

          Serial.print("RX SEQ:");
          Serial.print(seq);
          Serial.print(" | RSSI:");
          Serial.print(rssi);
          Serial.print(" dBm | LQI:");
          Serial.print(lqi);
          Serial.print(" | Received:");
          Serial.print(receivedPackets);
          Serial.print("/");
          Serial.println(TOTAL_PACKETS);

          if (!DEMO_MODE && seq == TOTAL_PACKETS - 1) testComplete = true;
        }
      }
    }
  }
}
