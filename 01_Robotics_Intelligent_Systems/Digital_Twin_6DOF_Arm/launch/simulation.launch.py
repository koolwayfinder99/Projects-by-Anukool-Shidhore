#!/usr/bin/env python3
"""
Gazebo Simulation Launch Configuration for 6-DOF Robotic Arm Digital Twin

This launch file orchestrates the simulation environment setup including:
- Starting Gazebo simulator with an empty world
- Loading the robot model (arm_6dof) in Gazebo
- Launching joint_state_publisher for joint state broadcasting
- Starting ROS2 control manager for joint actuation
- Initializing sensor fusion node for predictive maintenance

Author: RWU Master's Project
Date: 2024
"""

from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, ExecuteProcess, RegisterEventHandler
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.event_handlers import OnProcessExit
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
import os


def generate_launch_description():
    """
    Generate the launch description for the 6-DOF arm digital twin simulation.
    
    Returns:
        LaunchDescription: Complete launch configuration
    """
    
    # Get package directories
    pkg_share = FindPackageShare('arm_6dof_description').perform([])
    pkg_gazebo = FindPackageShare('gazebo_ros').perform([])
    
    # Configuration variables
    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    world_file = LaunchConfiguration('world', default='empty.world')
    
    # Gazebo startup arguments
    launch_gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare('gazebo_ros'),
                'launch',
                'gazebo.launch.py'
            ])
        ),
        launch_arguments={
            'world': world_file,
            'verbose': 'false',
            'pause': 'false',
        }.items(),
    )
    
    # Get URDF file
    urdf_file = PathJoinSubstitution([
        FindPackageShare('arm_6dof_description'),
        'urdf',
        'arm_6dof.urdf.xacro'
    ])
    
    # Process URDF with xacro
    process_urdf = ExecuteProcess(
        cmd=['xacro', urdf_file],
        output='screen',
    )
    
    # Spawn robot in Gazebo
    spawn_robot = Node(
        package='gazebo_ros',
        executable='spawn_entity.py',
        arguments=[
            '-entity', 'arm_6dof',
            '-topic', '/robot_description',
            '-x', '0.0',
            '-y', '0.0',
            '-z', '0.0',
        ],
        output='screen',
    )
    
    # Joint state publisher (publishes joint states from simulation)
    joint_state_publisher = Node(
        package='joint_state_publisher',
        executable='joint_state_publisher',
        name='joint_state_publisher',
        arguments=['--use_sim_time'],
        output='screen',
    )
    
    # Robot state publisher (broadcasts transforms)
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        arguments=['--use_sim_time'],
        parameters=[{
            'robot_description': urdf_file,
            'use_sim_time': use_sim_time,
        }],
        output='screen',
    )
    
    # Joint trajectory controller (for arm control)
    controller_manager = Node(
        package='ros2_control',
        executable='ros2_control_node',
        parameters=[{
            'robot_description': urdf_file,
            'use_sim_time': use_sim_time,
        }],
        output='screen',
    )
    
    # Predictive maintenance monitoring node
    predictive_maintenance = Node(
        package='arm_6dof_ml',
        executable='predictive_maintenance.py',
        name='predictive_maintenance_monitor',
        arguments=['--use_sim_time'],
        output='screen',
    )
    
    # RViz visualization (optional but recommended for monitoring)
    rviz_config_file = PathJoinSubstitution([
        FindPackageShare('arm_6dof_description'),
        'rviz',
        'arm_visualization.rviz'
    ])
    
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        arguments=['-d', rviz_config_file],
        output='screen',
    )
    
    return LaunchDescription([
        # Set use_sim_time for all nodes
        launch_gazebo,
        
        # Delayed spawn (wait for Gazebo to be ready)
        RegisterEventHandler(
            event_handler=OnProcessExit(
                target_action=launch_gazebo,
                on_exit=[spawn_robot],
            )
        ),
        
        # State publishers
        joint_state_publisher,
        robot_state_publisher,
        
        # Control and monitoring
        controller_manager,
        predictive_maintenance,
        
        # Visualization
        rviz_node,
    ])
