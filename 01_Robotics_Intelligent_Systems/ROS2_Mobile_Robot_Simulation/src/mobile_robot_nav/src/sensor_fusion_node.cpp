#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/laser_scan.hpp>
#include <nav_msgs/msg/odometry.hpp>
#include <chrono>

using namespace std::chrono_literals;

class SensorFusionNode : public rclcpp::Node {
public:
    SensorFusionNode() : Node("sensor_fusion_node") {
        scan_sub_ = this->create_subscription<sensor_msgs::msg::LaserScan>(
            "/scan", 10, std::bind(&SensorFusionNode::scan_callback, this, std::placeholders::_1));
        
        odom_sub_ = this->create_subscription<nav_msgs::msg::Odometry>(
            "/odom", 10, std::bind(&SensorFusionNode::odom_callback, this, std::placeholders::_1));

        // 30Hz sync loop as defined in the project specs
        timer_ = this->create_wall_timer(
            33ms, std::bind(&SensorFusionNode::timer_callback, this));

        RCLCPP_INFO(this->get_logger(), "Sensor Fusion Node Initialized for SLAM.");
    }

private:
    void scan_callback(const sensor_msgs::msg::LaserScan::SharedPtr msg) {
        last_scan_time_ = msg->header.stamp;
    }

    void odom_callback(const nav_msgs::msg::Odometry::SharedPtr msg) {
        last_odom_time_ = msg->header.stamp;
    }

    void timer_callback() {
        RCLCPP_INFO(this->get_logger(), "Syncing Odometry and LiDAR streams at 30Hz...");
        // Additional fusion logic for mapping goes here
    }

    rclcpp::Subscription<sensor_msgs::msg::LaserScan>::SharedPtr scan_sub_;
    rclcpp::Subscription<nav_msgs::msg::Odometry>::SharedPtr odom_sub_;
    rclcpp::TimerBase::SharedPtr timer_;
    rclcpp::Time last_scan_time_;
    rclcpp::Time last_odom_time_;
};

int main(int argc, char **argv) {
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<SensorFusionNode>());
    rclcpp::shutdown();
    return 0;
}