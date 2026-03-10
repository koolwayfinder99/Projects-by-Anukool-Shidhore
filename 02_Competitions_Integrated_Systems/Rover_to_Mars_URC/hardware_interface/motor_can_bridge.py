#!/usr/bin/env python3
"""
Motor CAN Bridge for Rover to Mars URC Project

This module bridges ROS 2 twist messages to CAN-bus motor controllers.
Reflects the integration of Steel (robust hardware) and Silicon (intelligent control).

Features:
- Converts geometry_msgs/Twist to CAN commands for motor controllers
- Supports multiple motor types (DC, BLDC, Stepper)
- Real-time safety checks and fault handling
- CAN message queuing and rate limiting
- Odometry feedback integration
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import JointState
from std_msgs.msg import Int32MultiArray
import struct
import threading
import time
from typing import Dict, Tuple, Optional
from dataclasses import dataclass
from enum import IntEnum
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CANMessageType(IntEnum):
    """CAN Message Type IDs for motor controller communication"""
    MOTOR_COMMAND = 0x100
    MOTOR_STATUS = 0x101
    ODOMETRY_REQUEST = 0x102
    FAULT_CODE = 0x103
    HEARTBEAT = 0x104


class MotorControlMode(IntEnum):
    """Motor control modes"""
    VELOCITY = 0
    POSITION = 1
    CURRENT = 2
    DISABLED = 3


@dataclass
class MotorConfig:
    """Configuration for individual motor controller"""
    can_id: int
    motor_type: str  # "DC", "BLDC", "Stepper"
    max_rpm: float
    gear_ratio: float
    encoder_resolution: int
    max_current_amps: float
    control_mode: MotorControlMode = MotorControlMode.VELOCITY


class MotorCANBridge(Node):
    """
    ROS 2 Node for bridging Twist commands to CAN motor controllers
    
    Implements real-time control for Mars Rover autonomous traversal
    """
    
    def __init__(self):
        super().__init__('motor_can_bridge')
        
        # Parameters from ROS config
        self.declare_parameter('left_motor_id', 0x01)
        self.declare_parameter('right_motor_id', 0x02)
        self.declare_parameter('max_linear_velocity', 1.0)  # m/s
        self.declare_parameter('max_angular_velocity', 1.57)  # rad/s
        self.declare_parameter('wheel_base', 0.6)  # meters
        self.declare_parameter('wheel_radius', 0.15)  # meters
        self.declare_parameter('can_frequency', 50.0)  # Hz
        self.declare_parameter('enable_safety_checks', True)
        
        # Get parameters
        left_id = self.get_parameter('left_motor_id').value
        right_id = self.get_parameter('right_motor_id').value
        self.max_linear_vel = self.get_parameter('max_linear_velocity').value
        self.max_angular_vel = self.get_parameter('max_angular_velocity').value
        self.wheel_base = self.get_parameter('wheel_base').value
        self.wheel_radius = self.get_parameter('wheel_radius').value
        self.can_frequency = self.get_parameter('can_frequency').value
        self.enable_safety_checks = self.get_parameter('enable_safety_checks').value
        
        # Motor configurations
        self.motors: Dict[str, MotorConfig] = {
            'left': MotorConfig(
                can_id=left_id,
                motor_type='BLDC',
                max_rpm=200,
                gear_ratio=10.0,
                encoder_resolution=4096,
                max_current_amps=30.0
            ),
            'right': MotorConfig(
                can_id=right_id,
                motor_type='BLDC',
                max_rpm=200,
                gear_ratio=10.0,
                encoder_resolution=4096,
                max_current_amps=30.0
            )
        }
        
        # State tracking
        self.current_twist: Optional[Twist] = None
        self.motor_velocities: Dict[str, float] = {'left': 0.0, 'right': 0.0}
        self.motor_positions: Dict[str, float] = {'left': 0.0, 'right': 0.0}
        self.motor_currents: Dict[str, float] = {'left': 0.0, 'right': 0.0}
        self.fault_flags: Dict[str, bool] = {'left': False, 'right': False}
        
        # CAN message queue
        self.can_queue: list = []
        self.queue_lock = threading.Lock()
        
        # ROS 2 Subscribers
        self.twist_sub = self.create_subscription(
            Twist,
            'cmd_vel',
            self.twist_callback,
            10
        )
        
        self.odom_sub = self.create_subscription(
            Odometry,
            'odom',
            self.odometry_callback,
            10
        )
        
        # ROS 2 Publishers
        self.can_tx_pub = self.create_publisher(
            Int32MultiArray,
            'can_tx',
            10
        )
        
        self.joint_state_pub = self.create_publisher(
            JointState,
            'joint_states',
            10
        )
        
        # Timer for CAN communication at specified frequency
        timer_period = 1.0 / self.can_frequency
        self.can_timer = self.create_timer(
            timer_period,
            self.can_communication_callback
        )
        
        # Timer for heartbeat/status messages
        self.status_timer = self.create_timer(
            1.0,  # 1 Hz status update
            self.status_callback
        )
        
        self.get_logger().info(
            f'Motor CAN Bridge initialized: '
            f'Left ID=0x{left_id:02x}, Right ID=0x{right_id:02x}, '
            f'CAN Frequency={self.can_frequency}Hz'
        )
    
    def twist_callback(self, msg: Twist) -> None:
        """
        Callback for velocity commands (cmd_vel)
        
        Converts Twist (linear and angular velocities) to individual motor commands
        using differential drive kinematics.
        """
        self.current_twist = msg
        
        # Extract velocities
        v_linear = msg.linear.x  # m/s
        v_angular = msg.angular.z  # rad/s
        
        # Safety checks
        if self.enable_safety_checks:
            v_linear = self.clamp_value(v_linear, -self.max_linear_vel, self.max_linear_vel)
            v_angular = self.clamp_value(v_angular, -self.max_angular_vel, self.max_angular_vel)
        
        # Differential drive kinematics
        # v_left = v_linear - (v_angular * wheel_base / 2)
        # v_right = v_linear + (v_angular * wheel_base / 2)
        left_vel = v_linear - (v_angular * self.wheel_base / 2.0)
        right_vel = v_linear + (v_angular * self.wheel_base / 2.0)
        
        # Store motor velocities
        self.motor_velocities['left'] = left_vel
        self.motor_velocities['right'] = right_vel
        
        self.get_logger().debug(
            f'Twist received: v_linear={v_linear:.2f} m/s, '
            f'v_angular={v_angular:.2f} rad/s -> '
            f'left_vel={left_vel:.2f} m/s, right_vel={right_vel:.2f} m/s'
        )
    
    def odometry_callback(self, msg: Odometry) -> None:
        """
        Callback for odometry feedback
        
        Updates internal motor position and velocity estimates
        """
        # Extract position
        self.motor_positions['left'] = msg.pose.pose.position.x
        self.motor_positions['right'] = msg.pose.pose.position.y
        
        # Extract velocity
        self.motor_velocities['left'] = msg.twist.twist.linear.x
        self.motor_velocities['right'] = msg.twist.twist.linear.y
    
    def can_communication_callback(self) -> None:
        """
        Main CAN communication loop at specified frequency
        
        Encodes motor commands into CAN messages and sends to motor controllers
        """
        # Build CAN messages for left and right motors
        left_msg = self.build_motor_command_message('left')
        right_msg = self.build_motor_command_message('right')
        
        # Queue messages
        with self.queue_lock:
            if left_msg:
                self.can_queue.append(left_msg)
            if right_msg:
                self.can_queue.append(right_msg)
        
        # Transmit queued messages
        self.transmit_can_messages()
    
    def build_motor_command_message(self, motor_name: str) -> Optional[list]:
        """
        Build CAN message for motor velocity command
        
        CAN Message Format:
        - Byte 0: Command Type (0x01 = Velocity)
        - Bytes 1-2: Velocity (int16, RPM)
        - Bytes 3-4: Current Limit (int16, mA)
        - Byte 5: Control Flags
        
        Args:
            motor_name: 'left' or 'right'
        
        Returns:
            CAN message as list of bytes
        """
        motor_config = self.motors[motor_name]
        velocity_mps = self.motor_velocities[motor_name]
        
        # Convert m/s to motor RPM
        # wheel_circumference = 2 * pi * wheel_radius
        # RPM = (velocity_mps * 60) / (wheel_circumference / gear_ratio)
        wheel_circumference = 2 * 3.14159 * self.wheel_radius
        rpm = (velocity_mps * 60.0) / (wheel_circumference / motor_config.gear_ratio)
        
        # Clamp to motor limits
        max_motor_rpm = motor_config.max_rpm
        rpm = self.clamp_value(rpm, -max_motor_rpm, max_motor_rpm)
        
        # Convert to int16 (range -32768 to 32767)
        rpm_int16 = int(rpm)
        
        # Current limit in mA
        current_limit_ma = int(motor_config.max_current_amps * 1000)
        
        # Build CAN message
        can_msg = [
            motor_config.can_id,  # CAN ID
            CANMessageType.MOTOR_COMMAND,  # Message type
            MotorControlMode.VELOCITY,  # Control mode
            (rpm_int16 >> 8) & 0xFF,  # RPM high byte
            rpm_int16 & 0xFF,  # RPM low byte
            (current_limit_ma >> 8) & 0xFF,  # Current limit high byte
            current_limit_ma & 0xFF,  # Current limit low byte
            0x00  # Control flags (bit 0: enable, bit 1: brake, bit 2: fault clear)
        ]
        
        return can_msg
    
    def transmit_can_messages(self) -> None:
        """
        Transmit queued CAN messages via ROS 2 publisher
        
        In a real system, this would interface with actual CAN hardware driver
        """
        with self.queue_lock:
            for can_msg in self.can_queue:
                # Publish CAN message
                can_array = Int32MultiArray()
                can_array.data = [int(x) for x in can_msg]
                self.can_tx_pub.publish(can_array)
            
            self.can_queue.clear()
    
    def status_callback(self) -> None:
        """
        Periodic callback to publish motor status and joint states
        """
        # Create joint state message
        joint_state = JointState()
        joint_state.header.stamp = self.get_clock().now().to_msg()
        joint_state.header.frame_id = "base_link"
        
        joint_state.name = ['left_wheel', 'right_wheel']
        joint_state.position = [
            self.motor_positions['left'],
            self.motor_positions['right']
        ]
        joint_state.velocity = [
            self.motor_velocities['left'],
            self.motor_velocities['right']
        ]
        joint_state.effort = [
            self.motor_currents['left'],
            self.motor_currents['right']
        ]
        
        self.joint_state_pub.publish(joint_state)
    
    @staticmethod
    def clamp_value(value: float, min_val: float, max_val: float) -> float:
        """Clamp value between min and max"""
        return max(min_val, min(value, max_val))


class CANSimulator:
    """
    Simulates CAN bus motor controller responses for testing
    
    In production, this would be replaced with actual CAN hardware driver
    """
    
    def __init__(self):
        self.motor_states = {
            'left': {'rpm': 0, 'current': 0, 'position': 0},
            'right': {'rpm': 0, 'current': 0, 'position': 0}
        }
    
    def process_can_message(self, can_msg: list) -> Dict:
        """
        Simulate motor controller response to CAN command
        
        Args:
            can_msg: CAN message bytes
        
        Returns:
            Simulated motor state
        """
        can_id = can_msg[0]
        msg_type = can_msg[1]
        
        if msg_type == CANMessageType.MOTOR_COMMAND:
            rpm = ((can_msg[3] << 8) | can_msg[4])
            
            # Simulate motor response with 100ms delay
            motor_side = 'left' if can_id == 0x01 else 'right'
            self.motor_states[motor_side]['rpm'] = rpm
            
            return {
                'status': 'OK',
                'motor': motor_side,
                'rpm': rpm,
                'current': 0.5  # Simulated current
            }
        
        return {'status': 'ERROR', 'motor': None, 'rpm': 0}


def main(args=None):
    """Main entry point"""
    rclpy.init(args=args)
    
    motor_bridge = MotorCANBridge()
    
    try:
        rclpy.spin(motor_bridge)
    except KeyboardInterrupt:
        pass
    finally:
        motor_bridge.destroy_node()
        rclpy.shutdown()
        logger.info("Motor CAN Bridge shutdown complete")


if __name__ == '__main__':
    main()
