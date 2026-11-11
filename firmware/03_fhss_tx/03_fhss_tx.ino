/*
 * RUN 3-6 TRANSMITTER - basic FHSS, fixed hop order, no sensing.
 *
 * Walks the channel list in order, one channel per packet, and tells the
 * receiver where it is going next inside the packet itself. It never
 * looks at the air before hopping, so a denied channel is something it
 * walks straight into.
 *
 * Packet format:  "SEQ:<n>,NEXT:<hop index>"
 */

#include <ELECHOUSE_CC1101_SRC_DRV.h>
#include "rf_config.h"

unsigned long sequenceNumber = 0;
int currentHop = 0;

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println();
  Serial.println("================================");
  Serial.println("         BASIC FHSS TX");
  Serial.println("================================");

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
  printRunConfig("basic FHSS TX");
  Serial.println("Hop table:");
  for (int i = 0; i < NUM_HOPS; i++) {
    Serial.print("  Hop ");
    Serial.print(i);
    Serial.print(": ");
    Serial.print(hopFrequencies[i], 2);
    Serial.println(" MHz");
  }
  Serial.println("Starting 100 packet FHSS test...");
  Serial.println();
}

void loop() {
  pollSerialCommands();

  if (DEMO_MODE || sequenceNumber < TOTAL_PACKETS) {

    int nextHop = (currentHop + 1) % NUM_HOPS;

    char message[32];
    sprintf(message, "SEQ:%lu,NEXT:%d",
            sequenceNumber % TOTAL_PACKETS, nextHop);

    ELECHOUSE_cc1101.SendData(message);

    Serial.print("TX: ");
    Serial.print(message);
    Serial.print(" | CURRENT: ");
    Serial.print(hopFrequencies[currentHop], 2);
    Serial.print(" MHz | NEXT: ");
    Serial.print(hopFrequencies[nextHop], 2);
    Serial.println(" MHz");

    sequenceNumber++;
    delay(PACKET_INTERVAL);

    currentHop = nextHop;
    ELECHOUSE_cc1101.setMHZ(hopFrequencies[currentHop]);

  } else {
    Serial.println();
    Serial.println("       TX TEST COMPLETE");
    while (1);
  }
}
