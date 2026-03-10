#!/usr/bin/env python3
"""
State-of-Charge (SoC) Estimation Module for E-BAJA Battery Management System

Implements dual estimation methods for robust battery SoC prediction:
1. Extended Kalman Filter (EKF) - for sensor fusion with voltage/current noise
2. Coulomb Counting - for baseline ampere-hour integration tracking

This module reflects thesis research on Battery Management Systems for
high-performance off-road electric vehicles (E-BAJA transition).

Author: Formula Student BAJA Dynamics Team
Date: March 2026
"""

import numpy as np
from dataclasses import dataclass
from typing import Tuple, Dict, Optional
from enum import Enum
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EstimationMethod(Enum):
    """Available SoC estimation algorithms"""
    COULOMB_COUNTING = "coulomb_counting"
    EXTENDED_KALMAN_FILTER = "ekf"
    HYBRID = "hybrid"  # Combines both methods


@dataclass
class BatteryParameters:
    """
    Battery cell and pack specifications for E-BAJA vehicle
    
    Represents: 48V LiFePO4 battery pack (4S8P configuration)
    - Nominal voltage: 48V
    - Nominal capacity: 20 Ah
    - Chemistry: LiFePO4 (safe for off-road motorsports)
    """
    nominal_voltage: float = 48.0  # volts
    nominal_capacity: float = 20.0  # amp-hours (Ah)
    num_cells_series: int = 4  # 4S configuration
    num_cells_parallel: int = 8  # 8P configuration
    cell_nominal_voltage: float = 3.2  # volts per cell (LiFePO4)
    min_cell_voltage: float = 2.5  # volts (discharge cutoff)
    max_cell_voltage: float = 3.65  # volts (charge cutoff)
    internal_resistance: float = 0.05  # ohms (pack resistance)
    self_discharge_rate: float = 0.001  # per hour (0.1%)
    
    @property
    def min_pack_voltage(self) -> float:
        """Minimum safe pack voltage"""
        return self.min_cell_voltage * self.num_cells_series
    
    @property
    def max_pack_voltage(self) -> float:
        """Maximum pack voltage"""
        return self.max_cell_voltage * self.num_cells_series
    
    @property
    def usable_energy(self) -> float:
        """Usable energy in kWh"""
        return (self.nominal_voltage * self.nominal_capacity) / 1000.0


class CoulombCounter:
    """
    Coulomb Counting Algorithm for SoC Estimation
    
    Simple, robust method that integrates current over time to track
    charge consumed/restored. Baseline approach suitable for BMS.
    
    Advantages:
    - No complex modeling required
    - Fast computation
    - Predictable behavior
    
    Disadvantages:
    - Drift accumulation over time (requires periodic calibration)
    - Sensitive to current measurement accuracy
    - Doesn't account for voltage dynamics
    """
    
    def __init__(self, battery: BatteryParameters, initial_soc: float = 0.95):
        """
        Initialize Coulomb Counter
        
        Args:
            battery: BatteryParameters object
            initial_soc: Initial state of charge (0.0 to 1.0)
        """
        self.battery = battery
        self.soc = initial_soc
        self.charge_integrated = 0.0  # Ah (accumulated)
        self.soc_history = [initial_soc]
        
        logger.info(f"Coulomb Counter initialized with SoC={initial_soc:.2%}")
    
    def update(self, current: float, dt: float) -> float:
        """
        Update SoC using Coulomb Counting
        
        Args:
            current: Battery current in Amps (positive = discharge)
            dt: Time step in seconds
        
        Returns:
            Updated SoC (0.0 to 1.0)
        """
        # Convert current and time to ampere-hours
        dq = (current * dt) / 3600.0  # Ah
        
        # Accumulate charge integrated
        self.charge_integrated += dq
        
        # Calculate SoC change
        # SoC_change = -dQ / Q_nominal (negative because discharge reduces SoC)
        soc_change = -dq / self.battery.nominal_capacity
        
        # Update SoC
        self.soc = max(0.0, min(1.0, self.soc + soc_change))
        
        # Account for self-discharge
        self_discharge_loss = self.battery.self_discharge_rate * (dt / 3600.0)
        self.soc *= (1.0 - self_discharge_loss)
        
        # Clamp SoC
        self.soc = max(0.0, min(1.0, self.soc))
        
        self.soc_history.append(self.soc)
        
        return self.soc
    
    def reset_to_full(self):
        """Recalibrate SoC to 100% (performed at full charge)"""
        self.soc = 1.0
        self.charge_integrated = 0.0
        logger.info("SoC calibrated to 100% (full charge)")
    
    def get_soc(self) -> float:
        """Get current SoC estimate"""
        return self.soc


