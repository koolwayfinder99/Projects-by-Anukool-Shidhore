"""
Intermediate Temperature Solid Oxide Fuel Cell (IT-SOFC)
Exhaust Energy Recovery System

This module calculates the theoretical electrical energy that can be generated
by an IT-SOFC system from ATV exhaust gases, enabling sustainable energy harvesting
and emission reduction through advanced thermodynamic processes.

Author: Sustainable Design Engineer
Purpose: Repurpose exhaust thermal and chemical energy for auxiliary power generation
"""

import numpy as np
import scipy.integrate as integrate
from scipy.interpolate import interp1d
from dataclasses import dataclass
from typing import Tuple, Dict
import warnings


@dataclass
class ExhaustGasProperties:
    """Properties of ATV exhaust gas stream."""
    mass_flow_rate: float  # kg/s
    inlet_temperature: float  # K
    outlet_temperature: float  # K
    co_concentration: float  # ppm (parts per million)
    nox_concentration: float  # ppm
    hydrogen_concentration: float  # % by volume (potential if reformed)
    pressure: float  # atm


@dataclass
class IT_SOFCParameters:
    """Operating parameters for IT-SOFC system."""
    operating_temperature: float  # K (typically 700-800 K)
    fuel_utilization: float  # % (0-1)
    electrical_efficiency: float  # % (0-1)
    open_circuit_voltage: float  # V
    current_density: float  # A/cm^2
    cell_area: float  # cm^2


