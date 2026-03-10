"""
Mechatronic Integration: 2D to 3D Coordinate Transformation
Maps image-space object coordinates (u, v) to 3D robot workspace coordinates.
Enables dynamic robot interaction tasks through vision-based targeting.
"""

import numpy as np
from typing import Tuple, List, Dict, Optional
import logging
from dataclasses import dataclass
from enum import Enum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class CameraIntrinsics:
    """Camera intrinsic parameters."""
    fx: float  # Focal length x (pixels)
    fy: float  # Focal length y (pixels)
    cx: float  # Principal point x (pixels)
    cy: float  # Principal point y (pixels)
    width: int  # Image width (pixels)
    height: int  # Image height (pixels)
    
    @property
    def K(self) -> np.ndarray:
        """Get camera intrinsic matrix K."""
        return np.array([
            [self.fx, 0, self.cx],
            [0, self.fy, self.cy],
            [0, 0, 1]
        ])


@dataclass
class RobotWorkspace:
    """Robot workspace constraints and parameters."""
    x_min: float  # Minimum x coordinate (mm)
    x_max: float  # Maximum x coordinate (mm)
    y_min: float  # Minimum y coordinate (mm)
    y_max: float  # Maximum y coordinate (mm)
    z_min: float  # Minimum z coordinate (mm)
    z_max: float  # Maximum z coordinate (mm)
    
    def is_within_bounds(self, point: np.ndarray) -> bool:
        """Check if point is within workspace."""
        x, y, z = point
        return (self.x_min <= x <= self.x_max and
                self.y_min <= y <= self.y_max and
                self.z_min <= z <= self.z_max)


class CoordinateSystem(Enum):
    """Coordinate system conventions."""
    EYE_IN_HAND = "eye_in_hand"
    EYE_TO_HAND = "eye_to_hand"


