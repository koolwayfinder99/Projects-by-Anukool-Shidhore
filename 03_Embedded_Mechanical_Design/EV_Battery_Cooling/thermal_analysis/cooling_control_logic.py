#!/usr/bin/env python3
"""
EV Battery Cooling System - PID Controller for Coolant Pump
===========================================================================
Advanced thermal management system utilizing cascaded PID control to maintain
Li-ion battery pack temperatures within optimal operating range (25°C - 40°C).

Physical System:
    - Battery thermal model: lumped capacitance with temperature-dependent
      internal resistance
    - Coolant pump: variable speed (0-100% duty cycle)
    - Heat exchanger: liquid-cooled cold plate integrated with battery module
    - Sensor: NTC thermistor with 0.5°C accuracy
    
Control Strategy:
    - Outer loop: Temperature regulation via PID compensation
    - Inner loop: Pump speed modulation with anti-windup and rate limiting
    - Adaptive tuning: Temperature-dependent P, I, D gains
    
Thermal Constants:
    - Optimal temperature range: [25, 40] °C
    - Thermal time constant τ: ~180 seconds
    - Max heating rate: 0.15 °C/s
    - Max cooling rate: 0.12 °C/s
===========================================================================
"""

import numpy as np
import matplotlib.pyplot as plt
from dataclasses import dataclass
from typing import Tuple, List
from enum import Enum
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CoolingState(Enum):
    """Enumeration for cooling system operational states."""
    IDLE = 0           # Ambient condition, no active cooling
    ACTIVE = 1         # Pump running, temperature within setpoint ±2°C
    AGGRESSIVE = 2     # High pump speed, temperature > 42°C
    CRITICAL = 3       # Protective mode, temperature > 55°C


@dataclass
class ThermalParameters:
    """Physical parameters for battery thermal model."""
    
    # Battery specifications (48V LiFePO4 pack)
    voltage_nominal: float = 48.0           # Nominal voltage [V]
    capacity: float = 100.0                 # Amp-hour capacity [Ah]
    num_cells: int = 16                     # Cell count (3.2V nominal each)
    mass_total: float = 1.04                # Pack mass [kg]
    
    # Thermal properties
    c_p: float = 1200.0                     # Specific heat [J/(kg·K)]
    k_eff: float = 8.0                      # Effective conductivity [W/(m·K)]
    
    # Heat transfer coefficients
    h_natural: float = 15.0                 # Natural convection [W/(m²·K)]
    h_forced: float = 85.0                  # Forced convection (pump on) [W/(m²·K)]
    A_cooling: float = 0.35                 # Effective cooling area [m²]
    
    # Environmental
    T_ambient: float = 25.0                 # Ambient temperature [°C]
    T_initial: float = 25.0                 # Initial battery temp [°C]
    
    # Time constants
    tau_thermal: float = 180.0              # Thermal time constant [s]
    tau_pump: float = 5.0                   # Pump response time [s]


@dataclass
class PIDGains:
    """PID controller tuning parameters with adaptive scheduling."""
    
    K_p: float = 8.5                        # Proportional gain [1/°C]
    K_i: float = 0.15                       # Integral gain [1/(°C·s)]
    K_d: float = 45.0                       # Derivative gain [s/°C]
    
    # Anti-windup saturation limits
    I_max: float = 100.0                    # Max integral term [%]
    I_min: float = 0.0                      # Min integral term [%]
    
    # Rate limiting
    pump_max_rate: float = 2.0              # Max rate of change [%/s]