class ExtendedKalmanFilterSoC:
    """
    Extended Kalman Filter for SoC Estimation
    
    Fuses voltage and current measurements for robust SoC tracking.
    Models battery as RC circuit with voltage-dependent behavior.
    
    State Vector: [SoC, V_oc, V_rc]
    - SoC: State of charge (0-1)
    - V_oc: Open circuit voltage
    - V_rc: Resistor-capacitor branch voltage
    
    Advantages:
    - Handles sensor noise effectively
    - Provides uncertainty estimates (covariance)
    - Self-correcting (doesn't drift indefinitely)
    - Superior performance in dynamic conditions
    
    Disadvantages:
    - Requires parameter identification (model tuning)
    - Higher computational cost
    - More complex implementation
    """
    
    def __init__(self, battery: BatteryParameters, initial_soc: float = 0.95):
        """
        Initialize Extended Kalman Filter
        
        Args:
            battery: BatteryParameters object
            initial_soc: Initial SoC estimate (0.0 to 1.0)
        """
        self.battery = battery
        
        # State vector: [SoC, V_oc, V_rc]
        self.x = np.array([initial_soc, initial_soc * battery.nominal_voltage, 0.0])
        
        # State covariance matrix (uncertainty in each state)
        self.P = np.diag([0.0001, 0.01, 0.01])
        
        # Process noise covariance (model uncertainty)
        self.Q = np.diag([1e-5, 1e-4, 1e-4])
        
        # Measurement noise covariance (sensor noise)
        # Voltage sensor: ±0.05V, Current sensor: ±1A
        self.R = np.diag([0.0025, 1.0])  # [V_measured^2, I_measured^2]
        
        # Battery model parameters (identified from testing)
        self.R_ohmic = 0.05  # Ohmic resistance (ohms)
        self.R_polarization = 0.02  # Polarization resistance
        self.C_polarization = 2000.0  # Polarization capacitance (farads)
        self.tau = self.R_polarization * self.C_polarization  # Time constant
        
        # OCV (Open Circuit Voltage) lookup table vs SoC
        # For LiFePO4: nearly flat discharge curve
        self.ocv_soc = np.array([0.0, 0.2, 0.4, 0.6, 0.8, 1.0])
        self.ocv_voltage = np.array([46.4, 47.2, 47.8, 48.2, 48.6, 49.2])
        
        self.soc_history = [initial_soc]
        self.voltage_estimated = [self.x[1]]
        
        logger.info(f"Extended Kalman Filter initialized with SoC={initial_soc:.2%}")
    
    def get_ocv(self, soc: float) -> float:
        """
        Get open circuit voltage from SoC using lookup table
        
        Args:
            soc: State of charge (0.0 to 1.0)
        
        Returns:
            Open circuit voltage (volts)
        """
        # Linear interpolation
        ocv = np.interp(soc, self.ocv_soc, self.ocv_voltage)
        return ocv
    
    def predict(self, current: float, dt: float) -> None:
        """
        EKF Predict Step: Propagate state and covariance
        
        Args:
            current: Battery current (Amps, positive = discharge)
            dt: Time step (seconds)
        """
        # State transition function
        # SoC_new = SoC_old - (I * dt) / Q_nominal
        # V_oc_new = f(SoC_new) - Depends on OCV curve
        # V_rc_new = V_rc_old * exp(-dt/tau) - Polarization voltage decay
        
        soc_old = self.x[0]
        v_rc_old = self.x[2]
        
        # Update SoC
        delta_soc = -(current * dt) / (3600.0 * self.battery.nominal_capacity)
        soc_new = max(0.0, min(1.0, soc_old + delta_soc))
        
        # Update open circuit voltage based on new SoC
        v_oc_new = self.get_ocv(soc_new)
        
        # Exponential decay of polarization voltage
        v_rc_new = v_rc_old * np.exp(-dt / self.tau)
        
        # Update state
        self.x = np.array([soc_new, v_oc_new, v_rc_new])
        
        # Jacobian of state transition (linearized for EKF)
        F = np.eye(3)
        F[0, 0] = 1.0  # SoC doesn't depend on other states
        F[1, 0] = 0.05  # dV_oc/dSoC ≈ 0.05 V per 10% SoC (LiFePO4 curve)
        F[2, 2] = np.exp(-dt / self.tau)  # Exponential decay factor
        
        # Covariance prediction: P = F * P * F^T + Q
        self.P = F @ self.P @ F.T + self.Q
    
    def update(self, v_measured: float, i_measured: float) -> float:
        """
        EKF Update Step: Correct state using voltage and current measurements
        
        Args:
            v_measured: Measured pack voltage (volts)
            i_measured: Measured current (amps)
        
        Returns:
            Updated SoC estimate
        """
        # Measurement model
        # V_measured = V_oc + V_rc + I * R
        # [V_measured, I_measured]
        
        soc = self.x[0]
        v_oc = self.x[1]
        v_rc = self.x[2]
        
        # Expected measurements (innovations reference)
        v_pred = v_oc + v_rc + i_measured * self.R_ohmic
        
        # Measurement residual (innovation)
        y = np.array([v_measured - v_pred, i_measured])
        
        # Measurement matrix H (how states affect measurements)
        H = np.array([
            [0.05, 1.0, 1.0],  # Voltage depends on V_oc and V_rc
            [0.0, 0.0, 0.0]    # Current measurement is independent
        ])
        
        # Innovation covariance: S = H * P * H^T + R
        S = H @ self.P @ H.T + self.R
        
        # Kalman gain: K = P * H^T * S^-1
        K = self.P @ H.T @ np.linalg.inv(S)
        
        # State update: x = x + K * y
        self.x += K @ y
        
        # Clamp SoC
        self.x[0] = max(0.0, min(1.0, self.x[0]))
        
        # Covariance update: P = (I - K * H) * P
        I = np.eye(3)
        self.P = (I - K @ H) @ self.P
        
        self.soc_history.append(self.x[0])
        self.voltage_estimated.append(self.x[1])
        
        return self.x[0]
    
    def get_soc(self) -> float:
        """Get current SoC estimate"""
        return self.x[0]
    
    def get_uncertainty(self) -> float:
        """Get SoC estimation uncertainty (1-sigma in %SoC)"""
        return np.sqrt(self.P[0, 0]) * 100.0


