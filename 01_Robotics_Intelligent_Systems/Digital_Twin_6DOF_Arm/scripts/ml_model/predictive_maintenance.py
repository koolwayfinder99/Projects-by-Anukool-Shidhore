#!/usr/bin/env python3
"""
Predictive Maintenance Module for 6-DOF Robotic Arm Digital Twin

This module implements real-time joint degradation monitoring using Scikit-learn
models trained on historical sensor data. It monitors joint efforts and predicts
maintenance requirements based on degradation patterns.

Features:
- Real-time joint effort monitoring across 6 axes
- ML-based degradation prediction
- Anomaly detection using Isolation Forest
- Maintenance alert generation
- Historical data logging for model retraining

Author: RWU Master's Project - Digital Twin Systems
License: MIT
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Float32MultiArray, Int32MultiArray
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

import numpy as np
import pickle
import json
from pathlib import Path
from datetime import datetime
from collections import deque
from typing import Dict, List, Tuple, Optional

from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
import warnings

warnings.filterwarnings('ignore')


class JointDegradationModel:
    """
    ML-based model for predicting joint degradation and maintenance needs.
    
    Uses an ensemble approach combining:
    - Isolation Forest for anomaly detection
    - RandomForest for degradation prediction
    - Linear regression for trend analysis
    """
    
    def __init__(self, model_path: Optional[Path] = None):
        """
        Initialize the joint degradation model.
        
        Args:
            model_path: Path to pre-trained model weights. If None, initializes with default models.
        """
        self.scaler = StandardScaler()
        self.anomaly_detector = IsolationForest(
            contamination=0.1,
            n_estimators=100,
            random_state=42,
            n_jobs=-1
        )
        
        self.degradation_predictor = RandomForestRegressor(
            n_estimators=50,
            max_depth=10,
            random_state=42,
            n_jobs=-1
        )
        
        self.trend_analyzer = LinearRegression()
        
        self.is_trained = False
        self.model_path = model_path
        
        if model_path and model_path.exists():
            self._load_model(model_path)
    
    def train(self, X_train: np.ndarray, y_train: np.ndarray) -> None:
        """
        Train the degradation prediction models on historical data.
        
        Args:
            X_train: Training features [n_samples, n_features] - joint efforts, temps, speeds
            y_train: Training labels [n_samples] - degradation level (0-100%)
        """
        X_scaled = self.scaler.fit_transform(X_train)
        
        # Train anomaly detector
        self.anomaly_detector.fit(X_scaled)
        
        # Train degradation predictor
        self.degradation_predictor.fit(X_scaled, y_train)
        
        # Prepare data for trend analysis
        if len(X_train) > 1:
            X_trend = np.arange(len(X_train)).reshape(-1, 1)
            y_trend = y_train.reshape(-1, 1)
            self.trend_analyzer.fit(X_trend, y_trend)
        
        self.is_trained = True
    
    def predict_degradation(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Predict joint degradation levels and detect anomalies.
        
        Args:
            X: Feature array [n_samples, n_features]
            
        Returns:
            Tuple of:
                - degradation_levels: Predicted degradation (0-100%)
                - anomaly_scores: Anomaly scores (-1: anomaly, 1: normal)
                - confidence_scores: Prediction confidence (0-1)
        """
        if not self.is_trained:
            return np.zeros(len(X)), np.ones(len(X)), np.full(len(X), 0.5)
        
        X_scaled = self.scaler.transform(X)
        
        # Anomaly detection
        anomaly_scores = self.anomaly_detector.predict(X_scaled)
        anomaly_confidence = self.anomaly_detector.score_samples(X_scaled)
        
        # Degradation prediction
        degradation_raw = self.degradation_predictor.predict(X_scaled)
        degradation_levels = np.clip(degradation_raw * 100, 0, 100)  # Normalize to 0-100%
        
        # Confidence from feature importances
        importances = self.degradation_predictor.feature_importances_
        confidence_scores = (importances / importances.sum()).max() * np.ones(len(X))
        
        return degradation_levels, anomaly_scores, confidence_scores
    
    def _load_model(self, path: Path) -> None:
        """Load pre-trained model weights from disk."""
        try:
            with open(path, 'rb') as f:
                model_data = pickle.load(f)
            self.scaler = model_data.get('scaler', self.scaler)
            self.anomaly_detector = model_data.get('anomaly_detector', self.anomaly_detector)
            self.degradation_predictor = model_data.get('degradation_predictor', self.degradation_predictor)
            self.trend_analyzer = model_data.get('trend_analyzer', self.trend_analyzer)
            self.is_trained = True
        except Exception as e:
            print(f"Warning: Failed to load model from {path}: {e}")
    
    def save_model(self, path: Path) -> None:
        """Save model weights to disk for future inference."""
        path.parent.mkdir(parents=True, exist_ok=True)
        model_data = {
            'scaler': self.scaler,
            'anomaly_detector': self.anomaly_detector,
            'degradation_predictor': self.degradation_predictor,
            'trend_analyzer': self.trend_analyzer,
        }
        with open(path, 'wb') as f:
            pickle.dump(model_data, f)


