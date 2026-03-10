/**
 * @file fusion_node.cpp
 * @brief Extended Kalman Filter (EKF) based Sensor Fusion Node
 * 
 * This node implements an EKF to fuse LiDAR point cloud data and Radar scan data
 * for robust velocity estimation and 3D spatial mapping. The fusion process:
 * 1. Predicts robot state (position, velocity) using motion model
 * 2. Updates predictions with LiDAR observations (3D point measurements)
 * 3. Updates with Radar observations (range, azimuth, velocity)
 * 4. Publishes fused state and generates 3D spatial occupancy maps
 * 
 * @author Silicon Integration Engineer
 * @date 2025
 * @version 1.0
 * 
 * Dependencies:
 * - sensor_msgs: for PointCloud2 and RadarScan data
 * - nav_msgs: for Odometry and OccupancyGrid
 * - tf2: for coordinate transformations
 * - pcl_ros: for Point Cloud Library integration
 */

#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/point_cloud2.hpp>
#include <sensor_msgs/msg/imu.hpp>
#include <nav_msgs/msg/odometry.hpp>
#include <nav_msgs/msg/occupancy_grid.hpp>
#include <geometry_msgs/msg/transform_stamped.hpp>
#include <tf2_ros/static_transform_broadcaster.h>

#include <pcl/point_cloud.h>
#include <pcl/point_types.h>
#include <pcl_conversions/pcl_conversions.h>

#include <Eigen/Dense>
#include <queue>
#include <cmath>
#include <memory>

/**
 * @class ExtendedKalmanFilter
 * @brief Extended Kalman Filter implementation for sensor fusion
 * 
 * State vector: [x, y, vx, vy] (position and velocity in 2D, extensible to 3D)
 * Process model: Constant velocity model with process noise
 * Measurement models: LiDAR (range-bearing) and Radar (range-azimuth-velocity)
 */
class ExtendedKalmanFilter {
private:
    // State and Covariance matrices
    Eigen::Vector4d state_;          ///< State vector [x, y, vx, vy]
    Eigen::Matrix4d P_;              ///< State covariance matrix
    Eigen::Matrix4d Q_;              ///< Process noise covariance
    
    // Sensor variances (loaded from config)
    double lidar_range_std_;         ///< LiDAR range measurement std deviation
    double lidar_bearing_std_;       ///< LiDAR bearing measurement std deviation
    double radar_range_std_;         ///< Radar range measurement std deviation
    double radar_bearing_std_;       ///< Radar bearing measurement std deviation
    double radar_velocity_std_;      ///< Radar velocity measurement std deviation
    
    double dt_;                      ///< Time step for discrete integration
    double process_noise_scale_;     ///< Scale factor for process noise

public:
    /**
     * @brief Constructor for EKF
     * @param dt Time step duration
     * @param process_noise_scale Process noise scaling factor
     */
    ExtendedKalmanFilter(double dt = 0.1, double process_noise_scale = 0.1) 
        : dt_(dt), process_noise_scale_(process_noise_scale) {
        
        // Initialize state to zero (origin, stationary)
        state_ = Eigen::Vector4d::Zero();
        
        // Initialize state covariance - high initial uncertainty
        P_ = Eigen::Matrix4d::Identity() * 10.0;
        
        // Initialize process noise covariance
        // Q models uncertainty in constant velocity model
        Q_ = Eigen::Matrix4d::Zero();
        double q = process_noise_scale_ * process_noise_scale_;
        Q_(0, 0) = q * dt_ * dt_ / 4.0;  // x acceleration uncertainty
        Q_(0, 2) = q * dt_ / 2.0;
        Q_(1, 1) = q * dt_ * dt_ / 4.0;  // y acceleration uncertainty
        Q_(1, 3) = q * dt_ / 2.0;
        Q_(2, 0) = q * dt_ / 2.0;
        Q_(2, 2) = q * dt_;              // velocity uncertainty
        Q_(3, 1) = q * dt_ / 2.0;
        Q_(3, 3) = q * dt_;
        
        // Sensor noise defaults (will be updated from config)
        lidar_range_std_ = 0.05;
        lidar_bearing_std_ = 0.01;
        radar_range_std_ = 0.1;
        radar_bearing_std_ = 0.05;
        radar_velocity_std_ = 0.1;
    }
    