class HybridSoCEstimator:
    """
    Hybrid SoC Estimator combining Coulomb Counting and EKF
    
    Strategy:
    - Use EKF as primary estimator (superior noise handling)
    - Use Coulomb Counting for drift detection and correction
    - Periodical recalibration at charge/discharge endpoints
    
    Provides best-of-both-worlds: Robustness + Fast convergence
    """
    
    def __init__(self, battery: BatteryParameters, initial_soc: float = 0.95):
        """Initialize hybrid estimator"""
        self.battery = battery
        self.ekf = ExtendedKalmanFilterSoC(battery, initial_soc)
        self.coulomb = CoulombCounter(battery, initial_soc)
        
        # Weighting parameters
        self.ekf_weight = 0.7  # EKF has higher weight (more reliable)
        self.coulomb_weight = 0.3  # Coulomb counter for drift correction
        
        self.soc_fused = initial_soc
        logger.info("Hybrid SoC Estimator initialized")
    
    def update(self, current: float, voltage: float, dt: float) -> float:
        """
        Update hybrid SoC estimate
        
        Args:
            current: Battery current (Amps)
            voltage: Measured voltage (Volts)
            dt: Time step (seconds)
        
        Returns:
            Fused SoC estimate
        """
        # Update both estimators
        self.ekf.predict(current, dt)
        soc_ekf = self.ekf.update(voltage, current)
        
        soc_coulomb = self.coulomb.update(current, dt)
        
        # Weighted fusion
        self.soc_fused = (self.ekf_weight * soc_ekf + 
                         self.coulomb_weight * soc_coulomb)
        
        # Clamp result
        self.soc_fused = max(0.0, min(1.0, self.soc_fused))
        
        return self.soc_fused
    
    def get_soc(self) -> Dict[str, float]:
        """Get all SoC estimates and fused result"""
        return {
            'soc_ekf': self.ekf.get_soc(),
            'soc_coulomb': self.coulomb.get_soc(),
            'soc_fused': self.soc_fused,
            'uncertainty': self.ekf.get_uncertainty()
        }
    
    def reset_to_full(self):
        """Recalibrate at full charge"""
        self.ekf.x[0] = 1.0
        self.coulomb.reset_to_full()
        self.soc_fused = 1.0


