/**
 * @file main.cpp
 * @brief ESP32 IoT Embedded Controller with MPU6050 IMU and Ultrasonic Obstacle Avoidance
 * @author Anukool Shidhore
 * @date Oct 2024 - Feb 2025
 * 
 * Task-based architecture using FreeRTOS for concurrent sensor reading,
 * orientation tracking, and real-time interrupt handling.
 */

#include <Arduino.h>
#include <Wire.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <math.h>

// ==================== Configuration ====================
#define MPU6050_ADDR 0x68
#define I2C_SDA_PIN 21
#define I2C_SCL_PIN 22
#define UART_TX_PIN 1
#define UART_RX_PIN 3

#define ULTRASONIC_TRIG 18
#define ULTRASONIC_ECHO 19
#define OBSTACLE_THRESHOLD 20  // cm

#define MQTT_BROKER "mqtt.example.com"
#define MQTT_PORT 1883
#define MQTT_CLIENT_ID "esp32-iot-controller"
#define MQTT_TOPIC_TELEMETRY "esp32/telemetry"
#define MQTT_TOPIC_STATUS "esp32/status"

// WiFi credentials (configure via environment)
const char* WIFI_SSID = "YOUR_SSID";
const char* WIFI_PASSWORD = "YOUR_PASSWORD";

// ==================== MPU6050 Registers ====================
#define MPU6050_PWR_MGMT_1 0x6B
#define MPU6050_ACCEL_XOUT_H 0x3B
#define MPU6050_GYRO_XOUT_H 0x43

// ==================== Global Variables ====================
volatile float accelX, accelY, accelZ;
volatile float gyroX, gyroY, gyroZ;
volatile float roll, pitch, yaw = 0.0;
volatile unsigned long lastMicros = 0;

volatile int ultrasonic_distance = 0;
volatile bool obstacle_detected = false;

WiFiClient espClient;
PubSubClient mqttClient(espClient);

TaskHandle_t sensorTaskHandle = NULL;
TaskHandle_t orientationTaskHandle = NULL;
TaskHandle_t mqttTaskHandle = NULL;

// ==================== I2C Communication ====================
/**
 * @brief Read multiple bytes from MPU6050
 */
bool i2c_read(uint8_t addr, uint8_t reg, uint8_t* data, uint8_t len) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) {
    Serial.println("[ERROR] I2C transmission failed");
    return false;
  }
  
  if (Wire.requestFrom(addr, len, true) != len) {
    Serial.println("[ERROR] I2C read failed - insufficient bytes");
    return false;
  }
  
  for (int i = 0; i < len; i++) {
    data[i] = Wire.read();
  }
  return true;
}

/**
 * @brief Write byte to MPU6050
 */
bool i2c_write(uint8_t addr, uint8_t reg, uint8_t data) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  Wire.write(data);
  if (Wire.endTransmission() != 0) {
    Serial.println("[ERROR] I2C write failed");
    return false;
  }
  return true;
}

// ==================== MPU6050 Initialization ====================
/**
 * @brief Initialize MPU6050 with proper error handling
 */
bool mpu6050_init() {
  uint8_t id = 0;
  int retry_count = 3;
  
  while (retry_count--) {
    if (i2c_read(MPU6050_ADDR, 0x75, &id, 1)) {
      if (id == 0x68) {
        Serial.println("[INFO] MPU6050 detected (ID: 0x68)");
        break;
      }
    }
    delay(100);
  }
  
  if (retry_count < 0) {
    Serial.println("[ERROR] MPU6050 not found. Check I2C connections.");
    return false;
  }
  
  // Wake up MPU6050
  if (!i2c_write(MPU6050_ADDR, MPU6050_PWR_MGMT_1, 0x00)) {
    Serial.println("[ERROR] Failed to wake MPU6050");
    return false;
  }
  
  delay(100);
  
  // Set accelerometer range to ±8g (0x10)
  if (!i2c_write(MPU6050_ADDR, 0x1C, 0x10)) {
    Serial.println("[ERROR] Failed to configure accelerometer range");
    return false;
  }
  
  // Set gyroscope range to ±500°/s (0x08)
  if (!i2c_write(MPU6050_ADDR, 0x1B, 0x08)) {
    Serial.println("[ERROR] Failed to configure gyroscope range");
    return false;
  }
  
  Serial.println("[INFO] MPU6050 initialized successfully");
  return true;
}

// ==================== Sensor Reading Task ====================
/**
 * @brief FreeRTOS task to continuously read MPU6050 data
 */
