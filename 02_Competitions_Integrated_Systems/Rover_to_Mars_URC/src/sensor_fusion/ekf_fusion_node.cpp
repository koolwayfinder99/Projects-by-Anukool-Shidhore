#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/imu.hpp>
#include <nav_msgs/msg/odometry.hpp>
#include <geometry_msgs/msg/pose_with_covariance_stamped.hpp>
#include <Eigen/Dense>
#include <memory>
#include <cmath>

/**
 * @class EKFFusionNode
 * @brief Extended Kalman Filter (EKF) based sensor fusion for Mars Rover localization
 * 
 * Integrates IMU (accelerometer, gyroscope) and odometry data for robust localization
 * on uneven Martian terrain. Operates at 30Hz for real-time mapping and navigation.
 * Reflects the Steel (robust hardware) and Silicon (intelligent algorithms) integration.
 */
class EKFFusionNode : public rclcpp::Node {
public:
    EKFFusionNode() : rclcpp::Node("ekf_fusion_node") {
        // Initialize EKF state
        initializeEKF();
        
        // Subscribers
        imu_subscription_ = this->create_subscription<sensor_msgs::msg::Imu>(
            "imu/data", 10,
            std::bind(&EKFFusionNode::imuCallback, this, std::placeholders::_1));
        
        odometry_subscription_ = this->create_subscription<nav_msgs::msg::Odometry>(
            "odom", 10,
            std::bind(&EKFFusionNode::odometryCallback, this, std::placeholders::_1));
        
        // Publisher
        fused_pose_publisher_ = this->create_publisher<geometry_msgs::msg::PoseWithCovarianceStamped>(
            "fused_pose", 10);
        
        // 30Hz fusion rate for real-time performance
        fusion_timer_ = this->create_wall_timer(
            std::chrono::milliseconds(33),  // ~30Hz
            std::bind(&EKFFusionNode::fusionCallback, this));
        
        RCLCPP_INFO(this->get_logger(), "EKF Fusion Node initialized at 30Hz");
    }

private:
    // ROS 2 interfaces
    rclcpp::Subscription<sensor_msgs::msg::Imu>::SharedPtr imu_subscription_;
    rclcpp::Subscription<nav_msgs::msg::Odometry>::SharedPtr odometry_subscription_;
    rclcpp::Publisher<geometry_msgs::msg::PoseWithCovarianceStamped>::SharedPtr fused_pose_publisher_;
    rclcpp::TimerBase::SharedPtr fusion_timer_;
    
    // EKF state matrices
    Eigen::VectorXd state_;           // State vector [x, y, theta, vx, vy, omega]
    Eigen::MatrixXd P_;               // State covariance matrix (6x6)
    Eigen::MatrixXd Q_;               // Process noise covariance (6x6)
    Eigen::MatrixXd R_imu_;           // IMU measurement noise (3x3)
    Eigen::MatrixXd R_odom_;          // Odometry measurement noise (3x3)
    
    // Latest sensor measurements
    sensor_msgs::msg::Imu latest_imu_;
    nav_msgs::msg::Odometry latest_odom_;
    bool imu_received_ = false;
    bool odom_received_ = false;
    
    rclcpp::Time last_fusion_time_;
    
