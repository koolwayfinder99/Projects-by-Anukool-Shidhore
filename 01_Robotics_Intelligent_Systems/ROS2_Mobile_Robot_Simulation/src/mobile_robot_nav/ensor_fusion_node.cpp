#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/laser_scan.hpp>
#include <nav_msgs/msg/odometry.hpp>
#include <message_filters/subscriber.h>
#include <message_filters/synchronizer.h>
#include <message_filters/sync_policies/approximate_time.h>

class SensorFusionNode : public rclcpp::Node
{
public:
    SensorFusionNode()
        : Node("sensor_fusion_node")
    {
        // Subscribers
        laser_sub_.subscribe(this, "/scan");
        odom_sub_.subscribe(this, "/odom");

        // Synchronizer
        sync_ = std::make_shared<message_filters::Synchronizer<SyncPolicy>>(SyncPolicy(10), laser_sub_, odom_sub_);
        sync_->registerCallback(std::bind(&SensorFusionNode::syncCallback, this, std::placeholders::_1, std::placeholders::_2));
    }

private:
    using SyncPolicy = message_filters::sync_policies::ApproximateTime<sensor_msgs::msg::LaserScan, nav_msgs::msg::Odometry>;

    message_filters::Subscriber<sensor_msgs::msg::LaserScan> laser_sub_;
    message_filters::Subscriber<nav_msgs::msg::Odometry> odom_sub_;
    std::shared_ptr<message_filters::Synchronizer<SyncPolicy>> sync_;

    void syncCallback(const sensor_msgs::msg::LaserScan::ConstSharedPtr& scan_msg,
                      const nav_msgs::msg::Odometry::ConstSharedPtr& odom_msg)
    {
        RCLCPP_INFO(this->get_logger(), "Synced scan and odom messages at time: %f", rclcpp::Time(scan_msg->header.stamp).seconds());
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
