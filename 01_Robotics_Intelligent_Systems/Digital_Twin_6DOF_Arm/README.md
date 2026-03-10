# Digital Twin 6-DOF Robotic Arm

**Advanced Predictive Maintenance System for Industrial Robotic Arm Simulation**

Master's Project - Rhode Island University (RIU)  
Advanced Robotics & Digital Twin Systems  
**Date:** 2024  
**Author:** Anukool Shidhore

---

## 📋 Project Overview

This project implements a **comprehensive digital twin system** for a 6-degree-of-freedom (6-DOF) industrial robotic arm. The digital twin integrates real-time simulation in Gazebo with machine learning-based predictive maintenance algorithms, enabling proactive fault detection and maintenance planning.

### Key Features

✅ **High-Fidelity Simulation**
- 6-DOF kinematic chain with realistic joint dynamics
- Gazebo physics engine integration
- Joint transmission models for effort control

✅ **Real-Time Monitoring**
- Live joint state monitoring (position, velocity, effort)
- Multi-sensory data fusion (effort, velocity, temperature estimation)
- Streaming data to ROS2 topics

✅ **Predictive Maintenance**
- ML-based joint degradation prediction
- Anomaly detection using Isolation Forest
- Degradation forecasting with Random Forest
- Alert generation system with severity levels

✅ **Modular Architecture**
- Clean separation of simulation, control, and ML components
- Easy integration with actual hardware
- Extensible design for additional sensors

---

## 🏗️ Project Structure

```
Digital_Twin_6DOF_Arm/
├── description/
│   └── urdf/
│       └── arm_6dof.urdf.xacro       # Kinematic model definition
├── launch/
│   └── simulation.launch.py           # Gazebo simulation launcher
├── config/
│   ├── controller_config.yaml         # Joint controller parameters
│   └── arm_properties.yaml            # Arm specifications
├── scripts/
│   └── ml_model/
│       ├── __init__.py
│       ├── predictive_maintenance.py  # ML monitoring node
│       ├── train_models.py            # Model training script
│       └── data_analyzer.py           # Historical data analysis
├── meshes/                            # (Optional) STL mesh files
├── README.md                          # This file
└── requirements.txt                   # Python dependencies
```

---

## 🔧 Technical Specifications

### Robotic Arm Configuration

| Parameter | Value | Unit |
|-----------|-------|------|
| Degrees of Freedom | 6 | - |
| Base Mass | 5.0 | kg |
| Link Mass | 1.5 | kg (each) |
| Tool Mass | 0.5 | kg |
| Joint 1 (Waist) - Effort | 150 | N·m |
| Joint 2,3 (Shoulder/Upper Arm) - Effort | 120-150 | N·m |
| Joint 4,5,6 (Wrist) - Effort | 80-100 | N·m |
| Max Joint Velocity | 4.71 | rad/s |

### Kinematic Chain

```
base_link ─[joint_1]─→ link_1 ─[joint_2]─→ link_2
   │                      │
   │                      └─[joint_3]─→ link_3 ─[joint_4]─→ link_4
   │
   └─[joint_5]─→ link_5 ─[joint_6]─→ link_6 ─[joint_ee]─→ ee_link
```

**Joint Types & Axes:**
- **Joint 1:** Revolute Z-axis (Waist rotation)
- **Joint 2,3:** Revolute Y-axis (Shoulder/Elbow pitch)
- **Joint 4:** Revolute Y-axis (Wrist 1 pitch)
- **Joint 5:** Revolute Z-axis (Wrist 2 roll)
- **Joint 6:** Revolute Y-axis (Wrist 3 pitch)

---

## 🤖 ML-Based Predictive Maintenance

### Degradation Model Architecture

The predictive maintenance system uses an ensemble machine learning approach:

```python
Ensemble ML Model
├── Isolation Forest (Anomaly Detection)
│   ├── Contamination: 10%
│   ├── Trees: 100
│   └── Output: Anomaly Score (-1/+1)
│
├── Random Forest (Degradation Prediction)
│   ├── Trees: 50
│   ├── Max Depth: 10
│   └── Output: Degradation Level (0-100%)
│
└── Linear Regression (Trend Analysis)
    ├── Feature: Time
    ├── Target: Degradation Level
    └── Output: Trend Slope
```

### Feature Engineering