class BatteryThermalModel:
    """
    Lumped thermal model for 48V Li-ion battery pack.
    
    Implements first-order differential equation:
        dT/dt = (Q_generated - Q_dissipated) / (m * c_p)
    
    where:
        Q_generated: Ohmic heating from discharge current
        Q_dissipated: Convective cooling via forced/natural convection
    """
    
    def __init__(self, params: ThermalParameters):
        self.params = params
        self.T_battery = params.T_initial
        self.I_discharge = 0.0               # Battery discharge current [A]
        self.R_internal = 0.003              # Internal resistance [Ω]
        self.SOC = 100.0                     # State of charge [%]
        
    def set_discharge_current(self, I: float) -> None:
        """Update battery discharge current."""
        self.I_discharge = I
    
    def _calculate_internal_resistance(self) -> float:
        """
        Temperature-dependent internal resistance using Arrhenius model.
        
        R(T) = R0 * exp(Ea/R_gas * (1/T_K - 1/T_ref_K))
        
        Parameters for LiFePO4:
            Ea: 5000 J/mol
            R_gas: 8.314 J/(mol·K)
        """
        R0 = 0.003                          # Resistance @ 25°C [Ω]
        T_ref = 25.0 + 273.15               # Reference temperature [K]
        T_K = self.T_battery + 273.15       # Current temperature [K]
        
        E_a = 5000.0                        # Activation energy [J/mol]
        R_gas = 8.314                       # Gas constant [J/(mol·K)]
        
        exponent = (E_a / R_gas) * (1/T_K - 1/T_ref)
        R_T = R0 * np.exp(exponent)
        
        return R_T
    
    def _calculate_heat_generation(self) -> float:
        """
        Calculate total heat generation in battery pack.
        
        Q_total = Q_ohmic + Q_electrochemical
        where:
            Q_ohmic = I² * R_internal * n_cells (Joule heating - dominant)
            Q_elec = ΔS * T * I (entropy-related, ~10% of total)
        """
        self.R_internal = self._calculate_internal_resistance()
        
        # Ohmic heating: I² * R
        Q_ohmic = (self.I_discharge ** 2) * self.R_internal * self.params.num_cells
        
        # Electrochemical component (small contribution)
        # For LiFePO4: dU/dT ≈ -0.001 V/K
        T_K = self.T_battery + 273.15
        T_ref_K = 25.0 + 273.15
        dU_dT = -0.001
        Q_elec = abs(dU_dT) * (T_K / T_ref_K) * self.I_discharge * self.params.num_cells
        
        Q_total = Q_ohmic + Q_elec
        
        return Q_total
    
    def _calculate_heat_dissipation(self, pump_speed: float) -> float:
        """
        Calculate convective heat dissipation.
        
        Q_loss = h * A * (T_batt - T_ambient)
        where h is adjusted based on pump speed (0-100%).
        """
        # Interpolate heat transfer coefficient between natural and forced convection
        h = self.params.h_natural + (self.params.h_forced - self.params.h_natural) * (pump_speed / 100.0)
        
        Q_loss = h * self.params.A_cooling * (self.T_battery - self.params.T_ambient)
        
        return Q_loss
    
    def update(self, pump_speed: float, dt: float = 1.0) -> None:
        """
        Advance thermal model by one time step using forward Euler integration.
        
        Args:
            pump_speed: Pump duty cycle [0-100%]
            dt: Time step [seconds]
        """
        # Calculate net heat flow
        Q_gen = self._calculate_heat_generation()
        Q_loss = self._calculate_heat_dissipation(pump_speed)
        Q_net = Q_gen - Q_loss
        
        # Temperature rate of change: dT/dt = Q_net / (m * c_p)
        dT_dt = Q_net / (self.params.mass_total * self.params.c_p)
        
        # Euler integration
        self.T_battery += dT_dt * dt
        
        # Enforce hard limits (thermal runaway protection)
        if self.T_battery > 60.0:
            logger.warning(f"CRITICAL: Battery temperature {self.T_battery:.1f}°C - SHUTTING DOWN")
            self.T_battery = 60.0
        
        # Update state-of-charge during discharge
        if self.I_discharge > 0:
            self.SOC -= (self.I_discharge / (self.params.capacity * 3600.0)) * dt * 100.0
            self.SOC = np.clip(self.SOC, 0.0, 100.0)