    /**
     * Initialize EKF matrices with appropriate noise parameters for Mars terrain
     */
    void initializeEKF() {
        state_.resize(6);
        state_.setZero();  // [x, y, theta, vx, vy, omega]
        
        // Initial covariance (high uncertainty at start)
        P_.resize(6, 6);
        P_.setIdentity();
        P_ *= 1.0;
        
        // Process noise: accounts for model uncertainty and uneven terrain
        Q_.resize(6, 6);
        Q_.setZero();
        Q_(0, 0) = 0.01;   // Position uncertainty
        Q_(1, 1) = 0.01;
        Q_(2, 2) = 0.001;  // Orientation uncertainty
        Q_(3, 3) = 0.05;   // Velocity uncertainty
        Q_(4, 4) = 0.05;
        Q_(5, 5) = 0.01;   // Angular velocity uncertainty
        
        // IMU measurement noise (3x3): acceleration and angular velocity
        R_imu_.resize(3, 3);
        R_imu_.setZero();
        R_imu_(0, 0) = 0.02;  // Accel noise
        R_imu_(1, 1) = 0.02;
        R_imu_(2, 2) = 0.01;  // Angular velocity noise
        
        // Odometry measurement noise (3x3): position and orientation
        R_odom_.resize(3, 3);
        R_odom_.setZero();
        R_odom_(0, 0) = 0.05;  // Position noise
        R_odom_(1, 1) = 0.05;
        R_odom_(2, 2) = 0.02;  // Orientation noise
        
        last_fusion_time_ = this->now();
    }
    
    /**
     * IMU callback: Store latest IMU data
     */
    void imuCallback(const sensor_msgs::msg::Imu::SharedPtr msg) {
        latest_imu_ = *msg;
        imu_received_ = true;
    }
    
    /**
     * Odometry callback: Store latest odometry data
     */
    void odometryCallback(const nav_msgs::msg::Odometry::SharedPtr msg) {
        latest_odom_ = *msg;
        odom_received_ = true;
    }
    
    /**
     * Main fusion callback: Performs EKF predict and update steps
     */
    void fusionCallback() {
        if (!imu_received_ || !odom_received_) {
            return;
        }
        
        rclcpp::Time current_time = this->now();
        double dt = (current_time - last_fusion_time_).seconds();
        
        if (dt <= 0.0) return;
        
        // EKF Predict Step
        predictStep(dt);
        
        // EKF Update Step with IMU measurements
        updateStepIMU();
        
        // EKF Update Step with Odometry measurements
        updateStepOdometry();
        
        // Publish fused pose estimate
        publishFusedPose(current_time);
        
        last_fusion_time_ = current_time;
    }
    
    /**
     * EKF Predict Step: Propagate state and covariance
     * Uses kinematic model for uneven terrain traversal
     */
    void predictStep(double dt) {
        // State transition (kinematic model)
        Eigen::MatrixXd F = Eigen::MatrixXd::Identity(6, 6);
        
        // Position update from velocity
        F(0, 3) = dt;  // dx = vx * dt
        F(1, 4) = dt;  // dy = vy * dt
        F(2, 5) = dt;  // dtheta = omega * dt
        
        // State prediction: x_pred = F * x
        state_(0) += state_(3) * dt;  // x
        state_(1) += state_(4) * dt;  // y
        state_(2) += state_(5) * dt;  // theta
        
        // Normalize angle to [-pi, pi]
        while (state_(2) > M_PI) state_(2) -= 2 * M_PI;
        while (state_(2) < -M_PI) state_(2) += 2 * M_PI;
        
        // Covariance prediction: P_pred = F * P * F^T + Q
        P_ = F * P_ * F.transpose() + Q_;
    }
    
    /**
     * EKF Update Step with IMU measurements
     * Fuses accelerometer and gyroscope data
     */
    void updateStepIMU() {
        // Measurement vector [ax, ay, omega_z]
        Eigen::VectorXd z(3);
        z(0) = latest_imu_.linear_acceleration.x;
        z(1) = latest_imu_.linear_acceleration.y;
        z(2) = latest_imu_.angular_velocity.z;
        
        // Measurement matrix H (maps state to measurement space)
        Eigen::MatrixXd H = Eigen::MatrixXd::Zero(3, 6);
        H(0, 3) = 1.0;  // Accel_x relates to vx
        H(1, 4) = 1.0;  // Accel_y relates to vy
        H(2, 5) = 1.0;  // Angular vel relates to omega
        
        // Expected measurement from current state
        Eigen::VectorXd z_pred = H * state_;
        
        // Innovation
        Eigen::VectorXd y = z - z_pred;
        
        // Innovation covariance: S = H * P * H^T + R
        Eigen::MatrixXd S = H * P_ * H.transpose() + R_imu_;
        
        // Kalman gain: K = P * H^T * S^(-1)
        Eigen::MatrixXd K = P_ * H.transpose() * S.inverse();
        
        // State update: x = x + K * y
        state_ += K * y;
        
        // Covariance update: P = (I - K * H) * P
        Eigen::MatrixXd I = Eigen::MatrixXd::Identity(6, 6);
        P_ = (I - K * H) * P_;
    }
    