The model extracts 8 statistical features from each joint's sensor data:

```python
Features = [
    Mean Effort,              # Average joint effort
    Effort Std Dev,           # Effort variation (stability indicator)
    Peak Effort,              # Maximum instantaneous effort
    Mean Velocity,            # Average joint speed
    Velocity Std Dev,         # Speed variation
    Mean Temperature,         # Thermal state (estimated from effort)
    Temperature Std Dev,      # Temperature variation
    Effort × Std Dev,         # Interaction term
]
```

### Degradation Classification

| Degradation Level | Status | Action | Timeline |
|-------------------|--------|--------|----------|
| 0-30% | **Healthy** | Continue monitoring | - |
| 30-50% | **Minor** | Plan maintenance | 500+ hours |
| 50-80% | **Moderate** | Schedule maintenance | 100-200 hours |
| 80-100% | **Critical** | Immediate maintenance | < 24 hours |

---

## 🚀 Getting Started

### Prerequisites

- **ROS2** (Humble or newer)
- **Gazebo 11+**
- **Python 3.8+**
- **numpy**, **scikit-learn**, **rclpy**

### Installation

1. **Clone/Setup the project:**
   ```bash
   cd ~/ros2_ws/src
   # Place Digital_Twin_6DOF_Arm directory here
   ```

2. **Install dependencies:**
   ```bash
   pip install -r Digital_Twin_6DOF_Arm/requirements.txt
   ```

3. **Build ROS2 packages:**
   ```bash
   cd ~/ros2_ws
   colcon build --packages-select arm_6dof_description arm_6dof_ml
   source install/setup.bash
   ```

### Running the Simulation

#### Launch Gazebo Simulation with Monitoring:
```bash
ros2 launch arm_6dof_description simulation.launch.py
```

This command:
- Starts Gazebo with an empty world
- Loads the arm_6dof URDF model
- Spawns the robot in simulation
- Starts the joint_state_publisher
- Initializes the predictive maintenance monitor
- Launches RViz for visualization

#### In separate terminals:

**Monitor Degradation Predictions:**
```bash
ros2 topic echo /maintenance/degradation_levels
```

**Watch for Anomalies:**
```bash
ros2 topic echo /maintenance/anomalies
```

**View Maintenance Alerts:**
```bash
ros2 topic echo /maintenance/alerts
```

---

## 🧠 Machine Learning Model Training

### Training on Custom Data

```python
from predictive_maintenance import JointDegradationModel
import numpy as np

# Load your historical sensor data
X_train = np.load('historical_efforts.npy')  # [n_samples, 8 features]
y_train = np.load('degradation_labels.npy')   # [n_samples] - 0 to 1 scale

# Initialize and train model
model = JointDegradationModel()
model.train(X_train, y_train)

# Save trained model
model.save_model('path/to/degradation_model.pkl')
```

### Model Evaluation

```bash
python scripts/ml_model/data_analyzer.py \
  --log_dir ~/.ros/arm_6dof_logs \
  --output_dir ./analysis_results
```

---

## 📊 Real-Time Data Flow

```
┌─────────────────────────────────────────────────────┐
│         Gazebo Physics Simulation                    │
│  (Joint Positions, Velocities, Efforts)             │
└──────────────────────┬──────────────────────────────┘
                       │
                       ↓
         ┌─────────────────────────┐
         │  Joint State Publisher  │
         │   (ROS2 Topic)          │
         └──────────┬──────────────┘
                    │
      ┌─────────────┴──────────────┐
      │                            │
      ↓                            ↓
   ┌──────────────────┐    ┌──────────────────┐
   │ RViz Visual.     │    │ Feature Extractor│
   │ (Monitoring)     │    │ (8 Features)     │
   └──────────────────┘    └─────────┬────────┘
                                     │
                                     ↓
                        ┌────────────────────────┐
                        │  ML Ensemble Model     │
                        │  ├─ Anomaly Detection │
                        │  ├─ Degradation Pred. │
                        │  └─ Trend Analysis    │
                        └──────────┬─────────────┘
                                   │
                ┌──────────────────┼──────────────────┐
                ↓                  ↓                  ↓
        ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
        │ Degradation  │  │ Anomalies    │  │ Alerts       │
        │ Topic        │  │ Topic        │  │ Topic        │
        └──────────────┘  └──────────────┘  └──────────────┘
                                │
                                ↓
                        ┌──────────────────┐
                        │ Historical Logs  │
                        │ (~/.ros/logs)    │
                        └──────────────────┘
```