class ExhaustEnergyRecovery:
    """
    Calculates electrical energy generation and emission reduction
    from IT-SOFC utilizing ATV exhaust gases.
    """
    
    # Thermodynamic constants
    UNIVERSAL_GAS_CONSTANT = 8.314  # J/(mol·K)
    FARADAY_CONSTANT = 96485  # C/mol
    
    # Exhaust gas specific heat capacities (J/kg·K) at ~600K
    CP_EXHAUST = 1050  # Average for exhaust mixture
    
    # Molecular weights (g/mol)
    MW_CO = 28.01
    MW_NOX = 46.01
    MW_H2 = 2.016
    
    # Energy content (MJ/kg)
    ENERGY_CONTENT_H2 = 120.0  # MJ/kg for hydrogen oxidation
    
    # Emission limits (g/kWh)
    NOX_BASELINE = 15.0  # Traditional catalytic converter
    CO_BASELINE = 2.0
    
    def __init__(self, exhaust_props: ExhaustGasProperties, 
                 cell_params: IT_SOFCParameters):
        """
        Initialize the exhaust energy recovery system.
        
        Args:
            exhaust_props: Exhaust gas properties
            cell_params: IT-SOFC operating parameters
        """
        self.exhaust = exhaust_props
        self.cell = cell_params
        self.validate_parameters()
    
    def validate_parameters(self) -> None:
        """Validate input parameters are within realistic ranges."""
        if self.exhaust.mass_flow_rate <= 0:
            raise ValueError("Mass flow rate must be positive")
        
        if not (0 < self.exhaust.inlet_temperature < 1200):
            warnings.warn("Exhaust temperature outside typical range (300-1000K)")
        
        if not (0 <= self.cell.fuel_utilization <= 1):
            raise ValueError("Fuel utilization must be between 0 and 1")
        
        if not (0 <= self.cell.electrical_efficiency <= 1):
            raise ValueError("Electrical efficiency must be between 0 and 1")
    
    def calculate_sensible_heat_recovery(self) -> float:
        """
        Calculate sensible heat available from exhaust gas cooling.
        
        Returns:
            float: Available sensible heat power (W)
        """
        delta_T = self.exhaust.inlet_temperature - self.exhaust.outlet_temperature
        sensible_heat = self.exhaust.mass_flow_rate * self.CP_EXHAUST * delta_T
        return sensible_heat
    
    def calculate_chemical_energy_content(self) -> Tuple[float, float]:
        """
        Calculate chemical energy available from CO and potential H2 oxidation.
        
        Returns:
            Tuple[float, float]: (CO energy in W, H2 energy potential in W)
        """
        # CO oxidation: 2CO + O2 → 2CO2, ΔH = -283 kJ/mol
        ENERGY_CO_OXIDATION = 283000  # J/mol
        
        # Mass of CO per second
        co_mass_per_sec = (self.exhaust.mass_flow_rate * 
                          self.exhaust.co_concentration * 1e-6)
        co_moles_per_sec = co_mass_per_sec / (self.MW_CO / 1000)
        co_energy = co_moles_per_sec * ENERGY_CO_OXIDATION
        
        # H2 energy potential (if reformed from hydrocarbons)
        h2_mass_fraction = self.exhaust.hydrogen_concentration / 100
        h2_mass_per_sec = self.exhaust.mass_flow_rate * h2_mass_fraction
        h2_energy = h2_mass_per_sec * self.ENERGY_CONTENT_H2 * 1e6  # Convert MJ to J
        
        return co_energy, h2_energy
    
    def calculate_stack_output_power(self) -> float:
        """
        Calculate electrical power output from IT-SOFC stack.
        
        The fuel cell processes both sensible heat energy and chemical energy
        from exhaust gases to generate electricity.
        
        Returns:
            float: Electrical power output (W)
        """
        sensible_heat = self.calculate_sensible_heat_recovery()
        co_energy, h2_energy = self.calculate_chemical_energy_content()
        
        # Total available energy
        total_energy = sensible_heat + co_energy + h2_energy
        
        # Account for reforming efficiency (sensible heat) and fuel cell efficiency
        reforming_efficiency = 0.85  # Sensible heat to H2 conversion
        
        usable_energy = (sensible_heat * reforming_efficiency * 
                        self.cell.fuel_utilization + 
                        (co_energy + h2_energy) * self.cell.fuel_utilization)
        
        electrical_power = usable_energy * self.cell.electrical_efficiency
        
        return max(0, electrical_power)
    
    def calculate_emission_reduction(self) -> Dict[str, float]:
        """
        Calculate NOx and CO emission reduction metrics.
        
        Returns:
            Dict containing emission reduction percentages and absolute values
        """
        electrical_power_W = self.calculate_stack_output_power()
        electrical_power_kW = electrical_power_W / 1000
        
        # Operating hours per year (typical ATV usage)
        HOURS_PER_YEAR = 500
        annual_energy_kwh = electrical_power_kW * HOURS_PER_YEAR
        
        # Traditional catalytic converter emissions
        nox_baseline_annual = self.NOX_BASELINE * annual_energy_kwh  # g
        co_baseline_annual = self.CO_BASELINE * annual_energy_kwh  # g
        
        # IT-SOFC with integrated emission control
        # NOx reduction through controlled combustion (>95%)
        # CO oxidation in fuel cell (>98%)
        nox_reduction_percent = 96.0
        co_reduction_percent = 99.0
        
        nox_reduced = nox_baseline_annual * (1 - nox_reduction_percent/100)
        co_reduced = co_baseline_annual * (1 - co_reduction_percent/100)
        
        return {
            'nox_reduction_percent': nox_reduction_percent,
            'co_reduction_percent': co_reduction_percent,
            'nox_baseline_annual_g': nox_baseline_annual,
            'co_baseline_annual_g': co_baseline_annual,
            'nox_reduced_annual_g': nox_reduced,
            'co_reduced_annual_g': co_reduced,
            'nox_reduction_annual_g': nox_baseline_annual - nox_reduced,
            'co_reduction_annual_g': co_baseline_annual - co_reduced,
        }
    
    def calculate_carbon_footprint_reduction(self) -> Dict[str, float]:
        """
        Calculate CO2 equivalent reduction from energy generation and emission reduction.
        
        Returns:
            Dict containing carbon footprint metrics
        """
        electrical_power_kW = self.calculate_stack_output_power() / 1000
        
        # Grid electricity emissions (g CO2/kWh) - typical grid
        GRID_EMISSION_FACTOR = 500  # g CO2/kWh
        
        # Annual operation
        HOURS_PER_YEAR = 500
        annual_energy_kwh = electrical_power_kW * HOURS_PER_YEAR
        
        # CO2 offset from generated electricity
        co2_offset_from_energy = annual_energy_kwh * GRID_EMISSION_FACTOR  # g
        
        # CO2 reduction from emission control (indirect benefit)
        # NOx contributes to ozone formation; CO is indirect GHG precursor
        emission_reduction = self.calculate_emission_reduction()
        
        # Estimate indirect carbon benefit from reduced pollutants
        # (based on lifecycle assessment)
        indirect_co2_benefit = (emission_reduction['nox_reduction_annual_g'] * 2.5 +  # g CO2 eq
                               emission_reduction['co_reduction_annual_g'] * 0.5)
        
        total_co2_reduction = co2_offset_from_energy + indirect_co2_benefit  # g
        
        return {
            'annual_energy_generation_kwh': annual_energy_kwh,
            'co2_offset_from_energy_g': co2_offset_from_energy,
            'indirect_emission_reduction_g': indirect_co2_benefit,
            'total_co2_reduction_annual_g': total_co2_reduction,
            'total_co2_reduction_annual_kg': total_co2_reduction / 1000,
        }
    
    def calculate_system_efficiency(self) -> Dict[str, float]:
        """
        Calculate various efficiency metrics of the IT-SOFC system.
        
        Returns:
            Dict containing efficiency metrics
        """
        sensible_heat = self.calculate_sensible_heat_recovery()
        co_energy, h2_energy = self.calculate_chemical_energy_content()
        electrical_output = self.calculate_stack_output_power()
        
        total_input_energy = sensible_heat + co_energy + h2_energy
        
        overall_efficiency = (electrical_output / total_input_energy * 100 
                            if total_input_energy > 0 else 0)
        
        return {
            'total_input_energy_W': total_input_energy,
            'sensible_heat_W': sensible_heat,
            'chemical_energy_W': co_energy + h2_energy,
            'electrical_output_W': electrical_output,
            'overall_efficiency_percent': overall_efficiency,
            'fuel_cell_efficiency_percent': self.cell.electrical_efficiency * 100,
            'fuel_utilization_percent': self.cell.fuel_utilization * 100,
        }
    
    def generate_performance_report(self) -> str:
        """
        Generate a comprehensive performance report of the IT-SOFC system.
        
        Returns:
            str: Formatted performance report
        """
        efficiency = self.calculate_system_efficiency()
        emissions = self.calculate_emission_reduction()
        carbon = self.calculate_carbon_footprint_reduction()
        
        report = f"""
╔══════════════════════════════════════════════════════════════════╗
║        IT-SOFC EXHAUST ENERGY RECOVERY SYSTEM REPORT             ║
║              Sustainable Engineering Analysis                    ║
╚══════════════════════════════════════════════════════════════════╝

┌─ OPERATING CONDITIONS ────────────────────────────────────────────┐
│ Exhaust Mass Flow Rate:          {self.exhaust.mass_flow_rate:.4f} kg/s
│ Inlet Temperature:               {self.exhaust.inlet_temperature:.1f} K
│ Outlet Temperature:              {self.exhaust.outlet_temperature:.1f} K
│ Operating Temperature (Cell):    {self.cell.operating_temperature:.1f} K
│ Fuel Utilization:                {self.cell.fuel_utilization*100:.1f} %
│ Electrical Efficiency:           {self.cell.electrical_efficiency*100:.1f} %
└──────────────────────────────────────────────────────────────────┘

┌─ ENERGY CONVERSION METRICS ────────────────────────────────────────┐
│ Sensible Heat Available:         {efficiency['sensible_heat_W']/1000:.2f} kW
│ Chemical Energy (CO + H₂):       {efficiency['chemical_energy_W']/1000:.2f} kW
│ Total Input Energy:              {efficiency['total_input_energy_W']/1000:.2f} kW
│ Electrical Power Output:         {efficiency['electrical_output_W']/1000:.2f} kW
│ Overall System Efficiency:       {efficiency['overall_efficiency_percent']:.2f} %
└──────────────────────────────────────────────────────────────────┘

┌─ EMISSIONS REDUCTION ──────────────────────────────────────────────┐
│ NOx Reduction:                   {emissions['nox_reduction_percent']:.1f} %
│   Annual Reduction:              {emissions['nox_reduction_annual_g']:.1f} g
│ CO Reduction:                    {emissions['co_reduction_percent']:.1f} %
│   Annual Reduction:              {emissions['co_reduction_annual_g']:.1f} g
└──────────────────────────────────────────────────────────────────┘

┌─ CARBON FOOTPRINT IMPACT ──────────────────────────────────────────┐
│ Annual Energy Generation:        {carbon['annual_energy_generation_kwh']:.1f} kWh
│ CO₂ Offset (Energy):             {carbon['co2_offset_from_energy_g']/1000:.2f} kg
│ Emission Control Benefit:        {carbon['indirect_emission_reduction_g']/1000:.2f} kg CO₂ eq
│ Total Annual CO₂ Reduction:      {carbon['total_co2_reduction_annual_kg']:.2f} kg
└──────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════
"""
        return report


