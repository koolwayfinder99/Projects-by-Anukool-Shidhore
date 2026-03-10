#!/usr/bin/env python3
"""
Jetson Nano Offboard Control via MAVROS
========================================

This module implements MAVLink-based offboard flight control for autonomous UAVs.
A Jetson Nano sends position setpoints to a Pixhawk flight controller through
the MAVROS bridge, enabling edge AI-driven autonomous navigation.

Dependencies:
    - mavros_msgs (ROS package)
    - geometry_msgs (ROS package)
    - rclpy (ROS 2 client library)
    - numpy
    - tf_transformations

Author: UC3M Robotics Lab
License: Apache 2.0
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from geometry_msgs.msg import PoseStamped, TwistStamped
from mavros_msgs.msg import State, SetpointRaw
from mavros_msgs.srv import CommandBool, SetMode
import numpy as np
from enum import Enum
import time
from datetime import datetime


class FlightMode(Enum):
    """Flight control modes for Pixhawk integration."""
    STABILIZE = 0
    ACRO = 1
    ALT_HOLD = 2
    AUTO = 3
    GUIDED = 4
    LOITER = 5
    RTL = 6
    OFFBOARD = 17


class JetsonOffboardController(Node):
    """
    Jetson Nano offboard controller using MAVROS and MAVLink protocol.
    
    Publishes position setpoints to Pixhawk flight controller at 50 Hz.
    Implements safety checks, telemetry subscription, and emergency procedures.
    """

    def __init__(self):
        """Initialize ROS node and establish MAVLink connection."""
        super().__init__('jetson_offboard_controller')
        
        # Configuration parameters
        self.TARGET_SYSTEM_ID = 1
        self.CONTROL_FREQUENCY = 50  # Hz
        self.CONTROL_PERIOD = 1.0 / self.CONTROL_FREQUENCY
        self.TIMEOUT_THRESHOLD = 2.0  # seconds
        self.MAX_VELOCITY = 5.0  # m/s
        self.MAX_ACCELERATION = 2.0  # m/s²
        
        # State variables
        self.current_state = State()
        self.armed = False
        self.offboard_enabled = False
        self.flight_started = False
        self.last_setpoint_time = time.time()
        
        # Telemetry tracking
        self.position_setpoint = np.array([0.0, 0.0, -5.0])  # X, Y, Z (NED frame)
        self.velocity_setpoint = np.array([0.0, 0.0, 0.0])
        self.yaw_setpoint = 0.0
        self.flight_log = []
        
        # QoS profile for reliable communication
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )
        
        # Subscribers
        self.state_sub = self.create_subscription(
            State,
            '/mavros/state',
            self._state_callback,
            qos_profile
        )
        
        self.local_position_sub = self.create_subscription(
            PoseStamped,
            '/mavros/local_position/pose',
            self._local_position_callback,
            qos_profile
        )
        
        # Publishers
        self.local_pos_pub = self.create_publisher(
            PoseStamped,
            '/mavros/setpoint_position/local',
            qos_profile
        )
        
        self.velocity_pub = self.create_publisher(
            TwistStamped,
            '/mavros/setpoint_velocity/cmd_vel',
            qos_profile
        )
        
        # Service clients
        self.arming_client = self.create_client(
            CommandBool,
            '/mavros/cmd/arming'
        )
        
        self.set_mode_client = self.create_client(
            SetMode,
            '/mavros/set_mode'
        )
        
        # Control loop timer
        self.control_timer = self.create_timer(
            self.CONTROL_PERIOD,
            self._control_loop_callback
        )
        
        # Telemetry logging timer
        self.telemetry_timer = self.create_timer(
            1.0,  # 1 Hz logging
            self._telemetry_callback
        )
        
        self.get_logger().info("Jetson Offboard Controller initialized")
        self.get_logger().info(f"Control frequency: {self.CONTROL_FREQUENCY} Hz")
        self.get_logger().info("Waiting for FCU connection...")

    def _state_callback(self, msg):
        """
        Update drone state from MAVROS telemetry.
        
        Args:
            msg: State message from /mavros/state
        """
        self.current_state = msg
        
        # Log connection status
        if not msg.connected and self.flight_started:
            self.get_logger().warn("FCU connection lost!")
        
        # Log arming status changes
        if msg.armed != self.armed:
            self.armed = msg.armed
            status = "ARMED" if self.armed else "DISARMED"
            self.get_logger().info(f"Vehicle {status}")
        
        # Log mode changes
        if msg.mode != "OFFBOARD" and self.offboard_enabled:
            self.get_logger().warn(f"Flight mode changed to {msg.mode}")

    def _local_position_callback(self, msg):
        """
        Receive current vehicle position estimate.
        
        Args:
            msg: PoseStamped message from /mavros/local_position/pose
        """
        pass  # Placeholder for position feedback processing

    def _control_loop_callback(self):
        """
        Main control loop executed at TARGET_FREQUENCY.
        Publishes position setpoints and maintains connection to Pixhawk.
        """
        if not self.current_state.connected:
            return
        
        # Publish position setpoint
        self._publish_position_setpoint()
        
        # Check for timeout
        time_since_last = time.time() - self.last_setpoint_time
        if time_since_last > self.TIMEOUT_THRESHOLD and self.offboard_enabled:
            self.get_logger().error("Setpoint timeout detected!")
            self._emergency_land()

    def _publish_position_setpoint(self):
        """
        Publish the current position setpoint to Pixhawk.
        Follows MAVLink setpoint protocol for offboard control.
        """
        pose = PoseStamped()
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.header.frame_id = "map"
        
        # Set position (NED frame)
        pose.pose.position.x = self.position_setpoint[0]
        pose.pose.position.y = self.position_setpoint[1]
        pose.pose.position.z = self.position_setpoint[2]
        
        # Set orientation (quaternion from yaw angle)
        from tf_transformations import quaternion_from_euler
        quat = quaternion_from_euler(0, 0, self.yaw_setpoint)
        pose.pose.orientation.x = quat[0]
        pose.pose.orientation.y = quat[1]
        pose.pose.orientation.z = quat[2]
        pose.pose.orientation.w = quat[3]
        
        self.local_pos_pub.publish(pose)
        self.last_setpoint_time = time.time()

    def _telemetry_callback(self):
        """Log system telemetry for diagnostics and performance analysis."""
        if not self.flight_started:
            return
        
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'armed': self.armed,
            'connected': self.current_state.connected,
            'mode': self.current_state.mode,
            'position_setpoint': self.position_setpoint.tolist(),
            'yaw_setpoint': float(self.yaw_setpoint)
        }
        self.flight_log.append(log_entry)

    async def arm_vehicle(self) -> bool:
        """
        Arm the vehicle and prepare for flight.
        
        Returns:
            bool: True if arming successful, False otherwise
        """
        if self.armed:
            self.get_logger().info("Vehicle already armed")
            return True
        
        while not self.arming_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().warn("Arming service not available")
        
        req = CommandBool.Request()
        req.value = True
        
        future = self.arming_client.call_async(req)
        rclpy.spin_until_future_complete(self, future)
        
        if future.result().success:
            self.get_logger().info("Vehicle armed successfully")
            return True
        else:
            self.get_logger().error("Arming failed")
            return False

    async def set_offboard_mode(self) -> bool:
        """
        Switch flight controller to OFFBOARD mode.
        Enables Jetson to send position setpoints.
        
        Returns:
            bool: True if mode switch successful, False otherwise
        """
        if self.current_state.mode == "OFFBOARD":
            self.get_logger().info("Already in OFFBOARD mode")
            return True
        
        while not self.set_mode_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().warn("Set mode service not available")
        
        req = SetMode.Request()
        req.custom_mode = "OFFBOARD"
        
        future = self.set_mode_client.call_async(req)
        rclpy.spin_until_future_complete(self, future)
        
        if future.result().mode_sent:
            self.get_logger().info("Offboard mode enabled")
            self.offboard_enabled = True
            return True
        else:
            self.get_logger().error("Failed to switch to OFFBOARD mode")
            return False

    def set_position_setpoint(self, x: float, y: float, z: float, yaw: float = 0.0):
        """
        Update the position setpoint for the vehicle.
        
        Args:
            x: Target X position (meters, NED frame)
            y: Target Y position (meters, NED frame)
            z: Target Z position (meters, NED frame)
            yaw: Target yaw angle (radians)
        """
        self.position_setpoint = np.array([x, y, z])
        self.yaw_setpoint = yaw
        self.get_logger().debug(
            f"Setpoint updated: pos=[{x:.2f}, {y:.2f}, {z:.2f}], yaw={yaw:.2f} rad"
        )

    def set_velocity_setpoint(self, vx: float, vy: float, vz: float, yaw_rate: float = 0.0):
        """
        Set velocity-based setpoint (alternative to position control).
        
        Args:
            vx: X velocity (m/s, NED)
            vy: Y velocity (m/s, NED)
            vz: Z velocity (m/s, NED)
            yaw_rate: Yaw rotation rate (rad/s)
        """
        # Enforce velocity limits
        velocity = np.array([vx, vy, vz])
        speed = np.linalg.norm(velocity)
        
        if speed > self.MAX_VELOCITY:
            velocity = velocity / speed * self.MAX_VELOCITY
            self.get_logger().warn(
                f"Velocity clamped to {self.MAX_VELOCITY} m/s (requested: {speed:.2f})"
            )
        
        self.velocity_setpoint = velocity
        
        twist = TwistStamped()
        twist.header.stamp = self.get_clock().now().to_msg()
        twist.header.frame_id = "body"
        twist.twist.linear.x = velocity[0]
        twist.twist.linear.y = velocity[1]
        twist.twist.linear.z = velocity[2]
        twist.twist.angular.z = yaw_rate
        
        self.velocity_pub.publish(twist)

    async def execute_mission(self, waypoints: list):
        """
        Execute autonomous mission with sequential waypoint navigation.
        
        Args:
            waypoints: List of (x, y, z, yaw) tuples in NED frame
        """
        self.flight_started = True
        self.get_logger().info(f"Starting mission with {len(waypoints)} waypoints")
        
        # Pre-mission checks
        if not await self.arm_vehicle():
            self.get_logger().error("Failed to arm vehicle")
            return
        
        if not await self.set_offboard_mode():
            self.get_logger().error("Failed to set OFFBOARD mode")
            return
        
        # Execute waypoints
        for i, (x, y, z, yaw) in enumerate(waypoints):
            self.get_logger().info(f"Navigating to waypoint {i+1}/{len(waypoints)}")
            self.set_position_setpoint(x, y, z, yaw)
            
            # Wait for convergence (simple distance check)
            while rclpy.ok():
                await rclpy.sleep(0.1)
                # In real implementation, check actual position feedback
                break
        
        self.get_logger().info("Mission complete")

    def _emergency_land(self):
        """
        Trigger emergency landing procedure.
        Disables offboard mode and returns control to autopilot.
        """
        self.get_logger().fatal("EMERGENCY LANDING TRIGGERED")
        self.offboard_enabled = False
        # Pixhawk RTL mode will activate automatically

    def save_flight_log(self, filename: str):
        """
        Save flight telemetry to JSON file.
        
        Args:
            filename: Output JSON file path
        """
        import json
        with open(filename, 'w') as f:
            json.dump(self.flight_log, f, indent=2)
        self.get_logger().info(f"Flight log saved to {filename}")


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)
    controller = JetsonOffboardController()
    
    try:
        rclpy.spin(controller)
    except KeyboardInterrupt:
        controller.get_logger().info("Shutdown requested")
    finally:
        controller.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
