import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node

def generate_launch_description():
    pkg_share = get_package_share_directory('mobile_robot_nav')
    
    urdf_file = os.path.join(pkg_share, 'urdf', 'diff_bot.urdf.xacro')
    slam_params_file = os.path.join(pkg_share, 'config', 'mapper_params_online_async.yaml')

    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        arguments=[urdf_file]
    )

    slam_toolbox = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([os.path.join(
            get_package_share_directory('slam_toolbox'), 'launch', 'online_async_launch.py'
        )]),
        launch_arguments={'slam_params_file': slam_params_file}.items()
    )

    sensor_fusion_node = Node(
        package='mobile_robot_nav',
        executable='sensor_fusion_node',
        name='sensor_fusion_node',
        output='screen'
    )

    return LaunchDescription([
        robot_state_publisher,
        slam_toolbox,
        sensor_fusion_node
    ])