class PredictiveMaintenanceNode(Node):
    """
    ROS2 Node for real-time predictive maintenance monitoring of 6-DOF arm.
    
    Subscribes to:
        - /joint_states: Current joint state measurements
    
    Publishes to:
        - /maintenance/degradation_levels: Predicted degradation per joint
        - /maintenance/anomalies: Anomaly detection results
        - /maintenance/alerts: Critical maintenance alerts
    """
    
    def __init__(self):
        """Initialize the predictive maintenance node."""
        super().__init__('predictive_maintenance_monitor')
        
        # Configuration
        self.joint_names = [
            'joint_1', 'joint_2', 'joint_3',
            'joint_4', 'joint_5', 'joint_6'
        ]
        self.n_joints = len(self.joint_names)
        self.window_size = 20  # Rolling window for feature extraction
        self.update_rate = 10.0  # Hz
        
        # Initialize ML model
        model_path = Path.home() / '.ros' / 'arm_6dof_models' / 'degradation_model.pkl'
        self.ml_model = JointDegradationModel(model_path)
        
        # Data buffers for feature extraction
        self.effort_buffer: Dict[str, deque] = {
            name: deque(maxlen=self.window_size) for name in self.joint_names
        }
        self.velocity_buffer: Dict[str, deque] = {
            name: deque(maxlen=self.window_size) for name in self.joint_names
        }
        self.temperature_buffer: Dict[str, deque] = {
            name: deque(maxlen=self.window_size) for name in self.joint_names
        }
        
        # Initialize with placeholder temperature data (simulated from effort)
        self.temperature_estimate: Dict[str, float] = {
            name: 25.0 for name in self.joint_names
        }
        
        # Historical data for logging
        self.history = []
        self.maintenance_alerts = []
        
        # QoS settings for real-time performance
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1
        )
        
        # Subscribers
        self.joint_state_sub = self.create_subscription(
            JointState,
            '/joint_states',
            self.joint_state_callback,
            qos_profile
        )
        
        # Publishers
        self.degradation_pub = self.create_publisher(
            Float32MultiArray,
            '/maintenance/degradation_levels',
            qos_profile
        )
        
        self.anomaly_pub = self.create_publisher(
            Int32MultiArray,
            '/maintenance/anomalies',
            qos_profile
        )
        
        self.alert_pub = self.create_publisher(
            std_msgs.String,
            '/maintenance/alerts',
            qos_profile
        )
        
        # Timer for periodic processing
        self.timer = self.create_timer(
            1.0 / self.update_rate,
            self.prediction_callback
        )
        
        self.get_logger().info(
            f"Predictive Maintenance Node initialized with {self.n_joints} joints"
        )
    
    def joint_state_callback(self, msg: JointState) -> None:
        """
        Callback for joint state messages.
        
        Args:
            msg: JointState message containing position, velocity, effort
        """
        for i, name in enumerate(msg.name):
            if name in self.joint_names:
                # Buffer joint measurements
                if i < len(msg.effort):
                    self.effort_buffer[name].append(msg.effort[i])
                
                if i < len(msg.velocity):
                    self.velocity_buffer[name].append(abs(msg.velocity[i]))
                
                # Estimate temperature from effort (simplified model)
                # In real system, would use actual thermal sensors
                if len(self.effort_buffer[name]) > 0:
                    effort_avg = np.mean(list(self.effort_buffer[name]))
                    temp_delta = effort_avg * 0.05  # Simplified: 0.05°C per effort unit
                    self.temperature_estimate[name] = 25.0 + temp_delta
                    self.temperature_buffer[name].append(self.temperature_estimate[name])
    
    def prediction_callback(self) -> None:
        """
        Periodic callback for degradation prediction and anomaly detection.
        Runs at configurable frequency (default 10 Hz).
        """
        # Collect features for all joints
        features_list = []
        joint_indices = []
        
        for idx, name in enumerate(self.joint_names):
            if (len(self.effort_buffer[name]) > 5 and
                len(self.velocity_buffer[name]) > 5 and
                len(self.temperature_buffer[name]) > 5):
                
                # Extract statistical features from buffers
                features = self._extract_features(name)
                if features is not None:
                    features_list.append(features)
                    joint_indices.append(idx)
        
        if not features_list:
            return
        
        X = np.array(features_list)
        
        # Run predictions
        degradation, anomalies, confidence = self.ml_model.predict_degradation(X)
        
        # Create and publish messages
        deg_msg = Float32MultiArray()
        deg_msg.data = degradation.tolist()
        self.degradation_pub.publish(deg_msg)
        
        anom_msg = Int32MultiArray()
        anom_msg.data = anomalies.astype(int).tolist()
        self.anomaly_pub.publish(anom_msg)
        
        # Check for critical conditions and generate alerts
        self._check_maintenance_alerts(joint_indices, degradation, anomalies)
        
        # Log historical data
        self._log_data(joint_indices, degradation, anomalies, confidence)
    
    def _extract_features(self, joint_name: str) -> Optional[np.ndarray]:
        """
        Extract statistical features from joint sensor buffers.
        
        Args:
            joint_name: Name of the joint
            
        Returns:
            Feature vector or None if insufficient data
        """
        effort = np.array(list(self.effort_buffer[joint_name]))
        velocity = np.array(list(self.velocity_buffer[joint_name]))
        temperature = np.array(list(self.temperature_buffer[joint_name]))
        
        if len(effort) < 3:
            return None
        
        features = np.array([
            np.mean(effort),           # Mean effort
            np.std(effort),            # Effort variation
            np.max(effort),            # Peak effort
            np.mean(velocity),         # Mean velocity
            np.std(velocity),          # Velocity variation
            np.mean(temperature),      # Mean temperature
            np.std(temperature),       # Temperature variation
            np.mean(effort) * np.std(effort),  # Effort interaction
        ])
        
        return features
    
    def _check_maintenance_alerts(self, indices: List[int], 
                                  degradation: np.ndarray,
                                  anomalies: np.ndarray) -> None:
        """
        Check for maintenance-critical conditions and publish alerts.
        
        Args:
            indices: Joint indices being analyzed
            degradation: Predicted degradation levels
            anomalies: Anomaly detection results
        """
        for idx, deg_level, anomaly in zip(indices, degradation, anomalies):
            joint_name = self.joint_names[idx]
            
            # Critical degradation
            if deg_level > 80.0:
                alert = (f"CRITICAL: {joint_name} degradation at {deg_level:.1f}%. "
                        f"Schedule immediate maintenance.")
                self._publish_alert(alert, severity="CRITICAL")
            
            # Warning degradation
            elif deg_level > 50.0:
                alert = (f"WARNING: {joint_name} degradation at {deg_level:.1f}%. "
                        f"Plan maintenance within next 100 hours.")
                self._publish_alert(alert, severity="WARNING")
            
            # Anomaly detection
            if anomaly == -1:
                alert = f"ANOMALY: Unusual behavior detected in {joint_name}"
                self._publish_alert(alert, severity="INFO")
    
    def _publish_alert(self, message: str, severity: str = "INFO") -> None:
        """
        Publish maintenance alert message.
        
        Args:
            message: Alert message content
            severity: Alert severity level (INFO, WARNING, CRITICAL)
        """
        timestamp = datetime.now().isoformat()
        alert_json = json.dumps({
            'timestamp': timestamp,
            'severity': severity,
            'message': message
        })
        
        alert_msg = std_msgs.String()
        alert_msg.data = alert_json
        self.alert_pub.publish(alert_msg)
        
        log_level = {
            'INFO': self.get_logger().info,
            'WARNING': self.get_logger().warn,
            'CRITICAL': self.get_logger().error,
        }
        log_level.get(severity, self.get_logger().info)(message)
        
        self.maintenance_alerts.append({
            'timestamp': timestamp,
            'severity': severity,
            'message': message
        })
    
    def _log_data(self, indices: List[int], degradation: np.ndarray,
                  anomalies: np.ndarray, confidence: np.ndarray) -> None:
        """
        Log prediction data for offline analysis and model retraining.
        
        Args:
            indices: Joint indices
            degradation: Degradation predictions
            anomalies: Anomaly scores
            confidence: Prediction confidence scores
        """
        entry = {
            'timestamp': datetime.now().isoformat(),
            'joint_indices': indices,
            'degradation': degradation.tolist(),
            'anomalies': anomalies.tolist(),
            'confidence': confidence.tolist(),
        }
        self.history.append(entry)
        
        # Periodically save history to disk
        if len(self.history) % 100 == 0:
            self._save_history()
    
    def _save_history(self) -> None:
        """Save historical data to disk for analysis."""
        log_dir = Path.home() / '.ros' / 'arm_6dof_logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        
        log_file = log_dir / f"maintenance_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            with open(log_file, 'w') as f:
                json.dump(self.history, f, indent=2)
        except Exception as e:
            self.get_logger().error(f"Failed to save history: {e}")


def main(args=None):
    """Entry point for the predictive maintenance node."""
    rclpy.init(args=args)
    
    try:
        node = PredictiveMaintenanceNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()