    /**
     * @brief Set sensor noise parameters
     */
    void setSensorNoise(double lr, double lb, double rr, double rb, double rv) {
        lidar_range_std_ = lr;
        lidar_bearing_std_ = lb;
        radar_range_std_ = rr;
        radar_bearing_std_ = rb;
        radar_velocity_std_ = rv;
    }
    
    /**
     * @brief Prediction step of EKF
     * 
     * Predicts state forward using constant velocity model:
     * x_new = x + vx * dt
     * y_new = y + vy * dt
     * vx_new = vx (constant velocity assumption)
     * vy_new = vy (constant velocity assumption)
     */
    void predict() {
        // State transition matrix for constant velocity model
        Eigen::Matrix4d F = Eigen::Matrix4d::Identity();
        F(0, 2) = dt_;  // x += vx * dt
        F(1, 3) = dt_;  // y += vy * dt
        
        // Predict state: x_pred = F * x
        state_ = F * state_;
        
        // Update covariance: P_pred = F * P * F^T + Q
        P_ = F * P_ * F.transpose() + Q_;
    }
    
    /**
     * @brief Update step with LiDAR measurement (3D point)
     * 
     * Measurement model: Observes position (x, y) with Cartesian coordinates
     * @param point_x X-coordinate of detected point
     * @param point_y Y-coordinate of detected point
     */
    void updateLiDAR(double point_x, double point_y) {
        // Measurement vector: [x, y]
        Eigen::Vector2d z;
        z(0) = point_x;
        z(1) = point_y;
        
        // Observation matrix: We measure position directly
        Eigen::MatrixXd H = Eigen::MatrixXd::Zero(2, 4);
        H(0, 0) = 1.0;  // Observe x
        H(1, 1) = 1.0;  // Observe y
        
        // Measurement noise covariance
        Eigen::Matrix2d R = Eigen::Matrix2d::Zero();
        R(0, 0) = lidar_range_std_ * lidar_range_std_;
        R(1, 1) = lidar_range_std_ * lidar_range_std_;
        
        // Innovation (measurement residual): y = z - H*x
        Eigen::Vector2d y = z - H * state_;
        
        // Innovation covariance: S = H*P*H^T + R
        Eigen::Matrix2d S = H * P_ * H.transpose() + R;
        
        // Kalman gain: K = P*H^T*S^-1
        Eigen::MatrixXd K = P_ * H.transpose() * S.inverse();
        
        // State update: x = x + K*y
        state_ += K * y;
        
        // Covariance update: P = (I - K*H)*P
        Eigen::Matrix4d I = Eigen::Matrix4d::Identity();
        P_ = (I - K * H) * P_;
    }
    
