# KiCad PCB Design Documentation
## IoT Embedded Controller Hardware Design

**Project Period:** Oct 2024 - Feb 2025  
**Embedded Systems Architect:** Anukool Shidhore  
**Design Tool:** KiCad 8.0+  
**Target Platform:** ESP32 + MPU6050 + Ultrasonic Sensor

---

## Table of Contents

1. [Design Overview](#design-overview)
2. [Power Regulation](#power-regulation)
3. [Signal Integrity](#signal-integrity)
4. [Component Selection](#component-selection)
5. [PCB Layout Strategies](#pcb-layout-strategies)
6. [Miniaturization Techniques](#miniaturization-techniques)
7. [Testing & Verification](#testing--verification)

---

## Design Overview

### Objectives

- **Power Efficiency:** Minimize current draw for battery-powered IoT applications
- **Signal Integrity:** Maintain clean digital/analog signals for sensor accuracy
- **Compact Form Factor:** Achieve miniaturized design without compromising reliability
- **Robustness:** Handle real-world environmental conditions and electrical transients

### Architecture Blocks

```
┌─────────────────────────────────────────────────────────┐
│                  Embedded IoT Controller                │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  USB-C       5V Input      ┌──────────────────────┐    │
│  Connector   (Optional) ──▶│  Power Management    │    │
│              Battery ──────│  5V → 3.3V LDO       │    │
│                            └──────────────────────┘    │
│                                    │                   │
│                                3.3V Rail               │
│                    ┌───────────────┼───────────────┐   │
│                    │               │               │   │
│              ┌─────▼────┐    ┌──────▼────┐   ┌────▼──┐│
│              │   ESP32   │    │ MPU6050   │   │Sensors││
│              │  (Main    │    │  (IMU)    │   │       ││
│              │ Micro)    │◀──▶│  I2C      │   │       ││
│              │           │    │  0x68     │   │       ││
│              │ GPIO/PWM  │    └───────────┘   │       ││
│              │ UART/SPI  │                    │       ││
│              └───────────┘                    │       ││
│                    │                          │       ││
│                    │                   Ultrasonic     ││
│            ┌───────┼────────┐             (GPIO)     ││
│            │       │        │                        ││
│       Status LED   RST    Boot                └────────┘│
│            │       │        │                          │
│            └───────┴────────┴──────────────────────────┘
│                                                         │
│                  UART (USB Serial):                    │
│          Programming & Debug Interface                │
└─────────────────────────────────────────────────────────┘
```

---

## Power Regulation

### Power Supply Requirements

| Component | Voltage | Current | Notes |
|-----------|---------|---------|-------|
| ESP32 | 3.3V | 80-200 mA (peak) | Digital core, WiFi radio |
| MPU6050 | 3.3V | 3-5 mA | I2C interface |
| Ultrasonic | 5V | 15-30 mA (pulse) | Requires 5V supply |
| Status LED | 3.3V | 10-20 mA | With current-limiting resistor |

### LDO Selection: 5V → 3.3V

**Recommended:** TI LM1117-3.3 or similar

**Specifications:**
- Input: 5V ± 0.5V (USB or battery adapter)
- Output: 3.3V ± 3% (regulated)
- Max Current: 800 mA
- Quiescent Current: ~10 mA
- Temperature Coefficient: ±0.3%/°C

**Circuit Implementation:**

```
     ┌──── Vin (5V/USB) ────┐
     │                      │
    [C_in]                [R_ldo]
   (10µF)                 (10Ω)
     │                      │
     ├─────┬────────────────┤
     │     │                │
    GND   GND        ┌──────┴──────┐
                     │    1117     │
                    2│ Out  LDO    │1 (Vin)
                     │             │ 
                     │ Adj Vref    │3
                     └──────┬──────┘
                          │
                         [C_out]
                        (10µF Tant.)
                          │
                         GND

Output: 3.3V ±50mV (Steady State)
```

### Decoupling Strategy

**ESP32 Core:**
- 100 nF ceramic (X7R) at Vdd pin (close placement, <5mm)
- 10 µF electrolytic for bulk capacitance

**MPU6050:**
- 100 nF ceramic across Vdd-Gnd (close placement)
- 10 µF electrolytic for EMI rejection

**Recommendation:** Place bypass capacitors within 5-10 mm of IC power pins with short traces.

### Power Distribution

- **Input Rail (5V):** 12-mil minimum trace width
- **Output Rail (3.3V):** 10-mil trace width
- **Ground Plane:** Full layer (Layer 2) for low impedance returns
- **Thermal via:** 8x vias under LDO to dissipate ~100mW heat

---

## Signal Integrity

### I2C Bus (ESP32 ↔ MPU6050)

**Protocol:** I2C, 400 kHz (Standard Mode)

**Specifications:**
- **SDA (GPIO 21):** I2C Data Line
- **SCL (GPIO 22):** I2C Clock Line
- **Pull-up Resistors:** 4.7 kΩ to 3.3V (already on MPU6050 breakout)
- **Bus Capacitance:** ≤400 pF for reliable operation

**Layout Rules:**
1. Keep I2C traces ≤10 cm long to minimize capacitance
2. Route SDA and SCL together to maintain impedance matching
3. Guard traces with ground to reduce cross-talk
4. Add 100 nF filter capacitor at the end of SDA/SCL (optional)

```
ESP32                     MPU6050
GPIO21(SDA) ──────────── SDA (with 4.7kΩ pullup)
GPIO22(SCL) ──────────── SCL (with 4.7kΩ pullup)
        GND ──────────── GND
```

### UART Serial (Debugging)

**Pin Allocation:**
- **TX (GPIO 1):** Transmit to USB Serial Adapter
- **RX (GPIO 3):** Receive from USB Serial Adapter
- **Baud Rate:** 115,200 bps

**Protection:**
- Add 100 Ω series resistors in TX/RX lines to reduce EMI
- Optional: TVS diode (PESD5V0X2BL) for ESD protection

### Ultrasonic Sensor Interface

**Pin Configuration:**
- **TRIG (GPIO 18):** Output, LOW logic, TTL level
- **ECHO (GPIO 19):** Input, Interrupt-capable pin, 5V tolerant
- **GND/Vcc:** Separate 5V rail (not 3.3V!)

**Important:** ESP32 GPIO pins are 3.3V tolerant. Verify that ultrasonic sensor echo output is clamped to 3.3V:

```
Ultrasonic ECHO (5V) ──┬─── GPIO 19 (3.3V)
                       │
                     [R1=1kΩ]
                       │
                     [R2=2kΩ]
                       │
                      GND

Voltage Divider: Vout = 5V × (2kΩ / 3kΩ) = 3.33V ≈ 3.3V (safe)
```

### Electromagnetic Compatibility (EMC)

**WiFi Radiation Mitigation:**
- Dedicate a ground plane on Layer 2
- Keep high-speed digital traces (UART, SPI) away from RF antenna area
- Add 100 nF bypass capacitors near digital power pins

**Board Grounding:**
- Multiple star-point connections from all analog GND to digital GND
- Single low-impedance connection to external ground reference
- Via stitching around RF region for Faraday cage effect

---

## Component Selection

### Critical Components

#### 1. **ESP32 DevKit v4.4**
- **Microcontroller:** Tensilica Xtensa LX6 dual-core
- **Flash:** 4 MB
- **RAM:** 520 KB (SRAM)
- **Interfaces:** SPI, I2C, UART, GPIO, ADC, PWM
- **WiFi:** 802.11 b/g/n @ 2.4 GHz
- **Bluetooth:** 4.2 LE
- **Operating Voltage:** 3.0 - 3.6V
- **Considerations:** 
  - Built-in USB-serial for easy programming
  - Integrated voltage regulator (1117-type)
  - Already includes decoupling capacitors

#### 2. **MPU6050 IMU Module**
- **Sensors:** 3-axis accelerometer + 3-axis gyroscope
- **Accel Range:** ±2, ±4, ±8, ±16 g
- **Gyro Range:** ±250, ±500, ±1000, ±2000 °/s
- **I2C Address:** 0x68 (configurable to 0x69)
- **Typical Current:** 3.8 mA
- **Breakout includes:** I2C pull-ups, bypass caps
- **Note:** Avoid placing near heat sources; thermal drift affects accuracy

#### 3. **HC-SR04 Ultrasonic Module**
- **Type:** Non-contact distance measurement
- **Range:** 2 cm - 400 cm
- **Accuracy:** ±3 mm
- **Operating Voltage:** 5V DC
- **Logic Levels:** TTL output (5V) - requires level shifting!
- **Current:** ~15-30 mA during measurement
- **Frequency:** ~40 kHz carrier

#### 4. **LM1117-3.3 Voltage Regulator**
- **Package:** SOT-223 (surface-mount friendly)
- **Input Range:** 5V - 20V (5V recommended)
- **Output:** 3.3V ± 3%
- **Max Current:** 800 mA
- **Quiescent:** ~10 mA
- **Dropout:** 1.3V typical @ 800 mA

#### 5. **Passive Components**

| Component | Value | Qty | Purpose |
|-----------|-------|-----|---------|
| Ceramic Cap | 100 nF (X7R) | 8 | Bypass caps near ICs |
| Electrolytic | 10 µF (16V) | 4 | Bulk capacitance |
| Tantalum | 10 µF (6.3V) | 2 | Low-ESR output filtering |
| Resistor | 4.7 kΩ | 2 | I2C pull-ups (onboard) |
| Resistor | 100 Ω | 4 | UART/GPIO EMI damping |
| Resistor | 1 kΩ / 2 kΩ | 2 | Ultrasonic level divider |
| LED | Red 3mm | 1 | Status indicator |
| Resistor | 330 Ω | 1 | LED current limiting |

---

## PCB Layout Strategies

### Board Specifications

- **Size:** 60 mm × 40 mm (2.4" × 1.6") - Compact form factor
- **Layers:** 4-layer PCB (optimal for signal integrity)
  - Layer 1: Signal + Component side
  - Layer 2: Ground plane
  - Layer 3: Power plane (3.3V + 5V)
  - Layer 4: Signal + solder side
- **Via Size:** 0.3 mm drill, 0.5 mm pad
- **Trace Width:** 
  - High-speed: 10 mil (0.25 mm)
  - Power: 12-16 mil (0.3-0.4 mm)
  - Impedance-controlled: 8 mil (0.2 mm)

### Component Placement Zones

```
┌─────────────────────────────────────────────────┐
│  Status LED     Ultrasonic (J1)                │
│   (D1)                                         │
│                                               │
│           ┌──────────────────┐               │
│    ┌──────│      ESP32       │───────┐       │
│    │      │   DevKit v4.4    │       │       │
│    │      │                  │       │       │
│    │      └──────────────────┘       │       │
│    │                                 │       │
│    │  ┌────┬────┐     ┌────────┐    │       │
│    │  │R1/2│C1/2│     │MPU6050 │    │       │
│    │  │1kΩ │100nF│    │ Module │    │       │
│    │  └────┴────┘     └────────┘    │       │
│    │                                 │       │
│    │   ┌─────────────┐  ┌────────┐  │       │
│    │   │  LM1117     │  │  C_bulk│  │       │
│    │   │  5V→3.3V    │  │ 10µF   │  │       │
│    │   └─────────────┘  └────────┘  │       │
│    │                                 │       │
│    └─────────────────────────────────┘       │
│  Power Input (USB-C)  Debug UART (J2)        │
└─────────────────────────────────────────────────┘
```

### Layer Stack-up

**Layer 1 (Front):**
- Component mounting side
- Signal traces (I2C, UART, GPIO)
- Via stitching around power regions

**Layer 2 (Ground Plane):**
- Solid ground plane (entire layer)
- Provides low-impedance return path
- Via stitching around digital/analog boundaries

**Layer 3 (Power Plane):**
- Dedicated 3.3V rail (central region)
- Dedicated 5V input rail (perimeter)
- Star-point connection between power domains

**Layer 4 (Back):**
- Secondary signal layer
- High-current return paths
- Via stitching for thermal management

### Critical Routing Rules

1. **Keep I2C ≤ 10 cm:** SDA/SCL trace length matching (±2mm)
2. **Separate Power Domains:** 5V and 3.3V traces on different layers if possible
3. **Via Placement:** Place vias every 5-10 mm along ground plane edges
4. **EMI Reduction:** Return paths must be directly underneath or adjacent to signal traces
5. **Thermal Management:** Large copper pour under LDO for heat dissipation

---

## Miniaturization Techniques

### 1. Multi-layer PCB Benefits

- **Space Efficiency:** Via-based connections eliminate surface routing congestion
- **Impedance Control:** Inner power/ground planes maintain consistent impedance
- **Thermal Dissipation:** Internal heat can be conducted through layer stack

### 2. Component Density Optimization

**Selected Measures:**
- **Surface Mount Technology (SMT):** All passive components (0805 package)
- **Minimal Connectors:** Simplified to 2 headers only (power input + debug UART)
- **Integrated Modules:** MPU6050 + LDO already on breakout boards reduces individual components
- **Via Stitching:** Replaces bulky chassis grounding wires

### 3. Package Selection

| Component | Package | Reason |
|-----------|---------|--------|
| LM1117 | SOT-223 | Compact vs TO-252, minimal footprint |
| Resistors | 0805 | Standard size, hand-solderable if needed |
| Capacitors | 0805 (ceramic), 1206 (tantalum) | Standard, good current handling |
| LED | 0805 SMD | Reduced board area vs through-hole |

### 4. High-Density Interconnect (HDI)

- **Micro-vias:** 0.25 mm diameter vias for compact via placement
- **Blind vias:** Connect Layer 1→2 without drilling through entire board
- **Buried vias:** Connect Layer 2↔3 (internal power distribution)

### 5. Stackup Optimization for Size

For ultra-compact designs, consider:
- **2-layer Stackup:** Reduces cost but increases trace routing complexity
- **4-layer with Hybrid Planes:** Mixed power/signal on layers 2-3
- **Flex PCB Integration:** Reduce overall system footprint using flexible substrate sections

---

## Testing & Verification

### Pre-Manufacturing Validation (CAD Level)

1. **Design Rule Check (DRC):**
   - Minimum trace width: 8 mil
   - Minimum clearance: 8 mil
   - Via hole vs trace spacing: 10 mil

2. **Electrical Rule Check (ERC):**
   - No floating nets
   - Proper power distribution to all pins
   - I2C pull-ups verified (connected to 3.3V)

3. **Antenna Simulation (RF):**
   - WiFi antenna clearance: ≥5 mm from traces
   - Ground plane vias within 1 mm of antenna base

### Post-Manufacturing Testing

#### 1. **Visual Inspection**
- Check solder joints under magnification (20×)
- Verify component orientation (polarity markers)
- Inspect for solder bridges between traces

#### 2. **Continuity Testing**
```python
# Multimeter tests:
- GND ↔ GND (all vias): <0.5 Ω expected
- 3.3V rail: Should be isolated when powered off
- I2C bus: Pull-up resistance ≈2.35 kΩ (parallel 4.7k + 4.7k)
```

#### 3. **Power-On Self-Test (POST)**
```cpp
// Firmware validation:
1. LDO output: 3.3V ±5% at full load
2. MPU6050 I2C communication:
   - Read WHO_AM_I register (0x75): Should return 0x68
   - Verify accelerometer scale output: ~9.81 m/s² on Z-axis (gravity)
3. Ultrasonic distance measurement:
   - 0V distance = 2 cm minimum
   - 5V distance = 400 cm maximum
```

#### 4. **Functional Verification**
- Record telemetry data for 10 minutes
- Verify MQTT connectivity and cloud logging
- Test obstacle detection accuracy at various distances
- Monitor LDO thermal behavior under sustained load

### Environmental Testing (Optional)

- **Temperature Range:** -10°C to +60°C operational
- **Humidity:** Up to 90% non-condensing
- **Vibration:** IEC 60068-2-6 (sinusoidal sweep 10-500 Hz)
- **EMI/RFI:** CE compliance testing per EN 61000-6-2

---

## Manufacturing Considerations

### PCB Fabrication

**Recommended Specifications:**
- Copper weight: 1 oz (35 µm)
- Surface finish: ENIG (Electroless Nickel Immersion Gold)
  - Better solderability than HASL
  - Prevents copper oxidation
- Solder mask: LPI (Liquid Photoimageable) for fine details
- Silkscreen: White, <6 pt font for legibility

### Assembly (PCBA)

- **Pick & Place Tolerance:** ±0.1 mm (standard)
- **Solder Reflow Profile:**
  - Preheat: 150-180°C for 60-90 sec
  - Ramp: 3°C/sec
  - Peak: 245-260°C for 10-30 sec
  - Cool: 6°C/sec to <100°C

### Cost Optimization

- **NRE (Non-Recurring Engineering):** ~$500-1000 per board iteration
- **Unit Cost (100 qty):** ~$35-50 per assembled board
- **Lead Time:** 4-6 weeks (standard manufacturing)
- **Fast-track:** 2 weeks at 2-3× cost premium

---

## Design Files & Resources

### KiCad Project Structure
```
IoT_Embedded_Controller.kicad_pro
├── schematic.kicad_sch
├── pcb.kicad_pcb
├── symbols/
│   ├── esp32.kicad_sym
│   ├── mpu6050.kicad_sym
│   └── regulators.kicad_sym
├── footprints/
│   ├── 0805_resistor.kicad_mod
│   ├── 1206_capacitor.kicad_mod
│   └── sot223_regulator.kicad_mod
└── 3d_models/
    └── esp32_case.step
```

### External Resources

- **ESP32 Datasheet:** https://www.espressif.com/en/products/socs/esp32
- **MPU6050 Datasheet:** https://invensense.tdk.com (InvenSense)
- **KiCad Documentation:** https://docs.kicad.org/
- **PCB Assembly Partner:** JLCPCB, PCBWay, Oshpark

---

## Revision History

| Revision | Date | Changes |
|----------|------|---------|
| v1.0 | Feb 2025 | Initial design documentation |
| v1.1 | TBD | Post-manufacturing updates |

---

**Document Prepared By:** Anukool Shidhore  
**Role:** Embedded Systems Architect  
**Last Updated:** Feb 2025
