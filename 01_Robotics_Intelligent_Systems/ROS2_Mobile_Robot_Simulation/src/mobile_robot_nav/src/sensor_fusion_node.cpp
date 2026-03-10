#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/laser_scan.hpp>
#include <nav_msgs/msg/odometry.hpp>
#include <message_filters/subscriber.h>
#include <message_filters/synchronizer.h>
#include <message_filters/sync_policies/approximate_time.h>
#include <chrono>

class SensorFusionNode : public rclcpp::Node
{
public:
    SensorFusionNode()
        : Node("sensor_fusion_node"), sync_count_(0), odom_count_(0), scan_count_(0)
    {
        // Subscribers using message_filters for synchronization
        laser_sub_.subscribe(this, "/scan");
        odom_sub_.subscribe(this, "/odom");

        // Synchronizer with approximate time policy
        sync_ = std::make_shared<message_filters::Synchronizer<SyncPolicy>>(
            SyncPolicy(10), laser_sub_, odom_sub_);
        sync_->registerCallback(std::bind(&SensorFusionNode::syncCallback, this, 
            std::placeholders::_1, std::placeholders::_2));

        // Timer for 30Hz logging (33.33ms period)
        timer_ = this->create_wall_timer(
            std::chrono::milliseconds(33),
            std::bind(&SensorFusionNode::timerCallback, this));

        RCLCPP_INFO(this->get_logger(), "SensorFusionNode initialized. Monitoring /scan and /odom at 30Hz.");
    }

private:
    using SyncPolicy = message_filters::sync_policies::ApproximateTime<
        sensor_msgs::msg::LaserScan, nav_msgs::msg::Odometry>;

    message_filters::Subscriber<sensor_msgs::msg::LaserScan> laser_sub_;
    message_filters::Subscriber<nav_msgs::msg::Odometry> odom_sub_;
    std::shared_ptr<message_filters::Synchronizer<SyncPolicy>> sync_;
    rclcpp::TimerBase::SharedPtr timer_;

    size_t sync_count_;
    size_t odom_count_;
    size_t scan_count_;

    void syncCallback(const sensor_msgs::msg::LaserScan::ConstSharedPtr& scan_msg,
                      const nav_msgs::msg::Odometry::ConstSharedPtr& odom_msg)
    {
        ++sync_count_;
        RCLCPP_DEBUG(this->get_logger(), 
            "Synced: LaserScan [%lu rays] + Odometry [pose: (%.2f, %.2f)]",
            scan_msg->ranges.size(),
            odom_msg->pose.pose.position.x,
            odom_msg->pose.pose.position.y);
    }

    void timerCallback()
    {
        RCLCPP_INFO(this->get_logger(), 
            "Sync Status @ 30Hz | Synced Messages: %zu", sync_count_);
    }
};

int main(int argc, char * argv[])
{
    rclcpp::init(argc, argv);
    auto node = std::make_shared<SensorFusionNode>();
    rclcpp::spin(node);
    rclcpp::shutdown();
    return 0;
}