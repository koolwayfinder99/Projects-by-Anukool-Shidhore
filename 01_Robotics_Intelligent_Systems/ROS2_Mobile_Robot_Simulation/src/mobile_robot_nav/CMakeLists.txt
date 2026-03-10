cmake_minimum_required(VERSION 3.8)
project(mobile_robot_nav)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(message_filters REQUIRED)
find_package(nav2_bringup REQUIRED)

# Add executable for sensor fusion node
add_executable(sensor_fusion_node src/sensor_fusion_node.cpp)
ament_target_dependencies(sensor_fusion_node 
  rclcpp 
  sensor_msgs 
  nav_msgs 
  message_filters
)

# Install executable
install(TARGETS
  sensor_fusion_node
  DESTINATION lib/${PROJECT_NAME}
)

# Install launch directory
install(DIRECTORY
  launch/
  DESTINATION share/${PROJECT_NAME}/launch
)

# Install URDF/Xacro files
install(DIRECTORY
  urdf/
  DESTINATION share/${PROJECT_NAME}/urdf
)

# Install configuration files
install(DIRECTORY
  config/
  DESTINATION share/${PROJECT_NAME}/config
)

ament_package()