void sensorReadTask(void* parameter) {
  uint8_t data[14];
  int16_t ax, ay, az, gx, gy, gz;
  int retry_count;
  
  Serial.println("[INFO] Sensor read task started");
  
  while (1) {
    retry_count = 2;
    
    if (i2c_read(MPU6050_ADDR, MPU6050_ACCEL_XOUT_H, data, 14)) {
      // Parse accelerometer data (raw 16-bit signed)
      ax = (data[0] << 8) | data[1];
      ay = (data[2] << 8) | data[3];
      az = (data[4] << 8) | data[5];
      
      // Parse gyroscope data
      gx = (data[8] << 8) | data[9];
      gy = (data[10] << 8) | data[11];
      gz = (data[12] << 8) | data[13];
      
      // Convert to physical units (8g scale, 500°/s scale)
      accelX = ax / 4096.0;  // ~8g sensitivity
      accelY = ay / 4096.0;
      accelZ = az / 4096.0;
      
      gyroX = gx / 65.5;     // ~65.5 LSB/(°/s) for 500°/s range
      gyroY = gy / 65.5;
      gyroZ = gz / 65.5;
    } else {
      if (--retry_count <= 0) {
        Serial.println("[WARN] Failed to read MPU6050 after retries");
      }
      delay(50);
      continue;
    }
    
    vTaskDelay(pdMS_TO_TICKS(20));  // 50 Hz sampling rate
  }
}

// ==================== Orientation Tracking Task ====================
/**
 * @brief FreeRTOS task for orientation estimation using complementary filter
 * Complimentary filter combines accelerometer and gyroscope for drift-free orientation
 */
void orientationTrackingTask(void* parameter) {
  const float alpha = 0.98;  // Complementary filter coefficient
  unsigned long currentMicros;
  float dt;
  
  Serial.println("[INFO] Orientation tracking task started");
  lastMicros = micros();
  
  while (1) {
    currentMicros = micros();
    dt = (currentMicros - lastMicros) / 1000000.0;  // Convert to seconds
    lastMicros = currentMicros;
    
    // Prevent unrealistic dt values
    if (dt > 0.1) dt = 0.01;
    if (dt < 0.001) dt = 0.001;
    
    // Calculate roll and pitch from accelerometer
    float accel_roll = atan2(accelY, accelZ) * 180 / M_PI;
    float accel_pitch = atan2(-accelX, sqrt(accelY * accelY + accelZ * accelZ)) * 180 / M_PI;
    
    // Complementary filter integration
    roll = alpha * (roll + gyroX * dt) + (1 - alpha) * accel_roll;
    pitch = alpha * (pitch + gyroY * dt) + (1 - alpha) * accel_pitch;
    yaw = yaw + gyroZ * dt;
    
    // Constrain angles
    if (yaw > 360.0) yaw -= 360.0;
    if (yaw < 0.0) yaw += 360.0;
    
    vTaskDelay(pdMS_TO_TICKS(50));
  }
}

// ==================== Ultrasonic Sensor Interrupt ====================
/**
 * @brief Interrupt handler for ultrasonic echo detection
 */
volatile unsigned long echo_start = 0;
volatile unsigned long echo_duration = 0;

void IRAM_ATTR ultrasonic_echo_isr() {
  if (digitalRead(ULTRASONIC_ECHO) == HIGH) {
    echo_start = micros();
  } else {
    echo_duration = micros() - echo_start;
    // Distance = (time / 2) / 29.1 cm/microsecond
    ultrasonic_distance = echo_duration / 58;  // Simplified for speed
    
    if (ultrasonic_distance < OBSTACLE_THRESHOLD) {
      obstacle_detected = true;
    } else {
      obstacle_detected = false;
    }
  }
}

/**
 * @brief Initialize ultrasonic sensor
 */
void ultrasonic_init() {
  pinMode(ULTRASONIC_TRIG, OUTPUT);
  pinMode(ULTRASONIC_ECHO, INPUT);
  attachInterrupt(digitalPinToInterrupt(ULTRASONIC_ECHO), ultrasonic_echo_isr, CHANGE);
  Serial.println("[INFO] Ultrasonic sensor initialized");
}

/**
 * @brief Trigger ultrasonic measurement
 */
