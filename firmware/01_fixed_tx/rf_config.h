/*
 * Shared radio configuration for every sketch in this project.
 *
 * The runner copies this file into each sketch folder before compiling,
 * so the transmitter and receiver can never end up with mismatched
 * channel plans or radio settings.
 *
 * ---------------------------------------------------------------------
 * CHANNEL PLAN - why 400 kHz spacing
 * ---------------------------------------------------------------------
 * At 99.97 kbps with 47.60 kHz deviation, Carson's rule puts one
 * transmission at roughly 2 x (47.6 + 50) = 195 kHz wide.
 *
 * The original plan used 200 kHz spacing with an 812.50 kHz receive
 * bandwidth. That meant each signal nearly filled the gap to its
 * neighbour, and the receive passband (+/-406 kHz) was wider than the
 * entire 800 kHz hop span - so a receiver parked on any one channel
 * still heard most of the others. Measured directly in run 4: a receiver
 * stranded on one channel picked up 50 of 100 transmissions.
 *
 * With 400 kHz spacing and a 270.83 kHz passband (+/-135 kHz), the
 * nearest energy from an adjacent channel sits about 302 kHz off centre,
 * well outside the filter. The channels are genuinely isolated, which is
 * what frequency hopping needs in order to mean anything.
 *
 * All five channels stay inside the 433.05 - 434.79 MHz ISM band.
 */

#ifndef RF_CONFIG_H
#define RF_CONFIG_H

// ---- SPI wiring (identical on both boards) ----
#define SCK_PIN   18
#define MISO_PIN  19
#define MOSI_PIN  23
#define CSN_PIN   5

// ---- Channel plan ----
#define NUM_HOPS 5
static const float hopFrequencies[NUM_HOPS] = {
  433.05,
  433.45,
  433.85,
  434.25,
  434.65
};
#define FIXED_FREQUENCY 433.05

// ---- Radio parameters ----
#define RF_DEVIATION 47.60
#define RF_RXBW      270.83
#define RF_DRATE     99.97
#define RF_PA        10

// ---- Experiment constants ----
#define TOTAL_PACKETS   100
#define PACKET_INTERVAL 700

/* ---------------------------------------------------------------------
 * Build-time run configuration
 * ---------------------------------------------------------------------
 * The runner passes these with -D so a run can be configured without
 * editing any source. Defaults below apply if a sketch is built by hand
 * in the Arduino IDE.
 *
 * DENY_MASK is a bitmask of emulated-denied channels: bit i denies
 * hopFrequencies[i]. 0x04 denies channel 2 only; 0x14 denies 2 and 4.
 */
#ifndef DENY_MASK
#define DENY_MASK 0
#endif

#ifndef RESYNC_ENABLED
#define RESYNC_ENABLED 0
#endif

#ifndef ADAPTIVE_RUN
#define ADAPTIVE_RUN 0
#endif

#ifndef JAM_RSSI_THRESHOLD
#define JAM_RSSI_THRESHOLD -75
#endif

#ifndef COOLDOWN_CYCLES
#define COOLDOWN_CYCLES 3
#endif

// Synthetic reading reported for a denied channel during sensing.
#ifndef EMULATED_DENIED_RSSI
#define EMULATED_DENIED_RSSI -35
#endif

/*
 * DEMO_MODE: keep transmitting indefinitely instead of stopping at
 * TOTAL_PACKETS. The sequence number wraps, and the receiver restarts
 * its tally each time it does, giving rolling 100-packet statistics.
 * Used for the live dashboard; the measured runs leave it off.
 */
#ifndef DEMO_MODE
#define DEMO_MODE 0
#endif

/*
 * Denial is held in a variable rather than baked in, so the dashboard
 * can deny and release channels while the link is running. It starts at
 * the compile-time DENY_MASK, so the automated matrix is unaffected.
 */
static int activeDenyMask = DENY_MASK;

static inline bool channelDenied(int i) {
  return ((activeDenyMask >> i) & 1) != 0;
}

#define CHANNEL_DENIED(i) channelDenied(i)

/*
 * Accepts "DENY <mask>" on the serial line and echoes the new value back
 * so the dashboard can confirm it landed. Call once per loop.
 */
static inline void pollSerialCommands() {
  static char cmd[24];
  static int len = 0;

  while (Serial.available()) {
    char c = (char)Serial.read();

    if (c == '\n' || c == '\r') {
      if (len > 0) {
        cmd[len] = '\0';
        if (strncmp(cmd, "DENY ", 5) == 0) {
          activeDenyMask = atoi(cmd + 5) & 0x1F;
          Serial.print("DENY MASK NOW ");
          Serial.println(activeDenyMask);
        }
        len = 0;
      }
    } else if (len < (int)sizeof(cmd) - 1) {
      cmd[len++] = c;
    }
  }
}

// Timing
#define RESYNC_AFTER_MS  2000UL
#define IDLE_TIMEOUT_MS  15000UL
#define RENDEZVOUS_HOP   0

// Applies every radio setting shared by both ends of the link.
static inline void applyRadioConfig() {
  ELECHOUSE_cc1101.setCCMode(1);
  ELECHOUSE_cc1101.setModulation(0);     // 2-FSK
  ELECHOUSE_cc1101.setDeviation(RF_DEVIATION);
  ELECHOUSE_cc1101.setRxBW(RF_RXBW);
  ELECHOUSE_cc1101.setDRate(RF_DRATE);
  ELECHOUSE_cc1101.setSyncMode(2);
  ELECHOUSE_cc1101.setSyncWord(211, 145);
  ELECHOUSE_cc1101.setCrc(1);
  ELECHOUSE_cc1101.setLengthConfig(1);
  ELECHOUSE_cc1101.setPacketLength(61);
}

// Prints the run configuration so every log is self-documenting.
static inline void printRunConfig(const char *role) {
  Serial.print("Role             : ");
  Serial.println(role);
  Serial.print("RxBW / spacing   : ");
  Serial.print(RF_RXBW, 2);
  Serial.println(" kHz / 400 kHz");
  Serial.print("Denied channels  : ");
  bool any = false;
  for (int i = 0; i < NUM_HOPS; i++) {
    if (CHANNEL_DENIED(i)) {
      Serial.print(hopFrequencies[i], 2);
      Serial.print(" ");
      any = true;
    }
  }
  if (!any) Serial.print("none");
  Serial.println();
}

#endif
