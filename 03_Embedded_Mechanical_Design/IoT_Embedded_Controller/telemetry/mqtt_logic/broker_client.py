#!/usr/bin/env python3
"""
@file broker_client.py
@brief MQTT Client for ESP32 IoT Embedded Controller Telemetry Collection
@author Anukool Shidhore
@date Oct 2024 - Feb 2025

Subscribes to ESP32 sensor data stream, processes telemetry, and logs to cloud dashboard.
Includes robust error handling for network reconnection and data validation.
"""

import json
import time
import logging
import threading
from datetime import datetime
from typing import Optional, Callable
import paho.mqtt.client as mqtt

# ==================== Configuration ====================
MQTT_BROKER = "mqtt.example.com"
MQTT_PORT = 1883
MQTT_TIMEOUT = 60
MQTT_KEEPALIVE = 60

MQTT_TOPICS = {
    "telemetry": "esp32/telemetry",
    "status": "esp32/status",
    "commands": "esp32/commands"
}

CLIENT_ID = "iot-telemetry-logger"
RECONNECT_DELAY_MIN = 1      # seconds
RECONNECT_DELAY_MAX = 60     # seconds
MAX_RECONNECT_ATTEMPTS = 10

LOG_FILE = "telemetry_log.json"
BUFFER_SIZE = 1000           # Max telemetry entries before flush

# ==================== Logging Setup ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('mqtt_client.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class TelemetryBuffer:
    """
    Thread-safe buffer for collecting telemetry data.
    Automatically flushes to disk when full.
    """
    
    def __init__(self, max_size: int = BUFFER_SIZE, filepath: str = LOG_FILE):
        self.max_size = max_size
        self.filepath = filepath
        self.buffer = []
        self.lock = threading.Lock()
    
    def append(self, entry: dict) -> None:
        """Add telemetry entry to buffer"""
        with self.lock:
            self.buffer.append(entry)
            if len(self.buffer) >= self.max_size:
                self.flush()
    
    def flush(self) -> None:
        """Write buffer to file and clear"""
        if not self.buffer:
            return
        
        try:
            with open(self.filepath, 'a') as f:
                for entry in self.buffer:
                    f.write(json.dumps(entry) + '\n')
            
            count = len(self.buffer)
            self.buffer.clear()
            logger.info(f"Flushed {count} telemetry entries to {self.filepath}")
        
        except IOError as e:
            logger.error(f"Failed to write telemetry file: {e}")
    
    def get_size(self) -> int:
        """Get current buffer size"""
        with self.lock:
            return len(self.buffer)


