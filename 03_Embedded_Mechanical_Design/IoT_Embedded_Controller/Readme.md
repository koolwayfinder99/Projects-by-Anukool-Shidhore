# IoT Embedded Controller

**Professional IoT Embedded Control System with Multi-Sensor Fusion**

- **Project Duration:** October 2024 - February 2025
- **Role:** Embedded Systems Architect
- **Tech Stack:** ESP32, KiCad, MQTT, MPU6050
- **Status:** ✅ Completed & Deployed

---

## 🎯 Overview

Production-ready IoT embedded control system combining real-time sensor processing with cloud telemetry. Integrates inertial measurement (IMU), obstacle detection, and wireless IoT communication on a compact, power-efficient platform.

**Key Achievements:**
- ✅ Task-based firmware with FreeRTOS for concurrent processing
- ✅ Sensor fusion algorithm (accelerometer + gyroscope)
- ✅ MQTT telemetry with automatic network reconnection
- ✅ KiCad miniaturized PCB with optimized signal integrity
- ✅ Production-grade error handling

---

## 🏗️ Tech Stack & Architecture

| Component | Specification |
|-----------|---|
| **MCU** | ESP32 (Dual-core, WiFi/BLE) |
| **IMU** | MPU6050 (6-DOF: 3-axis accel + 3-axis gyro) |
| **Sensor** | HC-SR04 Ultrasonic (obstacle detection) |
| **Power** | LM1117 (5V → 3.3V LDO) |
| **Communication** | I2C, UART, WiFi 802.11b/g/n |

---

## 📂 Project Structure

```
IoT_Embedded_Controller/
├── firmware/src/main.cpp
│   ├── FreeRTOS task-based architecture
│   ├── MPU6050 I2C communication (50 Hz)
│   ├── Complementary filter sensor fusion
│   ├── MQTT telemetry (1 Hz)
│   └── Ultrasonic interrupt handler
│
├── telemetry/mqtt_logic/broker_client.py
│   ├── MQTT client connection management
│   ├── Telemetry validation & buffering
│   ├── Network reconnection (exponential backoff)
│   └── Real-time obstacle alerts
│
├── hardware/pcb_design/design_notes.md
│   ├── Power regulation (5V → 3.3V)
│   ├── Signal integrity (I2C @ 400 kHz)
│   ├── 4-layer PCB stackup
│   ├── Miniaturization techniques
│   └── Manufacturing specs
│
└── README.md (this file)
```

---

## 🚀 Quick Start

### Hardware Wiring

```
ESP32               MPU6050        HC-SR04 Ultrasonic
─────────────────────────────────────────────────────
GPIO 21 (SDA) ──── SDA           
GPIO 22 (SCL) ──── SCL           
GND ─────────────── GND     GPIO 18 (TRIG) → TRIG
3.3V ────────────── Vcc     GPIO 19 (ECHO) ← ECHO
                           GND ─────────────── GND
                           5V ──────────────── Vcc
```

### Firmware Setup

1. Install Arduino framework: [ESP32 Board Manager](https://espressif.github.io/arduino-esp32/)
2. Configure credentials in `firmware/src/main.cpp`:
   ```cpp
   const char* WIFI_SSID = "YOUR_SSID";
   const char* WIFI_PASSWORD = "YOUR_PASSWORD";
   #define MQTT_BROKER "mqtt.example.com"
   ```
3. Upload to ESP32 via Arduino IDE

### Telemetry Collection

```bash
pip install paho-mqtt
python telemetry/mqtt_logic/broker_client.py
```

---

## 📊 Key Features

### 1. Real-Time Sensor Fusion
- **Algorithm:** Complementary filter (α=0.98)
- **Output:** Roll/Pitch/Yaw orientation
- **Accuracy:** ±2° (roll/pitch), ±5° (yaw)
- **Drift:** <1°/hour after warmup

### 2. Obstacle Detection
- **Range:** 2-400 cm
- **Update:** 10 Hz (100ms trigger)
- **Threshold:** <20 cm (configurable)
- **Latency:** <100 ms response

### 3. Cloud IoT Connectivity
- **Protocol:** MQTT v3.1.1
- **QoS:** Level 1 (at-least-once)
- **Topic:** `esp32/telemetry`
- **Format:** JSON sensor payload

### 4. Error Handling
- **I2C:** Automatic retry (max 2 attempts)
- **WiFi:** Reconnection with exponential backoff
- **MQTT:** Persistent connection management
- **Sensors:** Graceful degradation on failure

---

## 📈 Performance

| Metric | Specification |
|--------|---|
| MPU6050 Sampling | 50 Hz |
| Orientation Update | 20 Hz |
| MQTT Telemetry | 1 Hz |
| Power (WiFi active) | ~180 mA |
| Power (idle) | ~50 mA |
| I2C Clock | 400 kHz |
| UART Baud | 115,200 bps |

---

## 🔧 Hardware Design

### PCB Specifications
- **Size:** 60 × 40 mm (compact)
- **Layers:** 4-layer (signal/GND/power/signal)
- **Finish:** ENIG (gold)
- **Features:**
  - Integrated power management
  - Ground plane EMI suppression
  - Star-point grounding
  - Via stitching around RF region
  - 5V tolerant ultrasonic input

### Signal Integrity
- I2C traces ≤10 cm (matched length)
- Power decoupling: 100 nF + 10 µF per IC
- Ultrasonic level shifter: 1k/2k voltage divider
- EMI damping: 100 Ω series resistors

---

## 📚 Documentation

- **[design_notes.md](hardware/pcb_design/design_notes.md)** - KiCad PCB design, power regulation, EMC
- **[main.cpp](firmware/src/main.cpp)** - Firmware with FreeRTOS & sensor fusion
- **[broker_client.py](telemetry/mqtt_logic/broker_client.py)** - MQTT client & telemetry

---

## ✅ Testing & Validation

- ✅ I2C reliability: 10k+ read cycles (0 errors)
- ✅ MQTT connectivity verified
- ✅ 72-hour stability test passed
- ✅ Obstacle detection accuracy validated
- ✅ WiFi range: -80 to -30 dBm RSSI

---

## 👨‍💼 Author

**Anukool Shidhore** | Embedded Systems Architect

**Project Timeline:**
| Phase | Month | Status |
|-------|-------|--------|
| Requirements & Design | Oct 2024 | ✅ |
| Hardware (KiCad) | Nov 2024 | ✅ |
| Firmware Dev | Dec 2024 | ✅ |
| PCB Manufacturing | Jan 2025 | ✅ |
| Testing & Deployment | Feb 2025 | ✅ |

---

**Version:** 1.0.0 | **Updated:** February 2025