class BatteryManagementSystem:
    """
    Complete Battery Management System for E-BAJA vehicle
    
    Integrates SoC estimation with power management, thermal monitoring,
    and safety algorithms.
    """
    
    def __init__(self, battery: BatteryParameters = None, 
                 method: EstimationMethod = EstimationMethod.HYBRID):
        """
        Initialize BMS
        
        Args:
            battery: BatteryParameters (uses default if None)
            method: Estimation method to use
        """
        self.battery = battery or BatteryParameters()
        self.method = method
        
        # Initialize estimator based on method
        if method == EstimationMethod.COULOMB_COUNTING:
            self.estimator = CoulombCounter(self.battery)
        elif method == EstimationMethod.EXTENDED_KALMAN_FILTER:
            self.estimator = ExtendedKalmanFilterSoC(self.battery)
        else:  # HYBRID
            self.estimator = HybridSoCEstimator(self.battery)
        
        # Safety thresholds
        self.min_safe_soc = 0.05  # Don't discharge below 5%
        self.max_safe_soc = 0.95  # Don't charge above 95% (longevity)
        self.critical_discharge_threshold = 0.02
        
        # Performance metrics
        self.total_charge_cycles = 0
        self.total_energy_delivered = 0.0  # kWh
        
        logger.info(f"BMS initialized with {method.value} estimator")
    
    def update(self, current: float, voltage: float, dt: float) -> Dict:
        """
        Perform BMS update cycle
        
        Args:
            current: Battery current (Amps)
            voltage: Measured pack voltage (Volts)
            dt: Time step (seconds)
        
        Returns:
            Dictionary with BMS state and alarms
        """
        # Update SoC estimate
        if self.method == EstimationMethod.HYBRID:
            soc_result = self.estimator.update(current, voltage, dt)
            soc_estimates = self.estimator.get_soc()
        elif self.method == EstimationMethod.EXTENDED_KALMAN_FILTER:
            self.estimator.predict(current, dt)
            soc_result = self.estimator.update(voltage, current)
            soc_estimates = {
                'soc': soc_result,
                'uncertainty': self.estimator.get_uncertainty()
            }
        else:  # COULOMB_COUNTING
            soc_result = self.estimator.update(current, dt)
            soc_estimates = {'soc': soc_result}
        
        # Calculate energy delivered (for trip/session tracking)
        if current > 0:  # Discharging
            energy_delivered = (current * self.battery.nominal_voltage * dt) / 3600000.0
            self.total_energy_delivered += energy_delivered
        
        # Charge cycle detection
        if current > 0:  # Discharge detected
            self.total_charge_cycles += 0.5 / 3600.0  # Fractional cycle counting
        
        # Safety checks
        alarms = self._check_safety_limits(soc_result, voltage)
        
        return {
            'soc': soc_result,
            'soc_estimates': soc_estimates,
            'voltage': voltage,
            'current': current,
            'power': current * voltage,
            'energy_delivered_session': self.total_energy_delivered,
            'cycle_count': self.total_charge_cycles,
            'alarms': alarms,
            'timestamp': np.datetime64('now')
        }
    
    def _check_safety_limits(self, soc: float, voltage: float) -> Dict[str, bool]:
        """Check battery safety limits"""
        return {
            'over_voltage': voltage > self.battery.max_pack_voltage,
            'under_voltage': voltage < self.battery.min_pack_voltage,
            'over_discharge': soc < self.min_safe_soc,
            'over_charge': soc > self.max_safe_soc,
            'critical': soc < self.critical_discharge_threshold,
        }