def main():
    """
    Example demonstration of IT-SOFC exhaust energy recovery system.
    """
    # Typical ATV exhaust conditions
    exhaust_properties = ExhaustGasProperties(
        mass_flow_rate=0.045,              # kg/s (typical ATV idle-cruise)
        inlet_temperature=723.15,           # K (~450°C)
        outlet_temperature=623.15,          # K (~350°C) after heat recovery
        co_concentration=8000,              # ppm (unburned CO)
        nox_concentration=2500,             # ppm (NOx from combustion)
        hydrogen_concentration=0.5,         # % (reformable from CO/hydrocarbons)
        pressure=1.0                        # atm
    )
    
    # IT-SOFC operating parameters
    cell_parameters = IT_SOFCParameters(
        operating_temperature=773.15,       # K (~500°C) for IT-SOFC
        fuel_utilization=0.75,              # 75% fuel utilization
        electrical_efficiency=0.45,         # 45% electrical conversion efficiency
        open_circuit_voltage=0.95,          # V
        current_density=0.5,                # A/cm²
        cell_area=200.0                     # cm² (20cm x 10cm stack)
    )
    
    # Initialize and analyze system
    system = ExhaustEnergyRecovery(exhaust_properties, cell_parameters)
    
    # Generate comprehensive report
    report = system.generate_performance_report()
    print(report)
    
    # Display efficiency breakdown
    efficiency = system.calculate_system_efficiency()
    print("\n┌─ EFFICIENCY BREAKDOWN ────────────────────────────────────────┐")
    for key, value in efficiency.items():
        print(f"│ {key:.<45} {value:>10.2f}")
    print("└──────────────────────────────────────────────────────────────┘\n")


if __name__ == "__main__":
    main()
