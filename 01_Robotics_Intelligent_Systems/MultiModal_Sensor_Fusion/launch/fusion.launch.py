"""
ROS 2 Launch Configuration for Sensor Fusion Node

This launch file:
1. Loads perception fusion parameters from YAML config
2. Starts the perception_fusion_node for EKF-based sensor fusion
3. Launches static transform publisher for sensor-to-base-link transforms
4. Manages the complete sensor fusion pipeline for robot perception

Author: Silicon Integration Engineer
Date: 2025
Version: 1.0

Usage:
    ros2 launch perception_fusion fusion.launch.py
    
With custom parameters:
    ros2 launch perception_fusion fusion.launch.py \
        odom_frame:=world \
        lidar_range_std:=0.1
"""

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def launch_setup(context, *args, **kwargs):
    """
    Setup launch configuration dynamically.
    
    This function is called after launch arguments are processed,
    allowing for dynamic path resolution and conditional node launching.
    """
    
    # Get package share directory
    perception_fusion_dir = FindPackageShare("perception_fusion")
    
    # Resolve configuration file path
    config_file = PathJoinSubstitution(
        [perception_fusion_dir, "config", "fusion_params.yaml"]
    )
    
    # Get launch arguments
    odom_frame = LaunchConfiguration("odom_frame").perform(context)
    base_frame = LaunchConfiguration("base_frame").perform(context)
    lidar_range_std = LaunchConfiguration("lidar_range_std").perform(context)
    lidar_bearing_std = LaunchConfiguration("lidar_bearing_std").perform(context)
    radar_range_std = LaunchConfiguration("radar_range_std").perform(context)
    radar_bearing_std = LaunchConfiguration("radar_bearing_std").perform(context)
    radar_velocity_std = LaunchConfiguration("radar_velocity_std").perform(context)
    process_noise = LaunchConfiguration("process_noise").perform(context)
    
    # ========================================================================
    # Perception Fusion Node
    # ========================================================================
    # This node implements the Extended Kalman Filter for sensor fusion
    # It subscribes to:
    #   - /lidar_points (sensor_msgs/PointCloud2): 3D point cloud from LiDAR
    #   - /radar_data (sensor_msgs/Imu): Radar measurements (range, bearing, velocity)
    # 
    # It publishes:
    #   - /fused_odom (nav_msgs/Odometry): Estimated robot position and velocity
    #   - /occupancy_grid (nav_msgs/OccupancyGrid): 3D spatial occupancy map
    
    perception_fusion_node = Node(
        package="perception_fusion",
        executable="perception_fusion_node",
        name="perception_fusion_node",
        namespace="",
        output="screen",
        
        # Parameter overrides from launch arguments
        parameters=[
            {
                "odom_frame": odom_frame,
                "base_frame": base_frame,
                "lidar_range_std": float(lidar_range_std),
                "lidar_bearing_std": float(lidar_bearing_std),
                "radar_range_std": float(radar_range_std),
                "radar_bearing_std": float(radar_bearing_std),
                "radar_velocity_std": float(radar_velocity_std),
                "process_noise": float(process_noise),
            }
        ],
        
        # Remappings for sensor topics (optional, adjust as needed)
        remappings=[
            ("/lidar_points", "/lidar_points"),
            ("/radar_data", "/radar_data"),
            ("/fused_odom", "/fused_odom"),
            ("/occupancy_grid", "/occupancy_grid"),
        ],
    )
    
    # ========================================================================
    # Static Transform Publisher for Sensor Calibration
    # ========================================================================
    # These transforms define the mounting configuration of sensors relative
    # to the robot base frame. Adjust these values based on your hardware setup.
    #
    # Transform convention: parent_frame -> child_frame
    # Args: x y z yaw pitch roll parent_frame child_frame
    
    # LiDAR mounted 0.2m forward, 0.0m sideways, 0.5m up from base_link
    # No rotation relative to base_link (yaw, pitch, roll = 0, 0, 0)
    lidar_tf_node = Node(
        package="tf2_ros",
        executable="static_transform_publisher",
        name="lidar_tf_broadcaster",
        arguments=[
            "0.2",      # x offset
            "0.0",      # y offset
            "0.5",      # z offset (height above base)
            "0",        # yaw rotation (radians)
            "0",        # pitch rotation
            "0",        # roll rotation
            base_frame, # parent frame
            "lidar_frame",  # child frame
        ],
        output="log",
    )
    
    # Radar mounted 0.1m forward, 0.0m sideways, 0.3m up from base_link
    # Radar is typically horizontal (no pitch/roll)
    radar_tf_node = Node(
        package="tf2_ros",
        executable="static_transform_publisher",
        name="radar_tf_broadcaster",
        arguments=[
            "0.1",      # x offset
            "0.0",      # y offset
            "0.3",      # z offset
            "0",        # yaw rotation
            "0",        # pitch rotation
            "0",        # roll rotation
            base_frame, # parent frame
            "radar_frame",  # child frame
        ],
        output="log",
    )
    
    # Odometry frame to base_link transform
    # This is published by the perception fusion node for odometry estimates
    odom_tf_node = Node(
        package="tf2_ros",
        executable="static_transform_publisher",
        name="odom_tf_broadcaster",
        arguments=[
            "0",        # Initial x
            "0",        # Initial y
            "0",        # Initial z
            "0",        # yaw
            "0",        # pitch
            "0",        # roll
            odom_frame, # parent frame
            base_frame, # child frame
        ],
        output="log",
    )
    
    # ========================================================================
    # Launch Description
    # ========================================================================
    # Collects all nodes and launch actions to be executed
    
    return [
        perception_fusion_node,
        lidar_tf_node,
        radar_tf_node,
        odom_tf_node,
    ]


def generate_launch_description():
    """
    Generate ROS 2 launch description.
    
    This function defines all launch arguments and returns the complete
    launch description that orchestrates the sensor fusion pipeline.
    """
    
    return LaunchDescription(
        [
            # ====================================================================
            # Launch Arguments with Default Values
            # ====================================================================
            # These can be overridden from the command line
            
            # Frame names
            DeclareLaunchArgument(
                "odom_frame",
                default_value="odom",
                description="Global odometry reference frame",
            ),
            DeclareLaunchArgument(
                "base_frame",
                default_value="base_link",
                description="Robot base reference frame",
            ),
            
            # LiDAR sensor noise parameters
            DeclareLaunchArgument(
                "lidar_range_std",
                default_value="0.05",
                description="LiDAR range measurement standard deviation (meters)",
            ),
            DeclareLaunchArgument(
                "lidar_bearing_std",
                default_value="0.01",
                description="LiDAR bearing measurement standard deviation (radians)",
            ),
            
            # Radar sensor noise parameters
            DeclareLaunchArgument(
                "radar_range_std",
                default_value="0.1",
                description="Radar range measurement standard deviation (meters)",
            ),
            DeclareLaunchArgument(
                "radar_bearing_std",
                default_value="0.05",
                description="Radar bearing measurement standard deviation (radians)",
            ),
            DeclareLaunchArgument(
                "radar_velocity_std",
                default_value="0.1",
                description="Radar velocity measurement standard deviation (m/s)",
            ),
            
            # Process noise parameter
            DeclareLaunchArgument(
                "process_noise",
                default_value="0.15",
                description="Process noise scaling factor for EKF motion model",
            ),
            
            # ====================================================================
            # Dynamic Launch Setup
            # ====================================================================
            OpaqueFunction(function=launch_setup),
        ]
    )