void ultrasonic_trigger() {
  digitalWrite(ULTRASONIC_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(ULTRASONIC_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(ULTRASONIC_TRIG, LOW);
}

// ==================== WiFi and MQTT ====================
/**
 * @brief Connect to WiFi with retry logic
 */
void wifi_connect() {
  int retry = 0;
  Serial.print("[INFO] Connecting to WiFi: ");
  Serial.println(WIFI_SSID);
  
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  
  while (WiFi.status() != WL_CONNECTED && retry < 20) {
    delay(500);
    Serial.print(".");
    retry++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[INFO] WiFi connected");
    Serial.print("[INFO] IP address: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\n[ERROR] WiFi connection failed");
  }
}

/**
 * @brief MQTT reconnect with exponential backoff
 */
void mqtt_reconnect() {
  static int reconnect_attempts = 0;
  const int MAX_RECONNECT_ATTEMPTS = 5;
  
  if (reconnect_attempts >= MAX_RECONNECT_ATTEMPTS) {
    Serial.println("[ERROR] Max MQTT reconnect attempts reached");
    reconnect_attempts = 0;
    vTaskDelay(pdMS_TO_TICKS(30000));  // Wait 30s before retry
    return;
  }
  
  Serial.print("[INFO] Attempting MQTT connection (attempt ");
  Serial.print(reconnect_attempts + 1);
  Serial.println(")");
  
  if (mqttClient.connect(MQTT_CLIENT_ID)) {
    Serial.println("[INFO] MQTT connected");
    mqttClient.publish(MQTT_TOPIC_STATUS, "online");
    reconnect_attempts = 0;
  } else {
    Serial.print("[ERROR] MQTT connection failed, rc=");
    Serial.println(mqttClient.state());
    reconnect_attempts++;
    vTaskDelay(pdMS_TO_TICKS(1000 * (1 << reconnect_attempts)));  // Exponential backoff
  }
}

/**
 * @brief MQTT publish telemetry
 */
void mqtt_publish_telemetry() {
  static char payload[256];
  
  snprintf(payload, sizeof(payload),
    "{\"roll\":%.2f,\"pitch\":%.2f,\"yaw\":%.2f,\"ax\":%.2f,\"ay\":%.2f,\"az\":%.2f,\"distance\":%d,\"obstacle\":%s}",
    roll, pitch, yaw, accelX, accelY, accelZ, ultrasonic_distance, obstacle_detected ? "true" : "false");
  
  if (!mqttClient.publish(MQTT_TOPIC_TELEMETRY, payload)) {
    Serial.println("[WARN] MQTT publish failed");
  }
}

/**
 * @brief FreeRTOS task for MQTT communication
 */
void mqttTask(void* parameter) {
  Serial.println("[INFO] MQTT task started");
  
  while (1) {
    if (WiFi.status() == WL_CONNECTED) {
      if (!mqttClient.connected()) {
        mqtt_reconnect();
      }
      mqttClient.loop();
      mqtt_publish_telemetry();
    } else {
      wifi_connect();
    }
    
    vTaskDelay(pdMS_TO_TICKS(1000));
  }
}

// ==================== Initialization ====================
void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n\n[INFO] ===== ESP32 IoT Embedded Controller =====");
  Serial.println("[INFO] Hardware: ESP32 with MPU6050 + Ultrasonic");
  Serial.println("[INFO] Project Period: Oct 2024 - Feb 2025");
  
  // Initialize I2C
  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);
  Wire.setClock(400000);  // 400 kHz
  Serial.println("[INFO] I2C initialized at 400 kHz");
  
  // Initialize sensors
  if (!mpu6050_init()) {
    Serial.println("[FATAL] MPU6050 initialization failed");
    while (1) delay(1000);
  }
  
  ultrasonic_init();
  
  // Initialize MQTT
  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  
  // Connect WiFi
  wifi_connect();
  
  // Create FreeRTOS tasks
  xTaskCreatePinnedToCore(
    sensorReadTask,           // Function
    "SensorRead",             // Name
    2048,                     // Stack size (words)
    NULL,                     // Parameter
    2,                        // Priority (higher = more important)
    &sensorTaskHandle,        // Task handle
    0                         // Core 0
  );
  
  xTaskCreatePinnedToCore(
    orientationTrackingTask,
    "OrientationTracking",
    2048,
    NULL,
    2,
    &orientationTaskHandle,
    0
  );
  
  xTaskCreatePinnedToCore(
    mqttTask,
    "MQTTComm",
    2048,
    NULL,
    1,                        // Lower priority for network tasks
    &mqttTaskHandle,
    1                         // Core 1
  );
  
  Serial.println("[INFO] All tasks created successfully");
  Serial.println("[INFO] System ready. Monitoring sensors...\n");
}

void loop() {
  // Ultrasonic trigger every 100ms
  static unsigned long last_trigger = 0;
  
  if (millis() - last_trigger >= 100) {
    ultrasonic_trigger();
    last_trigger = millis();
  }
  
  // Print diagnostics every 2 seconds
  static unsigned long last_print = 0;
  if (millis() - last_print >= 2000) {
    Serial.print("[TELEMETRY] Roll: ");
    Serial.print(roll, 2);
    Serial.print("° Pitch: ");
    Serial.print(pitch, 2);
    Serial.print("° Yaw: ");
    Serial.print(yaw, 2);
    Serial.print("° Distance: ");
    Serial.print(ultrasonic_distance);
    Serial.print("cm Obstacle: ");
    Serial.println(obstacle_detected ? "YES" : "NO");
    
    last_print = millis();
  }
  
  delay(10);
}
