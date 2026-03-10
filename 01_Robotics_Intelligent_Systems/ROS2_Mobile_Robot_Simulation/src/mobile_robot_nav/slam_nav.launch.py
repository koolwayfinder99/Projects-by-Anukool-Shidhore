import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node


def generate_launch_description():
    # Get package directories
    mobile_robot_nav_pkg_dir = get_package_share_directory('mobile_robot_nav')
    slam_toolbox_pkg_dir = get_package_share_directory('slam_toolbox')
    
    # URDF file path
    urdf_file = os.path.join(mobile_robot_nav_pkg_dir, 'urdf', 'robot.urdf')
    
    # Check if URDF file exists
    if not os.path.exists(urdf_file):
        print(f"Warning: URDF file not found at {urdf_file}")
    
    # Include slam_toolbox online_async launch file
    slam_toolbox_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(slam_toolbox_pkg_dir, 'launch', 'online_async_launch.py')
        )
    )
    
    # robot_state_publisher node
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{'robot_description': open(urdf_file).read()}],
    )
    
    return LaunchDescription([
        slam_toolbox_launch,
        robot_state_publisher,
    ])