    /**
     * @brief Update step with Radar measurement (range, azimuth, velocity)
     * 
     * Radar provides polar coordinates and radial velocity.
     * Measurement model: 
     * - range: sqrt(x^2 + y^2)
     * - bearing: atan2(y, x)
     * - velocity: (vx*cos(bearing) + vy*sin(bearing))
     * 
     * @param range Distance to target
     * @param bearing Azimuth angle in radians
     * @param radial_velocity Velocity component along radar line of sight
     */
    void updateRadar(double range, double bearing, double radial_velocity) {
        // Measurement vector: [range, bearing, velocity]
        Eigen::Vector3d z;
        z(0) = range;
        z(1) = bearing;
        z(2) = radial_velocity;
        
        // Expected measurement from current state
        double x = state_(0);
        double y = state_(1);
        double vx = state_(2);
        double vy = state_(3);
        
        double rho = std::sqrt(x*x + y*y);           // Predicted range
        double phi = std::atan2(y, x);                // Predicted bearing
        double rho_dot = (x*vx + y*vy) / (rho + 1e-6); // Predicted velocity
        
        Eigen::Vector3d z_pred;
        z_pred(0) = rho;
        z_pred(1) = phi;
        z_pred(2) = rho_dot;
        
        // Jacobian of measurement function H
        Eigen::Matrix<double, 3, 4> H = Eigen::Matrix<double, 3, 4>::Zero();
        
        // Derivative of range w.r.t. state
        H(0, 0) = x / (rho + 1e-6);
        H(0, 1) = y / (rho + 1e-6);
        
        // Derivative of bearing w.r.t. state
        H(1, 0) = -y / (rho*rho + 1e-6);
        H(1, 1) = x / (rho*rho + 1e-6);
        
        // Derivative of radial velocity w.r.t. state
        H(2, 0) = vx / (rho + 1e-6) - (x*x*vx + x*y*vy) / (rho*rho*rho + 1e-6);
        H(2, 1) = vy / (rho + 1e-6) - (x*y*vx + y*y*vy) / (rho*rho*rho + 1e-6);
        H(2, 2) = x / (rho + 1e-6);
        H(2, 3) = y / (rho + 1e-6);
        
        // Measurement noise covariance
        Eigen::Matrix3d R = Eigen::Matrix3d::Zero();
        R(0, 0) = radar_range_std_ * radar_range_std_;
        R(1, 1) = radar_bearing_std_ * radar_bearing_std_;
        R(2, 2) = radar_velocity_std_ * radar_velocity_std_;
        
        // Innovation
        Eigen::Vector3d y = z - z_pred;
        
        // Normalize bearing difference to [-pi, pi]
        while (y(1) > M_PI) y(1) -= 2 * M_PI;
        while (y(1) < -M_PI) y(1) += 2 * M_PI;
        
        // Innovation covariance
        Eigen::Matrix3d S = H * P_ * H.transpose() + R;
        
        // Kalman gain
        Eigen::Matrix<double, 4, 3> K = P_ * H.transpose() * S.inverse();
        
        // State update
        state_ += K * y;
        
        // Covariance update
        Eigen::Matrix4d I = Eigen::Matrix4d::Identity();
        P_ = (I - K * H) * P_;
    }
    
    /**
     * @brief Get current state estimate
     */
    Eigen::Vector4d getState() const { return state_; }
    
    /**
     * @brief Get state covariance
     */
    Eigen::Matrix4d getCovariance() const { return P_; }
    
    /**
     * @brief Reset filter state
     */
    void reset() {
        state_ = Eigen::Vector4d::Zero();
        P_ = Eigen::Matrix4d::Identity() * 10.0;
    }
};

/**
 * @class SensorFusionNode
 * @brief ROS2 node for multi-sensor fusion using EKF
 */
class SensorFusionNode : public rclcpp::Node {
private:
    std::unique_ptr<ExtendedKalmanFilter> ekf_;
    std::shared_ptr<tf2_ros::StaticTransformBroadcaster> static_tf_broadcaster_;
    
    // ROS publishers and subscribers
    rclcpp::Subscription<sensor_msgs::msg::PointCloud2>::SharedPtr lidar_sub_;
    rclcpp::Subscription<sensor_msgs::msg::Imu>::SharedPtr radar_sub_;
    rclcpp::Publisher<nav_msgs::msg::Odometry>::SharedPtr odom_pub_;
    rclcpp::Publisher<nav_msgs::msg::OccupancyGrid>::SharedPtr occupancy_pub_;
    
    // Point cloud buffer for occupancy grid generation
    pcl::PointCloud<pcl::PointXYZ> merged_cloud_;
    std::mutex cloud_mutex_;
    
