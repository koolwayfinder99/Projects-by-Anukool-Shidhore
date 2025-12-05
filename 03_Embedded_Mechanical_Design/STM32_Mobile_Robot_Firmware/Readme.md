# Autonomous Mobile Robot with Embedded Control (STM32)

**Role:** Embedded Systems Engineer
**Duration:** Nov 2025 - Present
**Tech Stack:** STM32 Nucleo, Embedded C, STM32CubeIDE, L298 Drivers, I2C/UART

## Project Overview
Developed a bare-metal embedded control system for an autonomous mobile robot using the STM32 Nucleo development board. This project focuses on low-level firmware architecture rather than high-level OS.

## Key Technical Contributions
* **Firmware Architecture:** Engineered an exclusively **interrupt-based firmware architecture** for real-time sensor processing and actuator control using **Embedded C**.
* **Sensor Integration:** Integrated ultrasonic sensors, buzzers, and ADC inputs to handle environmental perception.
* **Motor Control:** Implemented PWM control logic for the propulsion system using L298 H-bridge drivers to ensure smooth velocity transitions.
* **Communication:** Validated system telemetry using serial communication modules (UART/I2C) for debugging and data logging.
## System Architecture
Here is the high-level data flow for the embedded control system:

```mermaid
graph TD;
    A[Ultrasonic Sensors] -->|ADC Reading| B(STM32 Nucleo);
    C[IMU - MPU6050] -->|I2C| B;
    B -->|PWM Signals| D[L298 Motor Driver];
    B -->|UART Telemetry| E[Laptop Dashboard];
    D -->|Voltage| F[DC Motors];
    power[Li-Ion Battery] -->|Buck Converter| B;