class MechatronicIntegration:
    """Vision-based robot task coordination system."""
    
    def __init__(self, camera_intrinsics: CameraIntrinsics, 
                 robot_workspace: RobotWorkspace,
                 cam_to_base: np.ndarray,
                 coordinate_system: CoordinateSystem = CoordinateSystem.EYE_TO_HAND):
        """
        Initialize mechatronic integration system.
        
        Args:
            camera_intrinsics: Camera calibration parameters
            robot_workspace: Robot workspace constraints
            cam_to_base: 4x4 transformation matrix from camera to robot base
            coordinate_system: Camera mounting configuration
        """
        self.camera = camera_intrinsics
        self.workspace = robot_workspace
        self.cam_to_base = cam_to_base
        self.coordinate_system = coordinate_system
        
        logger.info(f"Initialized with {coordinate_system.value} configuration")
        logger.info(f"Camera matrix K:\n{self.camera.K}")
    
    def pixel_to_3d(self, u: float, v: float, depth: float) -> np.ndarray:
        """
        Transform 2D pixel coordinates to 3D camera frame coordinates.
        
        Mathematical formulation:
        Given normalized coordinates (u', v') = ((u - cx) / fx, (v - cy) / fy),
        the 3D point in camera frame is computed as:
        
        $$P_c = \\begin{bmatrix} x_c \\\\ y_c \\\\ z_c \\end{bmatrix} = 
        z \\cdot \\begin{bmatrix} \\frac{u - c_x}{f_x} \\\\ \\frac{v - c_y}{f_y} \\\\ 1 \\end{bmatrix}$$
        
        Args:
            u: Pixel x-coordinate
            v: Pixel y-coordinate
            depth: Depth value at pixel (meters)
            
        Returns:
            3D point in camera frame [x_c, y_c, z_c]
        """
        # Backproject to 3D using camera intrinsics
        x_c = (u - self.camera.cx) * depth / self.camera.fx
        y_c = (v - self.camera.cy) * depth / self.camera.fy
        z_c = depth
        
        return np.array([x_c, y_c, z_c])
    
    def camera_to_base(self, point_3d: np.ndarray) -> np.ndarray:
        """
        Transform point from camera frame to robot base frame.
        
        Mathematical formulation:
        $$P_{base} = T_{c2b} \\cdot P_c$$
        
        where $T_{c2b}$ is the 4x4 homogeneous transformation matrix.
        
        Args:
            point_3d: 3D point in camera frame
            
        Returns:
            3D point in robot base frame
        """
        # Convert to homogeneous coordinates
        point_homogeneous = np.append(point_3d, 1)
        
        # Apply transformation
        point_base_homogeneous = self.cam_to_base @ point_homogeneous
        
        # Extract 3D coordinates
        return point_base_homogeneous[:3]
    
    def pixel_to_base(self, u: float, v: float, depth: float) -> Tuple[np.ndarray, bool]:
        """
        Complete pipeline: pixel coordinates to robot base frame.
        
        Args:
            u: Pixel x-coordinate
            v: Pixel y-coordinate
            depth: Depth at pixel (meters)
            
        Returns:
            Tuple of (3D point in base frame, is_within_workspace)
        """
        # Step 1: Backproject to 3D camera coordinates
        point_cam = self.pixel_to_3d(u, v, depth)
        
        # Step 2: Transform to robot base frame
        point_base = self.camera_to_base(point_cam)
        
        # Step 3: Check workspace bounds
        is_valid = self.workspace.is_within_bounds(point_base)
        
        logger.info(f"Pixel ({u:.1f}, {v:.1f}, depth={depth:.3f}m) -> "
                   f"Base ({point_base[0]:.3f}, {point_base[1]:.3f}, {point_base[2]:.3f}m) "
                   f"[Valid: {is_valid}]")
        
        return point_base, is_valid
    
    def detection_to_target(self, detection: Dict, depth_map: Optional[np.ndarray] = None) -> Dict:
        """
        Convert object detection to robot target coordinates.
        
        Args:
            detection: Detection dict with 'bbox', 'center' keys
            depth_map: Depth image (optional, uses center pixel if None)
            
        Returns:
            Target coordinates and metadata
        """
        x1, y1, x2, y2 = detection['bbox']
        center_u = (x1 + x2) // 2
        center_v = (y1 + y2) // 2
        
        # Get depth value
        if depth_map is not None:
            depth = depth_map[center_v, center_u] / 1000.0  # Convert mm to m
        else:
            # Use default depth (e.g., 0.5 meters)
            depth = 0.5
        
        # Transform to base frame
        target_point, is_valid = self.pixel_to_base(center_u, center_v, depth)
        
        return {
            'class': detection['class_name'],
            'confidence': detection['confidence'],
            'pixel_center': (center_u, center_v),
            'depth_m': depth,
            'target_xyz_m': target_point,
            'is_reachable': is_valid,
            'bbox_area_pixels': detection['area']
        }
    
    def batch_detections_to_targets(self, detections: List[Dict], 
                                    depth_map: Optional[np.ndarray] = None) -> List[Dict]:
        """
        Convert multiple detections to target coordinates.
        
        Args:
            detections: List of detection dicts
            depth_map: Depth image (optional)
            
        Returns:
            List of target coordinates
        """
        targets = []
        for detection in detections:
            target = self.detection_to_target(detection, depth_map)
            targets.append(target)
        
        # Sort by reachability and confidence
        targets_sorted = sorted(targets, 
                               key=lambda x: (x['is_reachable'], x['confidence']),
                               reverse=True)
        
        logger.info(f"Processed {len(detections)} detections -> "
                   f"{sum(1 for t in targets_sorted if t['is_reachable'])} reachable targets")
        
        return targets_sorted
    
    def compute_end_effector_pose(self, target_xyz: np.ndarray, 
                                  approach_distance: float = 0.1) -> np.ndarray:
        """
        Compute robot end-effector pose for target object.
        
        Args:
            target_xyz: Target 3D coordinates in base frame
            approach_distance: Distance to approach from above (meters)
            
        Returns:
            4x4 homogeneous transformation matrix for end-effector
        """
        # Create approach pose (above target, vertical approach)
        approach_point = target_xyz.copy()
        approach_point[2] += approach_distance  # Move up
        
        # Create end-effector frame with z-axis pointing down
        # Assuming parallel gripper orientation
        T_ee = np.eye(4)
        T_ee[0:3, 3] = approach_point
        
        # Orientation: z-axis pointing downward toward object
        z_axis = -np.array([0, 0, 1])
        x_axis = np.array([1, 0, 0])
        y_axis = np.cross(z_axis, x_axis)
        
        T_ee[0:3, 0] = x_axis
        T_ee[0:3, 1] = y_axis
        T_ee[0:3, 2] = z_axis
        
        return T_ee
    
    def set_camera_to_base_transform(self, T: np.ndarray) -> None:
        """Update camera-to-base transformation matrix."""
        if T.shape != (4, 4):
            raise ValueError("Transformation matrix must be 4x4")
        self.cam_to_base = T
        logger.info("Updated camera-to-base transformation")
    
    def get_calibration_matrix(self) -> Dict:
        """Get current calibration parameters."""
        return {
            'camera_intrinsics': {
                'fx': self.camera.fx,
                'fy': self.camera.fy,
                'cx': self.camera.cx,
                'cy': self.camera.cy
            },
            'camera_to_base': self.cam_to_base.tolist(),
            'workspace': {
                'x_range': [self.workspace.x_min, self.workspace.x_max],
                'y_range': [self.workspace.y_min, self.workspace.y_max],
                'z_range': [self.workspace.z_min, self.workspace.z_max]
            }
        }


# Example factory functions for common robot setups

def create_example_integration() -> MechatronicIntegration:
    """Create example mechatronic integration with sample calibration."""
    
    # Standard camera intrinsics (typical for USB cameras)
    camera = CameraIntrinsics(
        fx=500.0, fy=500.0,
        cx=320.0, cy=240.0,
        width=640, height=480
    )
    
    # 6-DOF robot workspace (typical collaborative arm)
    workspace = RobotWorkspace(
        x_min=-1.5, x_max=1.5,
        y_min=-1.5, y_max=1.5,
        z_min=0.0, z_max=2.0
    )
    
    # Camera-to-base transformation (example: camera 1m above base, 0.5m forward)
    T_cam_to_base = np.eye(4)
    T_cam_to_base[0:3, 3] = np.array([0.5, 0.0, 1.0])  # Translation
    T_cam_to_base[0:3, 0:3] = np.eye(3)  # No rotation (identity)
    
    return MechatronicIntegration(camera, workspace, T_cam_to_base)


if __name__ == "__main__":
    # Example usage
    mech = create_example_integration()
    
    # Example detection
    example_detection = {
        'class_name': 'bottle',
        'confidence': 0.92,
        'bbox': (100, 150, 200, 300),
        'area': 15000
    }
    
    # Convert to target
    target = mech.detection_to_target(example_detection)
    logger.info(f"Target coordinates: {target}")
    
    if target['is_reachable']:
        # Compute end-effector pose
        ee_pose = mech.compute_end_effector_pose(target['target_xyz_m'])
        logger.info(f"End-effector approach pose:\n{ee_pose}")