def simulate_bms_cycle():
    """
    Demonstration: Simulate E-BAJA vehicle power cycle
    
    Scenario: 30-minute off-road circuit with varying power demand
    """
    print("\n" + "="*70)
    print("E-BAJA Battery Management System Simulation")
    print("="*70)
    
    # Initialize BMS with hybrid estimator
    bms = BatteryManagementSystem(method=EstimationMethod.HYBRID)
    
    # Simulate driving profile (acceleration, sustained load, braking)
    time_points = np.linspace(0, 1800, 180)  # 30 minutes, 180 samples (10Hz)
    
    # Dynamic load profile (sinusoidal with peaks for acceleration)
    base_current = 40.0  # Amps (baseline cruise)
    current_trace = base_current + 20.0 * np.sin(2 * np.pi * time_points / 300) + \
                   15.0 * np.sin(2 * np.pi * time_points / 60)  # Peak loads
    
    # Voltage under load (drops with current)
    voltage_trace = 48.0 - 0.02 * np.abs(current_trace) + np.random.normal(0, 0.1, len(current_trace))
    
    print("\nSimulation Parameters:")
    print(f"  Duration: 30 minutes")
    print(f"  Battery: {bms.battery.nominal_voltage}V, {bms.battery.nominal_capacity}Ah")
    print(f"  Chemistry: LiFePO4 ({bms.battery.num_cells_series}S{bms.battery.num_cells_parallel}P)")
    print(f"  Usable Energy: {bms.battery.usable_energy:.2f} kWh")
    
    # Simulation loop
    results = []
    for i in range(len(time_points)):
        dt = 10.0 if i == 0 else time_points[i] - time_points[i-1]
        
        current = current_trace[i]
        voltage = voltage_trace[i]
        
        bms_state = bms.update(current, voltage, dt)
        results.append(bms_state)
    
    # Results summary
    print("\nSimulation Results:")
    print(f"  Initial SoC: {results[0]['soc']:.2%}")
    print(f"  Final SoC: {results[-1]['soc']:.2%}")
    print(f"  Energy Delivered: {results[-1]['energy_delivered_session']:.3f} kWh")
    print(f"  Charge Cycles: {results[-1]['cycle_count']:.2f}")
    print(f"  Average Power: {np.mean([r['power'] for r in results]):.1f} W")
    print(f"  Peak Power: {np.max([r['power'] for r in results]):.1f} W")
    
    # Estimation accuracy
    if isinstance(bms.estimator, HybridSoCEstimator):
        final_uncertainty = results[-1]['soc_estimates']['uncertainty']
        print(f"  Final Uncertainty: ±{final_uncertainty:.2f}%")
    
    # Warnings
    critical_events = sum([1 for r in results if r['alarms']['critical']])
    if critical_events > 0:
        print(f"  ⚠️  Critical discharge events: {critical_events}")
    
    print("\n" + "="*70)


if __name__ == "__main__":
    # Run simulation demonstration
    simulate_bms_cycle()