    /**
     * EKF Update Step with Odometry measurements
     * Fuses wheel odometry for position and orientation
     */
    void updateStepOdometry() {
        // Measurement vector [x, y, theta]
        Eigen::VectorXd z(3);
        z(0) = latest_odom_.pose.pose.position.x;
        z(1) = latest_odom_.pose.pose.position.y;
        
        // Extract theta from quaternion
        double qx = latest_odom_.pose.pose.orientation.x;
        double qy = latest_odom_.pose.pose.orientation.y;
        double qz = latest_odom_.pose.pose.orientation.z;
        double qw = latest_odom_.pose.pose.orientation.w;
        
        double theta = std::atan2(2 * (qw * qz + qx * qy), 1 - 2 * (qy * qy + qz * qz));
        z(2) = theta;
        
        // Measurement matrix H (direct position and orientation measurements)
        Eigen::MatrixXd H = Eigen::MatrixXd::Zero(3, 6);
        H(0, 0) = 1.0;  // x position
        H(1, 1) = 1.0;  // y position
        H(2, 2) = 1.0;  // theta
        
        // Expected measurement
        Eigen::VectorXd z_pred = H * state_;
        
        // Innovation with angle wrapping
        Eigen::VectorXd y = z - z_pred;
        while (y(2) > M_PI) y(2) -= 2 * M_PI;
        while (y(2) < -M_PI) y(2) += 2 * M_PI;
        
        // Innovation covariance
        Eigen::MatrixXd S = H * P_ * H.transpose() + R_odom_;
        
        // Kalman gain
        Eigen::MatrixXd K = P_ * H.transpose() * S.inverse();
        
        // State update
        state_ += K * y;
        
        // Covariance update
        Eigen::MatrixXd I = Eigen::MatrixXd::Identity(6, 6);
        P_ = (I - K * H) * P_;
    }
    
    /**
     * Publish the fused pose estimate with covariance
     */
    void publishFusedPose(const rclcpp::Time& timestamp) {
        auto fused_pose = std::make_unique<geometry_msgs::msg::PoseWithCovarianceStamped>();
        
        fused_pose->header.stamp = timestamp;
        fused_pose->header.frame_id = "odom";
        
        // Position
        fused_pose->pose.pose.position.x = state_(0);
        fused_pose->pose.pose.position.y = state_(1);
        fused_pose->pose.pose.position.z = 0.0;
        
        // Orientation from theta
        double half_theta = state_(2) / 2.0;
        fused_pose->pose.pose.orientation.x = 0.0;
        fused_pose->pose.pose.orientation.y = 0.0;
        fused_pose->pose.pose.orientation.z = std::sin(half_theta);
        fused_pose->pose.pose.orientation.w = std::cos(half_theta);
        
        // Covariance (position and orientation)
        for (size_t i = 0; i < 36; ++i) {
            fused_pose->pose.covariance[i] = 0.0;
        }
        fused_pose->pose.covariance[0] = P_(0, 0);   // x variance
        fused_pose->pose.covariance[7] = P_(1, 1);   // y variance
        fused_pose->pose.covariance[35] = P_(2, 2);  // theta variance
        
        fused_pose_publisher_->publish(std::move(fused_pose));
    }
};

/**
 * Main entry point
 */
int main(int argc, char* argv[]) {
    rclcpp::init(argc, argv);
    auto node = std::make_shared<EKFFusionNode>();
    rclcpp::spin(node);
    rclcpp::shutdown();
    return 0;
}
