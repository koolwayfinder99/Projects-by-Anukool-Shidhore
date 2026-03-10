cmake_minimum_required(VERSION 3.8)
project(perception_fusion)

# Set C++ standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find ROS2 packages
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(tf2 REQUIRED)
find_package(tf2_ros REQUIRED)
find_package(Eigen3 REQUIRED)
find_package(PCL REQUIRED)
find_package(pcl_ros REQUIRED)

# Include directories
include_directories(
    include
    ${EIGEN3_INCLUDE_DIR}
    ${PCL_INCLUDE_DIRS}
)

# Define dependencies list for reuse
set(DEPENDENCIES
    rclcpp
    sensor_msgs
    nav_msgs
    geometry_msgs
    std_msgs
    tf2
    tf2_ros
    pcl_ros
)

# Build perception fusion node
add_executable(perception_fusion_node
    src/perception_fusion/fusion_node.cpp
)

# Link dependencies
ament_target_dependencies(perception_fusion_node
    ${DEPENDENCIES}
)

# Link PCL and Eigen
target_link_libraries(perception_fusion_node
    ${PCL_LIBRARIES}
    Eigen3::Eigen
)

# Install executable
install(TARGETS perception_fusion_node
    DESTINATION lib/${PROJECT_NAME}
)

# Install launch files
install(DIRECTORY launch/
    DESTINATION share/${PROJECT_NAME}/launch
)

# Install config files
install(DIRECTORY config/
    DESTINATION share/${PROJECT_NAME}/config
)

# Testing setup (optional)
if(BUILD_TESTING)
    find_package(ament_cmake_gtest REQUIRED)
    # Add tests here
endif()

# Export information for dependent packages
ament_package()