    // Configuration parameters
    double lidar_range_std_;
    double lidar_bearing_std_;
    double radar_range_std_;
    double radar_bearing_std_;
    double radar_velocity_std_;
    double process_noise_;
    std::string base_frame_;
    std::string odom_frame_;
    
public:
    SensorFusionNode() : rclcpp::Node("perception_fusion_node") {
        RCLCPP_INFO(this->get_logger(), "Initializing Sensor Fusion Node...");
        
        // Declare and get parameters
        this->declare_parameter("lidar_range_std", 0.05);
        this->declare_parameter("lidar_bearing_std", 0.01);
        this->declare_parameter("radar_range_std", 0.1);
        this->declare_parameter("radar_bearing_std", 0.05);
        this->declare_parameter("radar_velocity_std", 0.1);
        this->declare_parameter("process_noise", 0.1);
        this->declare_parameter("base_frame", "base_link");
        this->declare_parameter("odom_frame", "odom");
        
        lidar_range_std_ = this->get_parameter("lidar_range_std").as_double();
        lidar_bearing_std_ = this->get_parameter("lidar_bearing_std").as_double();
        radar_range_std_ = this->get_parameter("radar_range_std").as_double();
        radar_bearing_std_ = this->get_parameter("radar_bearing_std").as_double();
        radar_velocity_std_ = this->get_parameter("radar_velocity_std").as_double();
        process_noise_ = this->get_parameter("process_noise").as_double();
        base_frame_ = this->get_parameter("base_frame").as_string();
        odom_frame_ = this->get_parameter("odom_frame").as_string();
        
        // Initialize EKF
        ekf_ = std::make_unique<ExtendedKalmanFilter>(0.1, process_noise_);
        ekf_->setSensorNoise(lidar_range_std_, lidar_bearing_std_,
                             radar_range_std_, radar_bearing_std_, 
                             radar_velocity_std_);
        
        // Initialize static transform broadcaster
        static_tf_broadcaster_ = std::make_shared<tf2_ros::StaticTransformBroadcaster>(this);
        publishStaticTransforms();
        
        // Create subscribers
        lidar_sub_ = this->create_subscription<sensor_msgs::msg::PointCloud2>(
            "/lidar_points", rclcpp::SensorDataQoS(),
            std::bind(&SensorFusionNode::lidarCallback, this, std::placeholders::_1));
        
        radar_sub_ = this->create_subscription<sensor_msgs::msg::Imu>(
            "/radar_data", rclcpp::SensorDataQoS(),
            std::bind(&SensorFusionNode::radarCallback, this, std::placeholders::_1));
        
        // Create publishers
        odom_pub_ = this->create_publisher<nav_msgs::msg::Odometry>("/fused_odom", 10);
        occupancy_pub_ = this->create_publisher<nav_msgs::msg::OccupancyGrid>("/occupancy_grid", 10);
        
        RCLCPP_INFO(this->get_logger(), "Sensor Fusion Node initialized successfully");
    }
    
    /**
     * @brief Publish static transforms between frames
     */
    void publishStaticTransforms() {
        // Transform from odom to base_link
        geometry_msgs::msg::TransformStamped tf_odom_to_base;
        tf_odom_to_base.header.stamp = this->now();
        tf_odom_to_base.header.frame_id = odom_frame_;
        tf_odom_to_base.child_frame_id = base_frame_;
        tf_odom_to_base.transform.translation.x = 0.0;
        tf_odom_to_base.transform.translation.y = 0.0;
        tf_odom_to_base.transform.translation.z = 0.0;
        tf_odom_to_base.transform.rotation.w = 1.0;
        
        static_tf_broadcaster_->sendTransform(tf_odom_to_base);
    }
    
    /**
     * @brief LiDAR point cloud callback
     * 
     * Extracts XY coordinates from 3D point cloud and feeds to EKF.
     * Accumulates points for occupancy grid generation.
     */
    void lidarCallback(const sensor_msgs::msg::PointCloud2::SharedPtr msg) {
        // Convert ROS PointCloud2 to PCL point cloud
        pcl::PointCloud<pcl::PointXYZ> cloud;
        pcl::fromROSMsg(*msg, cloud);
        
        // Update accumulated cloud for occupancy grid
        {
            std::lock_guard<std::mutex> lock(cloud_mutex_);
            merged_cloud_ += cloud;
            
            // Keep only recent points (limit cloud size)
            if (merged_cloud_.size() > 50000) {
                merged_cloud_.erase(merged_cloud_.begin(), 
                                  merged_cloud_.begin() + (merged_cloud_.size() - 50000));
            }
        }
        
        // Prediction step
        ekf_->predict();
        
        // Extract multiple points for robust estimation
        // Sample points to avoid computational overload
        int step = std::max(1, (int)cloud.size() / 100);
        for (size_t i = 0; i < cloud.size(); i += step) {
            double x = cloud[i].x;
            double y = cloud[i].y;
            
            // Filter out invalid points (NaN, zero range)
            if (std::isfinite(x) && std::isfinite(y) && 
                (x*x + y*y) > 0.01) {
                ekf_->updateLiDAR(x, y);
            }
        }
        
        publishFusedOdometry(msg->header);
        publishOccupancyGrid(msg->header);
    }
    