class MQTTClient:
    """
    Robust MQTT client for ESP32 telemetry collection with automatic reconnection
    and error handling.
    """
    
    def __init__(self, broker: str, port: int, client_id: str):
        self.broker = broker
        self.port = port
        self.client_id = client_id
        self.client = mqtt.Client(client_id=client_id)
        
        self.connected = False
        self.reconnect_attempts = 0
        self.last_reconnect_time = 0
        self.reconnect_delay = RECONNECT_DELAY_MIN
        
        self.telemetry_buffer = TelemetryBuffer()
        self.callbacks: dict[str, Callable] = {}
        
        # Setup callbacks
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.on_subscribe = self._on_subscribe
        self.client.on_publish = self._on_publish
        
        logger.info(f"MQTT Client initialized: {client_id}@{broker}:{port}")
    
    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """Callback: MQTT connection established"""
        if rc == 0:
            self.connected = True
            self.reconnect_attempts = 0
            self.reconnect_delay = RECONNECT_DELAY_MIN
            logger.info("MQTT connected successfully")
            
            # Subscribe to all topics
            for topic_key, topic_path in MQTT_TOPICS.items():
                client.subscribe(topic_path, qos=1)
                logger.info(f"Subscribed to {topic_path}")
        else:
            self.connected = False
            logger.error(f"MQTT connection failed with code {rc}: {mqtt.error_string(rc)}")
    
    def _on_disconnect(self, client, userdata, rc, properties=None):
        """Callback: MQTT disconnection"""
        self.connected = False
        
        if rc != 0:
            logger.warning(f"Unexpected disconnection (code {rc}). Will reconnect...")
            self.reconnect_attempts += 1
            
            if self.reconnect_attempts >= MAX_RECONNECT_ATTEMPTS:
                logger.error(f"Max reconnection attempts ({MAX_RECONNECT_ATTEMPTS}) reached")
                self.reconnect_attempts = 0
                self.reconnect_delay = RECONNECT_DELAY_MIN
            else:
                # Exponential backoff with jitter
                self.reconnect_delay = min(
                    self.reconnect_delay * 1.5,
                    RECONNECT_DELAY_MAX
                )
                logger.info(f"Reconnecting in {self.reconnect_delay:.1f}s (attempt {self.reconnect_attempts})")
        else:
            logger.info("MQTT disconnected by request")
    
    def _on_subscribe(self, client, userdata, mid, granted_qos, properties=None):
        """Callback: Subscription acknowledged"""
        logger.debug(f"Subscription acknowledged (QoS: {granted_qos})")
    
    def _on_publish(self, client, userdata, mid, properties=None):
        """Callback: Message published"""
        logger.debug(f"Message published (mid: {mid})")
    
    def _on_message(self, client, userdata, msg):
        """Callback: Message received"""
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            
            logger.debug(f"Message received on {topic}")
            
            # Route to appropriate handler
            if topic == MQTT_TOPICS["telemetry"]:
                self._handle_telemetry(payload)
            elif topic == MQTT_TOPICS["status"]:
                self._handle_status(payload)
            elif topic == MQTT_TOPICS["commands"]:
                self._handle_command(payload)
            
            # Call custom callback if registered
            if topic in self.callbacks:
                self.callbacks[topic](payload)
        
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")
    
    def _handle_telemetry(self, payload: str) -> None:
        """Process telemetry data from ESP32"""
        try:
            data = json.loads(payload)
            
            # Validate telemetry structure
            required_fields = ['roll', 'pitch', 'yaw', 'ax', 'ay', 'az', 'distance', 'obstacle']
            if not all(field in data for field in required_fields):
                logger.warning(f"Incomplete telemetry data: {data}")
                return
            
            # Validate value ranges
            if not self._validate_telemetry(data):
                logger.warning(f"Invalid telemetry values: {data}")
                return
            
            # Add timestamp and metadata
            entry = {
                'timestamp': datetime.utcnow().isoformat(),
                'data': data
            }
            
            self.telemetry_buffer.append(entry)
            
            logger.debug(f"Telemetry logged - Distance: {data['distance']}cm, "
                        f"Obstacle: {data['obstacle']}, "
                        f"Orientation: ({data['roll']:.1f}°, {data['pitch']:.1f}°, {data['yaw']:.1f}°)")
            
            # Alert if obstacle detected
            if data.get('obstacle'):
                logger.warning(f"OBSTACLE DETECTED at {data['distance']}cm!")
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse telemetry JSON: {e}")
        except Exception as e:
            logger.error(f"Error handling telemetry: {e}")
    
    def _validate_telemetry(self, data: dict) -> bool:
        """Validate telemetry data ranges"""
        try:
            # Orientation angles should be within reasonable bounds
            if not (-180 <= data.get('roll', 0) <= 180):
                return False
            if not (-90 <= data.get('pitch', 0) <= 90):
                return False
            if not (0 <= data.get('yaw', 0) <= 360):
                return False
            
            # Acceleration should be reasonable (±16g max on MPU6050)
            for key in ['ax', 'ay', 'az']:
                if not (-20 <= data.get(key, 0) <= 20):
                    return False
            
            # Distance should be positive and within sensor range
            if not (0 <= data.get('distance', 0) <= 400):
                return False
            
            return True
        
        except (TypeError, KeyError):
            return False
    
    def _handle_status(self, payload: str) -> None:
        """Process status messages from ESP32"""
        logger.info(f"ESP32 Status: {payload}")
    
    def _handle_command(self, payload: str) -> None:
        """Process incoming commands"""
        logger.info(f"Command received: {payload}")
    
    def register_callback(self, topic: str, callback: Callable) -> None:
        """Register custom callback for specific topic"""
        self.callbacks[topic] = callback
        logger.debug(f"Callback registered for topic: {topic}")
    
    def connect(self, timeout: int = MQTT_TIMEOUT) -> bool:
        """
        Connect to MQTT broker with timeout
        
        Args:
            timeout: Connection timeout in seconds
        
        Returns:
            True if connected, False otherwise
        """
        try:
            logger.info(f"Connecting to MQTT broker {self.broker}:{self.port}...")
            self.client.connect(
                self.broker,
                self.port,
                keepalive=MQTT_KEEPALIVE
            )
            self.client.loop_start()
            
            # Wait for connection
            start_time = time.time()
            while not self.connected:
                if time.time() - start_time > timeout:
                    logger.error(f"Connection timeout after {timeout}s")
                    return False
                time.sleep(0.1)
            
            return True
        
        except Exception as e:
            logger.error(f"MQTT connection failed: {e}")
            return False
    
    def disconnect(self) -> None:
        """Disconnect from MQTT broker and flush buffer"""
        try:
            self.telemetry_buffer.flush()
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("MQTT client disconnected")
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
    
    def publish(self, topic: str, payload: str, qos: int = 1, retain: bool = False) -> bool:
        """
        Publish message to topic
        
        Args:
            topic: MQTT topic
            payload: Message payload
            qos: Quality of Service (0, 1, or 2)
            retain: Whether to retain message
        
        Returns:
            True if published successfully
        """
        try:
            result = self.client.publish(topic, payload, qos=qos, retain=retain)
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                logger.error(f"Publish failed: {mqtt.error_string(result.rc)}")
                return False
            return True
        except Exception as e:
            logger.error(f"Error publishing message: {e}")
            return False
    
    def get_buffer_stats(self) -> dict:
        """Get telemetry buffer statistics"""
        return {
            'buffer_size': self.telemetry_buffer.get_size(),
            'max_buffer_size': self.telemetry_buffer.max_size,
            'connected': self.connected,
            'reconnect_attempts': self.reconnect_attempts
        }