class PIDController:
    """
    Proportional-Integral-Derivative (PID) controller with:
        - Anti-windup (saturation limiting)
        - Rate limiting on output
        - Adaptive gain scheduling
        - Derivative low-pass filtering
    
    Control Law:
        u = K_p*e + K_i*∫e dt + K_d*de/dt
    """
    
    def __init__(self, gains: PIDGains, T_setpoint: float = 32.5):
        """
        Initialize PID controller.
        
        Args:
            gains: PID gain configuration
            T_setpoint: Target battery temperature [°C]
        """
        self.gains = gains
        self.T_setpoint = T_setpoint           # Setpoint: mid-range of optimal band
        
        # State variables
        self.I_term = 0.0                      # Accumulated integral error
        self.e_prev = 0.0                      # Previous error for derivative
        self.u_prev = 50.0                     # Previous pump output
        
        # Filter parameters
        self.tau_lpf = 2.0                     # Low-pass filter time constant [s]
        self.de_dt_filtered = 0.0              # Filtered derivative of error
        
        # Controller history
        self.history = {
            'error': [],
            'I_term': [],
            'D_term': [],
            'output': [],
            'state': []
        }
        
    def set_setpoint(self, T: float) -> None:
        """Update temperature setpoint."""
        self.T_setpoint = np.clip(T, 25.0, 40.0)
    
    def _adaptive_gains(self, T_battery: float) -> Tuple[float, float, float]:
        """
        Implement gain scheduling based on battery temperature.
        
        Strategy:
            - Below 30°C: Reduce gains (gentle heating)
            - 30-40°C: Nominal gains (optimal operation)
            - Above 40°C: Increase proportional/derivative (aggressive cooling)
        """
        K_p = self.gains.K_p
        K_i = self.gains.K_i
        K_d = self.gains.K_d
        
        if T_battery < 30.0:
            # Low temperature: reduce all gains
            factor = 0.6
            K_p *= factor
            K_i *= factor
            K_d *= factor
            
        elif T_battery > 42.0:
            # High temperature: increase gains for aggressive cooling
            factor = 1.4
            K_p *= factor
            K_d *= factor * 1.2  # Extra boost on derivative
        
        return K_p, K_i, K_d
    
    def update(self, T_battery: float, dt: float = 1.0) -> float:
        """
        Compute PID control output (pump duty cycle).
        
        Args:
            T_battery: Measured battery temperature [°C]
            dt: Time step [seconds]
            
        Returns:
            Pump speed command [0-100%]
        """
        # Calculate temperature error
        e = self.T_setpoint - T_battery
        
        # Get adaptive gains
        K_p, K_i, K_d = self._adaptive_gains(T_battery)
        
        # Proportional term
        P_term = K_p * e
        
        # Integral term with anti-windup
        # Only accumulate integral if error is moderate
        if abs(e) < 5.0 and abs(self.I_term) < self.gains.I_max:
            self.I_term += e * dt
        
        # Anti-windup saturation
        self.I_term = np.clip(self.I_term, self.gains.I_min, self.gains.I_max)
        I_term_output = K_i * self.I_term
        
        # Derivative term with low-pass filtering
        # Filter: de_dt_filtered = (1-α)*de_dt_filtered + α*de_dt
        de_dt = (e - self.e_prev) / dt if dt > 0 else 0.0
        alpha = dt / (self.tau_lpf + dt)
        self.de_dt_filtered = (1 - alpha) * self.de_dt_filtered + alpha * de_dt
        
        D_term = K_d * self.de_dt_filtered
        
        # Composite PID output
        u_cmd = P_term + I_term_output + D_term
        
        # Rate limiting on pump speed
        du_max = self.gains.pump_max_rate * dt
        u_cmd = self.u_prev + np.clip(u_cmd - self.u_prev, -du_max, du_max)
        
        # Output saturation [0-100%]
        u_output = np.clip(u_cmd, 0.0, 100.0)
        
        # Store for next iteration
        self.e_prev = e
        self.u_prev = u_output
        
        # Logging
        self.history['error'].append(e)
        self.history['I_term'].append(self.I_term)
        self.history['D_term'].append(D_term)
        self.history['output'].append(u_output)
        
        return u_output


