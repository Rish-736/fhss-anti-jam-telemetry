/*
 * RUN 1-2 TRANSMITTER - fixed frequency baseline.
 *
 * Sends 100 numbered packets on one channel and stops. No hopping, no
 * sensing. This is the control: the simplest possible link, and the one
 * a conventional drone telemetry radio behaves like.
 *
 * Packet format:  "SEQ:<n>"
 */

#include <ELECHOUSE_CC1101_SRC_DRV.h>
#include "rf_config.h"

unsigned long sequenceNumber = 0;

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println();
  Serial.println("================================");
  Serial.println("      FIXED FREQUENCY TX");
  Serial.println("================================");

  ELECHOUSE_cc1101.setSpiPin(SCK_PIN, MISO_PIN, MOSI_PIN, CSN_PIN);
  ELECHOUSE_cc1101.Init();

  if (!ELECHOUSE_cc1101.getCC1101()) {
    Serial.println("CC1101 ERROR!");
    while (1);
  }

  applyRadioConfig();
  ELECHOUSE_cc1101.setPA(RF_PA);
  ELECHOUSE_cc1101.setMHZ(FIXED_FREQUENCY);

  Serial.println("CC1101 OK");
  printRunConfig("fixed TX");
  Serial.print("Frequency        : ");
  Serial.print(FIXED_FREQUENCY, 2);
  Serial.println(" MHz");
  Serial.println("Starting 100 packet test...");
  Serial.println();
}

void loop() {
  pollSerialCommands();

  if (DEMO_MODE || sequenceNumber < TOTAL_PACKETS) {
    char message[32];
    sprintf(message, "SEQ:%lu", sequenceNumber % TOTAL_PACKETS);

    ELECHOUSE_cc1101.SendData(message);

    Serial.print("TX: ");
    Serial.println(message);

    sequenceNumber++;
    delay(PACKET_INTERVAL);

  } else {
    Serial.println();
    Serial.println("       TX TEST COMPLETE");
    while (1);
  }
}
