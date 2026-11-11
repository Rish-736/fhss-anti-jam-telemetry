/*
 * RUN 7-9 TRANSMITTER - adaptive FHSS with sense-before-hop avoidance.
 *
 * Before moving to the next channel it tunes there briefly, reads the
 * energy level, and refuses to use the channel if it looks occupied. A
 * refused channel is blacklisted for a few cycles so the link does not
 * keep walking back into it.
 *
 * Whatever it picks still goes out in the packet's NEXT field, exactly
 * as the basic transmitter does - so the receiver needs no changes at
 * all to work with this sketch.
 *
 * ---------------------------------------------------------------------
 * EMULATED CHANNEL DENIAL
 * ---------------------------------------------------------------------
 * Nothing in this project transmits interference. Channels set in
 * DENY_MASK report a synthetic high RSSI from senseChannelRSSI(), so the
 * avoidance logic reacts as it would to a genuinely occupied channel.
 *
 * This exercises the DECISION LOGIC. The RF sensing path itself is only
 * exercised in the runs with DENY_MASK = 0, where every reading comes
 * from the radio.
 */

#include <ELECHOUSE_CC1101_SRC_DRV.h>
#include "rf_config.h"

int blacklistCooldown[NUM_HOPS];

unsigned long sequenceNumber = 0;
int currentHop = 0;

// Tune to a candidate channel and read how busy it looks.
int senseChannelRSSI(int hopIndex) {
  ELECHOUSE_cc1101.setMHZ(hopFrequencies[hopIndex]);
  ELECHOUSE_cc1101.SetRx();
  delay(5);                                 // let the RSSI register settle

  int rssi = ELECHOUSE_cc1101.getRssi();

  if (CHANNEL_DENIED(hopIndex)) {
    rssi = EMULATED_DENIED_RSSI;            // emulation, not a real reading
  }
  return rssi;
}

void tickCooldowns() {
  for (int i = 0; i < NUM_HOPS; i++) {
    if (blacklistCooldown[i] > 0) blacklistCooldown[i]--;
  }
}

// Pick the next hop, skipping anything occupied or still cooling down.
int selectNextHop(int current) {
  for (int offset = 1; offset <= NUM_HOPS; offset++) {
    int candidate = (current + offset) % NUM_HOPS;

    if (blacklistCooldown[candidate] > 0) continue;

    int rssi = senseChannelRSSI(candidate);

    Serial.print("   sensed ");
    Serial.print(hopFrequencies[candidate], 2);
    Serial.print(" MHz -> RSSI ");
    Serial.println(rssi);

    if (rssi < JAM_RSSI_THRESHOLD) {
      return candidate;
    }

    Serial.print(">> ");
    Serial.print(hopFrequencies[candidate], 2);
    Serial.print(" MHz OCCUPIED (RSSI ");
    Serial.print(rssi);
    Serial.println(" dBm) - blacklisting");
    blacklistCooldown[candidate] = COOLDOWN_CYCLES;
  }

  // Everything looked occupied. Keep the link moving rather than stall.
  Serial.println(">> all channels occupied - sequential fallback");
  return (current + 1) % NUM_HOPS;
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println();
  Serial.println("================================");
  Serial.println("        ADAPTIVE FHSS TX");
  Serial.println("================================");

  for (int i = 0; i < NUM_HOPS; i++) blacklistCooldown[i] = 0;

  ELECHOUSE_cc1101.setSpiPin(SCK_PIN, MISO_PIN, MOSI_PIN, CSN_PIN);
  ELECHOUSE_cc1101.Init();

  if (!ELECHOUSE_cc1101.getCC1101()) {
    Serial.println("CC1101 ERROR!");
    while (1);
  }

  applyRadioConfig();
  ELECHOUSE_cc1101.setPA(RF_PA);

  currentHop = 0;
  ELECHOUSE_cc1101.setMHZ(hopFrequencies[currentHop]);

  Serial.println("CC1101 OK");
  printRunConfig("adaptive FHSS TX");
  Serial.print("Jam threshold    : ");
  Serial.print(JAM_RSSI_THRESHOLD);
  Serial.println(" dBm");
  Serial.println("Starting 100 packet ADAPTIVE test...");
  Serial.println();
}

void loop() {
  pollSerialCommands();

  if (DEMO_MODE || sequenceNumber < TOTAL_PACKETS) {

    int nextHop;

    if (fixedModeActive) {
      // Conventional radio behaviour: one channel, no sensing, no
      // hopping. Announcing NEXT:0 every time keeps the receiver on
      // channel 0 with no receiver-side changes.
      currentHop = 0;
      nextHop = 0;
    } else {
      tickCooldowns();
      nextHop = selectNextHop(currentHop);
    }

    // Sensing may have left the radio on a candidate channel. Return to
    // the channel this packet is actually going out on.
    ELECHOUSE_cc1101.setMHZ(hopFrequencies[currentHop]);
    delay(2);

    char message[32];
    sprintf(message, "SEQ:%lu,NEXT:%d",
            sequenceNumber % TOTAL_PACKETS, nextHop);

    ELECHOUSE_cc1101.SendData(message);

    Serial.print(fixedModeActive ? "TX[FIXED]: " : "TX: ");
    Serial.print(message);
    Serial.print(" | CURRENT: ");
    Serial.print(hopFrequencies[currentHop], 2);
    Serial.print(" MHz | NEXT: ");
    Serial.print(hopFrequencies[nextHop], 2);
    Serial.println(" MHz");

    sequenceNumber++;
    delay(PACKET_INTERVAL);

    currentHop = nextHop;

  } else {
    Serial.println();
    Serial.println("       TX TEST COMPLETE");
    while (1);
  }
}