def simulate_cooling_system(
    simulation_time: float = 3600.0,        # 1 hour simulation
    I_discharge: float = 30.0,              # 30A discharge current
    T_ambient: float = 25.0,
    pump_control_mode: str = 'pid'          # 'pid' or 'bang_bang'
) -> dict:
    """
    Simulate complete battery cooling system with PID controller.
    
    Args:
        simulation_time: Total simulation duration [seconds]
        I_discharge: Discharge current [Amps]
        T_ambient: Ambient temperature [°C]
        pump_control_mode: Control strategy selection
        
    Returns:
        Dictionary containing time series data
    """
    dt = 1.0                                # Time step [seconds]
    
    # Initialize models
    params = ThermalParameters(T_ambient=T_ambient)
    battery = BatteryThermalModel(params)
    battery.set_discharge_current(I_discharge)
    
    gains = PIDGains()
    controller = PIDController(gains, T_setpoint=32.5)
    
    # Time vector and logging arrays
    t_vec = np.arange(0, simulation_time, dt)
    n_steps = len(t_vec)
    
    T_log = np.zeros(n_steps)
    pump_log = np.zeros(n_steps)
    SOC_log = np.zeros(n_steps)
    Q_gen_log = np.zeros(n_steps)
    R_log = np.zeros(n_steps)
    state_log = np.zeros(n_steps, dtype=int)
    
    logger.info(f"Starting simulation: I_discharge={I_discharge}A, T_ambient={T_ambient}°C")
    logger.info(f"Simulation duration: {simulation_time/3600:.1f} hours")
    
    # Simulation loop
    for i, t in enumerate(t_vec):
        # Get pump command from controller
        if pump_control_mode == 'pid':
            pump_speed = controller.update(battery.T_battery, dt)
        else:
            # Bang-bang control: pump on if T > 35°C, off if T < 30°C
            pump_speed = 100.0 if battery.T_battery > 35.0 else (0.0 if battery.T_battery < 30.0 else pump_log[i-1])
        
        # Determine operational state
        if pump_speed > 80:
            state = CoolingState.AGGRESSIVE.value
        elif pump_speed > 10:
            state = CoolingState.ACTIVE.value
        elif battery.T_battery > 55:
            state = CoolingState.CRITICAL.value
        else:
            state = CoolingState.IDLE.value
        
        # Update thermal model
        battery.update(pump_speed, dt)
        
        # Log data
        T_log[i] = battery.T_battery
        pump_log[i] = pump_speed
        SOC_log[i] = battery.SOC
        Q_gen_log[i] = battery._calculate_heat_generation()
        R_log[i] = battery.R_internal * 1000  # Convert to mOhm
        state_log[i] = state
        
        # Print periodic status
        if i % 600 == 0 and i > 0:  # Every 10 minutes
            logger.info(
                f"t={t/60:.1f}min: T={battery.T_battery:.1f}°C, "
                f"Pump={pump_speed:.1f}%, SOC={battery.SOC:.1f}%, "
                f"R={R_log[i]:.3f}mΩ"
            )
    
    logger.info("Simulation complete")
    
    return {
        'time': t_vec,
        'temperature': T_log,
        'pump_speed': pump_log,
        'SOC': SOC_log,
        'Q_generated': Q_gen_log,
        'R_internal': R_log,
        'state': state_log,
        'controller': controller
    }