    /**
     * @brief Radar data callback
     * 
     * Processes radar measurements (range, azimuth, velocity).
     * Note: This implementation assumes IMU msg format with specific layout
     * In production, use custom RadarScan message type
     */
    void radarCallback(const sensor_msgs::msg::Imu::SharedPtr msg) {
        // Extract radar data from IMU message (placeholder)
        // In production: deserialize from actual RadarScan message
        // Format assumed: linear_acceleration contains [range, bearing, velocity]
        
        double range = msg->linear_acceleration.x;
        double bearing = msg->linear_acceleration.y;
        double velocity = msg->linear_acceleration.z;
        
        // Only process if range is positive
        if (range > 0.1 && range < 100.0) {
            ekf_->updateRadar(range, bearing, velocity);
            publishFusedOdometry(msg->header);
        }
    }
    
    /**
     * @brief Publish fused odometry estimate
     */
    void publishFusedOdometry(const std_msgs::msg::Header& header) {
        nav_msgs::msg::Odometry odom;
        odom.header = header;
        odom.header.frame_id = odom_frame_;
        odom.child_frame_id = base_frame_;
        
        Eigen::Vector4d state = ekf_->getState();
        Eigen::Matrix4d cov = ekf_->getCovariance();
        
        // Position
        odom.pose.pose.position.x = state(0);
        odom.pose.pose.position.y = state(1);
        odom.pose.pose.position.z = 0.0;
        odom.pose.pose.orientation.w = 1.0;
        
        // Pose covariance
        odom.pose.covariance[0] = cov(0, 0);  // x variance
        odom.pose.covariance[7] = cov(1, 1);  // y variance
        odom.pose.covariance[14] = 0.01;      // z variance
        
        // Velocity
        odom.twist.twist.linear.x = state(2);
        odom.twist.twist.linear.y = state(3);
        odom.twist.twist.angular.z = 0.0;
        
        // Twist covariance
        odom.twist.covariance[0] = cov(2, 2);  // vx variance
        odom.twist.covariance[7] = cov(3, 3);  // vy variance
        
        odom_pub_->publish(odom);
    }
    
    /**
     * @brief Generate and publish occupancy grid from accumulated point cloud
     */
    void publishOccupancyGrid(const std_msgs::msg::Header& header) {
        nav_msgs::msg::OccupancyGrid grid;
        grid.header = header;
        grid.header.frame_id = odom_frame_;
        
        // Grid parameters
        double resolution = 0.1;  // 10cm cells
        int width = 200;           // 20m x 20m grid
        int height = 200;
        double origin_x = -10.0;   // Grid center at robot
        double origin_y = -10.0;
        
        grid.info.resolution = resolution;
        grid.info.width = width;
        grid.info.height = height;
        grid.info.origin.position.x = origin_x;
        grid.info.origin.position.y = origin_y;
        grid.info.origin.position.z = 0.0;
        grid.info.origin.orientation.w = 1.0;
        
        // Initialize grid with unknown cells
        grid.data.assign(width * height, -1);
        
        // Populate grid from point cloud
        {
            std::lock_guard<std::mutex> lock(cloud_mutex_);
            
            for (const auto& point : merged_cloud_) {
                // Convert point to grid indices
                int gx = (int)((point.x - origin_x) / resolution);
                int gy = (int)((point.y - origin_y) / resolution);
                
                if (gx >= 0 && gx < width && gy >= 0 && gy < height) {
                    int idx = gy * width + gx;
                    grid.data[idx] = 100;  // Occupied
                }
            }
        }
        
        occupancy_pub_->publish(grid);
    }
};

int main(int argc, char * argv[])
{
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<SensorFusionNode>());
    rclcpp::shutdown();
    return 0;
}
