import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import LaserScan

class RoverNavigation(Node):
    """
    Autonomous Navigation Node for URC Rover.
    Implements basic obstacle avoidance using LiDAR data.
    """
    def __init__(self):
        super().__init__('rover_navigation')
        self.publisher_ = self.create_publisher(Twist, '/cmd_vel', 10)
        self.subscription = self.create_subscription(
            LaserScan, '/scan', self.scan_callback, 10)
        self.get_logger().info('Rover Navigation Node Started')

    def scan_callback(self, msg):
        # Logic: If obstacle is closer than 1.0m, turn left.
        move_cmd = Twist()
        min_distance = min(msg.ranges)
        
        if min_distance < 1.0:
            move_cmd.angular.z = 0.5 # Turn
            move_cmd.linear.x = 0.0
            self.get_logger().warn(f'Obstacle detected at {min_distance}m! Turning...')
        else:
            move_cmd.linear.x = 0.5 # Move forward
            move_cmd.angular.z = 0.0
            
        self.publisher_.publish(move_cmd)

def main(args=None):
    rclpy.init(args=args)
    node = RoverNavigation()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()