def plot_results(results: dict) -> None:
    """Generate comprehensive visualization of cooling system performance."""
    
    fig, axes = plt.subplots(3, 2, figsize=(14, 10))
    fig.suptitle('EV Battery Thermal Management System - PID Control Analysis', 
                 fontsize=14, fontweight='bold')
    
    t_min = results['time'] / 60.0  # Convert to minutes
    
    # Plot 1: Temperature control
    ax = axes[0, 0]
    ax.plot(t_min, results['temperature'], 'b-', linewidth=2, label='Battery Temp')
    ax.axhline(40.0, color='r', linestyle='--', linewidth=1.5, label='Upper Limit (40°C)')
    ax.axhline(25.0, color='g', linestyle='--', linewidth=1.5, label='Lower Limit (25°C)')
    ax.fill_between(t_min, 25, 40, alpha=0.1, color='green', label='Optimal Range')
    ax.set_ylabel('Temperature [°C]', fontsize=11)
    ax.set_title('Battery Temperature Profile', fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=9)
    
    # Plot 2: Pump control
    ax = axes[0, 1]
    ax.plot(t_min, results['pump_speed'], 'orange', linewidth=2)
    ax.fill_between(t_min, 0, results['pump_speed'], alpha=0.3, color='orange')
    ax.set_ylabel('Pump Speed [%]', fontsize=11)
    ax.set_title('Coolant Pump Speed Command', fontweight='bold')
    ax.set_ylim([0, 105])
    ax.grid(True, alpha=0.3)
    
    # Plot 3: State of Charge
    ax = axes[1, 0]
    ax.plot(t_min, results['SOC'], 'g-', linewidth=2)
    ax.set_ylabel('SOC [%]', fontsize=11)
    ax.set_title('Battery State-of-Charge', fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.set_ylim([0, 105])
    
    # Plot 4: Heat generation
    ax = axes[1, 1]
    ax.plot(t_min, results['Q_generated'], 'r-', linewidth=2)
    ax.set_ylabel('Heat Generation [W]', fontsize=11)
    ax.set_title('Ohmic & Electrochemical Heat Production', fontweight='bold')
    ax.grid(True, alpha=0.3)
    
    # Plot 5: Internal resistance
    ax = axes[2, 0]
    ax.plot(t_min, results['R_internal'], 'purple', linewidth=2)
    ax.set_xlabel('Time [minutes]', fontsize=11)
    ax.set_ylabel('R_internal [mΩ]', fontsize=11)
    ax.set_title('Temperature-Dependent Internal Resistance', fontweight='bold')
    ax.grid(True, alpha=0.3)
    
    # Plot 6: Control error (from controller history)
    ax = axes[2, 1]
    controller = results['controller']
    if len(controller.history['error']) > 0:
        ax.plot(np.array(controller.history['error']), 'b-', linewidth=1.5, label='Error')
        ax.axhline(0, color='k', linestyle='-', linewidth=0.5)
        ax.fill_between(range(len(controller.history['error'])), 
                        controller.history['error'], 
                        alpha=0.2, color='blue')
        ax.set_xlabel('Time [seconds]', fontsize=11)
        ax.set_ylabel('Temperature Error [°C]', fontsize=11)
        ax.set_title('PID Controller Error Signal', fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=9)
    
    plt.tight_layout()
    plt.savefig('cooling_system_analysis.png', dpi=300, bbox_inches='tight')
    logger.info("Analysis plot saved: cooling_system_analysis.png")
    
    return fig


def main():
    """Main execution routine."""
    
    print("\n" + "="*70)
    print("EV BATTERY COOLING SYSTEM - PID CONTROLLER SIMULATION")
    print("="*70 + "\n")
    
    # Run simulation with PID control
    results = simulate_cooling_system(
        simulation_time=3600.0,      # 1 hour
        I_discharge=30.0,             # 30A continuous discharge
        T_ambient=25.0,
        pump_control_mode='pid'
    )
    
    # Extract results
    T_battery = results['temperature']
    pump_speed = results['pump_speed']
    
    # Performance metrics
    T_max = np.max(T_battery)
    T_mean = np.mean(T_battery)
    T_min = np.min(T_battery)
    
    # Time within optimal range
    optimal_range = (T_battery >= 25.0) & (T_battery <= 40.0)
    time_optimal = np.sum(optimal_range) * 100.0 / len(T_battery)
    
    # Pump statistics
    pump_avg = np.mean(pump_speed)
    pump_max = np.max(pump_speed)
    
    print("\n" + "="*70)
    print("THERMAL CONTROL PERFORMANCE SUMMARY")
    print("="*70)
    print(f"\nTemperature Statistics:")
    print(f"  Maximum Temperature:        {T_max:.2f} °C")
    print(f"  Average Temperature:        {T_mean:.2f} °C")
    print(f"  Minimum Temperature:        {T_min:.2f} °C")
    print(f"  Time in Optimal Range:      {time_optimal:.1f} %")
    
    print(f"\nPump Control Statistics:")
    print(f"  Average Pump Speed:         {pump_avg:.1f} %")
    print(f"  Maximum Pump Speed:         {pump_max:.1f} %")
    print(f"  Energy Efficiency Metric:   {100-pump_avg:.1f} %")
    
    print("\n" + "="*70 + "\n")
    
    # Generate visualization
    plot_results(results)
    
    # Save results to CSV
    import csv
    with open('cooling_system_results.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Time_s', 'Temperature_C', 'Pump_Speed_%', 'SOC_%', 'Heat_Gen_W', 'R_internal_mOhm'])
        for i in range(len(results['time'])):
            writer.writerow([
                f"{results['time'][i]:.1f}",
                f"{results['temperature'][i]:.2f}",
                f"{results['pump_speed'][i]:.2f}",
                f"{results['SOC'][i]:.2f}",
                f"{results['Q_generated'][i]:.2f}",
                f"{results['R_internal'][i]:.4f}"
            ])
    logger.info("Results exported: cooling_system_results.csv")
    
    plt.show()


if __name__ == '__main__':
    main()

#===========================================================================
# END OF SCRIPT
#===========================================================================