---

## 🔍 Monitoring & Diagnostics

### Published Topics

| Topic | Type | Frequency | Description |
|-------|------|-----------|-------------|
| `/joint_states` | sensor_msgs/JointState | 100 Hz | Joint state feedback |
| `/maintenance/degradation_levels` | std_msgs/Float32MultiArray | 10 Hz | Degradation per joint |
| `/maintenance/anomalies` | std_msgs/Int32MultiArray | 10 Hz | Anomaly flags (-1/+1) |
| `/maintenance/alerts` | std_msgs/String (JSON) | Event-driven | Maintenance alerts |

### Alert Message Format

```json
{
  "timestamp": "2024-01-15T14:30:45.123456",
  "severity": "CRITICAL",
  "message": "CRITICAL: joint_2 degradation at 87.5%. Schedule immediate maintenance."
}
```

### Log File Location

```
~/.ros/arm_6dof_logs/maintenance_log_YYYYMMDD_HHMMSS.json
~/.ros/arm_6dof_models/degradation_model.pkl
```

---

## 🎓 Master's Project Integration

This digital twin system demonstrates:

1. **Advanced Simulation** - Physics-based modeling with Gazebo
2. **Sensor Fusion** - Multi-modal data integration (effort, velocity, temperature)
3. **Machine Learning** - Ensemble methods for predictive maintenance
4. **Real-Time Systems** - ROS2 middleware for streaming data
5. **System Architecture** - Modular design for hardware integration

### Applications

- **Predictive Maintenance** - Reduce downtime through proactive intervention
- **Digital Twin Validation** - Compare sim vs. real-world data
- **Training & Research** - Platform for robotics & AI education
- **Industrial 4.0** - IoT-ready smart manufacturing system

---

## 📦 Dependencies

```
numpy>=1.21.0
scikit-learn>=1.0.0
rclpy>=0.12.0
sensor-msgs>=0.0.0
geometry-msgs>=0.0.0
gazebo-ros>=1.0.0
robot-state-publisher>=2.0.0
joint-state-publisher>=2.0.0
```

Install via:
```bash
pip install -r requirements.txt
```

---

## 🔄 Model Retraining Pipeline

For continuous improvement with real data:

```bash
# 1. Collect data during normal operation
# Logs automatically saved to ~/.ros/arm_6dof_logs/

# 2. Analyze collected data
python scripts/ml_model/data_analyzer.py --log_dir ~/.ros/arm_6dof_logs

# 3. Retrain model with new data
python scripts/ml_model/train_models.py \
  --input_logs ~/.ros/arm_6dof_logs \
  --output_model ~/.ros/arm_6dof_models/degradation_model_v2.pkl

# 4. Validate and deploy
python scripts/ml_model/validate_model.py \
  --model_path ~/.ros/arm_6dof_models/degradation_model_v2.pkl
```

---

## 📝 Code Standards

This project follows:
- **PEP 8** - Python style guide
- **ROS2 naming conventions** - For nodes, topics, services
- **Type hints** - For Python function signatures
- **Docstrings** - Google-style documentation

---

## 🐛 Troubleshooting

### Gazebo fails to load URDF
```bash
# Check URDF syntax
check_urdf arm_6dof.urdf.xacro

# Convert Xacro to URDF
xacro arm_6dof.urdf.xacro > arm_6dof.urdf
```

### Predictive maintenance node doesn't receive joint_states
```bash
# Verify joint_state_publisher is running
ros2 node list | grep joint_state

# Check topic availability
ros2 topic list | grep joint_states
```

### Model prediction gives all zeros
- Model is untrained. Train with historical data or wait for buffer to fill.
- Check feature extraction logic if running in simulation.

---

## 🔐 License

MIT License - See LICENSE file

---

## 📞 Contact & Support

**Project Lead:** Anukool Shidhore  
**Institution:** Rhode Island University - Master's Program  
**Email:** projects@example.com

For issues or contributions, open an issue in the repository.

---

## 🙏 Acknowledgments

- ROS2 and Gazebo communities
- Scikit-learn for ML algorithms
- Industrial robotics standards and best practices

---

**Last Updated:** March 2024  
**Status:** Active Development