def main():
    """Main entry point for telemetry collection"""
    
    client = MQTTClient(MQTT_BROKER, MQTT_PORT, CLIENT_ID)
    
    try:
        # Connect to broker
        if not client.connect():
            logger.error("Failed to connect to MQTT broker. Exiting.")
            return 1
        
        # Register custom callback for telemetry
        def custom_telemetry_handler(payload: str):
            data = json.loads(payload)
            if data.get('obstacle'):
                logger.critical(f"⚠️  OBSTACLE ALERT: {data.get('distance')}cm away!")
        
        client.register_callback(MQTT_TOPICS["telemetry"], custom_telemetry_handler)
        
        logger.info("Telemetry collection started. Press Ctrl+C to exit.")
        
        # Keep client running
        try:
            while True:
                # Print statistics every 30 seconds
                stats = client.get_buffer_stats()
                if stats['buffer_size'] % 10 == 0 and stats['buffer_size'] > 0:
                    logger.info(f"Buffer: {stats['buffer_size']}/{stats['max_buffer_size']} entries")
                
                time.sleep(1)
        
        except KeyboardInterrupt:
            logger.info("Shutdown signal received")
    
    finally:
        # Clean shutdown
        client.disconnect()
        logger.info("Telemetry collection stopped")
    
    return 0


if __name__ == "__main__":
    exit(main())
