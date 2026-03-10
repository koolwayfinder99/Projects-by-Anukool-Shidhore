%==========================================================================
% EV Battery Thermal Model - 48V Li-ion Battery Pack
%==========================================================================
% This script calculates the transient heat generation and temperature
% distribution in a 48V lithium-ion battery pack, accounting for ohmic
% heating, electrochemical effects, and convective heat dissipation.
%
% Physical Constants and Battery Parameters:
% - Battery nominal voltage: 48V
% - Nominal capacity: 100 Ah (typical EV battery)
% - Internal resistance: Temperature-dependent
% - Specific heat capacity: Varies with state-of-charge
% - Thermal conductivity: Anisotropic (parallel > perpendicular)
%==========================================================================

clear all; close all; clc;

% ========================================================================
% SECTION 1: BATTERY PACK PARAMETERS
% ========================================================================

% Battery specifications (48V LiFePO4 configuration)
V_nominal = 48;              % Nominal voltage [V]
Q_capacity = 100;            % Battery capacity [Ah]
num_cells = 16;              % Number of cells in series (3.2V nominal each)
V_cell_nominal = V_nominal / num_cells;  % Single cell voltage [V]

% Thermal properties (LiFePO4 cell - cylindrical 21700 format)
m_cell = 0.065;              % Mass per cell [kg]
m_total = m_cell * num_cells;  % Total battery pack mass [kg]
c_p = 1200;                  % Specific heat capacity [J/(kg·K)] @ 25°C
rho = 2200;                  % Effective density of battery pack [kg/m³]
k_thermal = 8;               % Effective thermal conductivity [W/(m·K)]

% Geometric parameters
L_cell = 0.070;              % Cell length [m]
D_cell = 0.021;              % Cell diameter [m]
A_cell = pi * D_cell^2 / 4;  % Cross-sectional area per cell [m²]
V_cell = A_cell * L_cell;    % Volume per cell [m³]
V_total = V_cell * num_cells;  % Total battery volume [m³]

% Heat transfer parameters
h_conv = 45;                 % Convective heat transfer coefficient [W/(m²·K)]
A_surface = 0.35;            % Effective cooling surface area [m²]
T_ambient = 25;              % Ambient temperature [°C]
T_initial = 25;              % Initial battery temperature [°C]

% ========================================================================
% SECTION 2: INTERNAL RESISTANCE MODEL (Temperature-dependent)
% ========================================================================
% Internal resistance exhibits strong temperature dependence in Li-ion cells
% R_internal ≈ R0 + R_T(T) where R_T varies exponentially with temperature

R0 = 0.003;                  % Ohmic resistance @ 25°C [Ohm]
T_ref = 25;                  % Reference temperature [°C]
alpha_R = 0.0015;            % Temperature coefficient [1/°C]

% Arrhenius-type correction for temperature dependence
% R(T) = R0 * exp(E_a / (R_gas) * (1/T - 1/T_ref))
E_a = 5000;                  % Activation energy [J/mol]
R_gas = 8.314;               % Universal gas constant [J/(mol·K)]

% ========================================================================
% SECTION 3: DISCHARGE PROFILES & OPERATING CONDITIONS
% ========================================================================
% Define realistic discharge scenarios for EV operation

% Scenario 1: Constant discharge current (highway cruising)
I_discharge = 30;            % Discharge current [A]
t_discharge = 3 * 3600;      % Discharge duration [s] - 3 hours
dt = 1;                      % Time step [s]
t_vec = 0:dt:t_discharge;

fprintf('=== EV BATTERY THERMAL MODEL ANALYSIS ===\n');
fprintf('Battery Configuration: %dS (16 cells in series)\n', V_nominal);
fprintf('Discharge Current: %.1f A\n', I_discharge);
fprintf('Simulation Duration: %.1f hours\n\n', t_discharge/3600);

% ========================================================================
% SECTION 4: HEAT GENERATION CALCULATION
% ========================================================================
% Total heat generation consists of:
% Q_total = Q_ohmic + Q_electrochemical + Q_polarization
%
% Q_ohmic = I² * R(T) - Primary source during constant discharge
% Q_electrochemical = I * (V_OCP - V_terminal) - Entropy-related
% Q_polarization = I² * R_ct - Charge transfer resistance

% Initialize arrays
Q_ohmic = zeros(size(t_vec));
Q_total = zeros(size(t_vec));
T_battery = zeros(size(t_vec));
T_battery(1) = T_initial;
R_internal = zeros(size(t_vec));

% State-of-charge calculation
SOC_max = 100;               % Maximum state of charge [%]
SOC = zeros(size(t_vec));
SOC(1) = 100;                % Start at full charge

% Open circuit voltage (Nernst equation approximation for LiFePO4)
% V_OCP ≈ 3.6 - 0.5*(1 - SOC) [V] for LiFePO4
V_OCP_nom = 3.65;            % Nominal OCP @ 50% SOC [V]
V_terminal = zeros(size(t_vec));

% ========================================================================
% SECTION 5: TRANSIENT THERMAL SIMULATION
% ========================================================================

for i = 2:length(t_vec)
    % Current battery temperature from previous step
    T_batt_current = T_battery(i-1);
    
    % Calculate internal resistance as function of temperature
    % Using Arrhenius equation for temperature dependence
    T_K = T_batt_current + 273.15;  % Convert to Kelvin
    T_ref_K = T_ref + 273.15;
    
    R_internal(i) = R0 * exp((E_a / R_gas) * (1/T_K - 1/T_ref_K));
    
    % Terminal voltage: V_t = V_OCP - I*R_internal
    V_OCP_current = V_OCP_nom + 0.01 * (T_batt_current - T_ref);
    V_terminal(i) = V_OCP_current * num_cells - I_discharge * R_internal(i);
    
    % Ohmic heat generation: Q = I² * R
    % This is the dominant heat source during discharge
    Q_ohmic(i) = I_discharge^2 * R_internal(i) * num_cells;
    
    % Electrochemical (reversible) heat: Q_elec = T*ΔS*I
    % For LiFePO4: dU/dT ≈ -0.001 V/K (weak temperature dependence)
    dU_dT = -0.001;
    Q_elec = (T_K / T_ref_K) * abs(dU_dT) * I_discharge * num_cells;
    
    % Total heat generation
    Q_total(i) = Q_ohmic(i) + Q_elec;
    
    % Heat dissipation via convection: Q_loss = h*A*(T_batt - T_ambient)
    % Forced convection with coolant circulation
    Q_loss = h_conv * A_surface * (T_batt_current - T_ambient);
    
    % Net heat rate [W]
    Q_net = Q_total(i) - Q_loss;
    
    % Temperature rise using lumped thermal model:
    % dT/dt = Q_net / (m*c_p)
    dT_dt = Q_net / (m_total * c_p);
    
    % Update battery temperature (forward Euler integration)
    T_battery(i) = T_batt_current + dT_dt * dt;
    
    % Limit maximum temperature (thermal runaway threshold ≈ 60°C)
    if T_battery(i) > 60
        warning('Critical temperature exceeded at t=%.1f s', t_vec(i));
        T_battery(i) = 60;
    end
    
    % State-of-charge reduction during discharge
    SOC(i) = SOC(i-1) - (I_discharge / (Q_capacity * 3600)) * dt * 100;
    
    % Stop simulation at minimum SOC threshold
    if SOC(i) <= 0
        T_battery(i:end) = T_battery(i);
        break;
    end
end

% ========================================================================
% SECTION 6: RESULTS & ANALYSIS
% ========================================================================

% Compute key thermal metrics
T_max = max(T_battery);
T_mean = mean(T_battery);
T_rise = T_max - T_initial;
time_to_40C = find(T_battery >= 40, 1) * dt;
dT_dt_max = max(diff(T_battery) / dt);

% Heat generation statistics
Q_avg = mean(Q_total);
Q_max = max(Q_total);
Q_loss_avg = h_conv * A_surface * (T_mean - T_ambient);

fprintf('THERMAL ANALYSIS RESULTS:\n');
fprintf('-----------------------------------\n');
fprintf('Peak Battery Temperature: %.2f °C\n', T_max);
fprintf('Mean Battery Temperature: %.2f °C\n', T_mean);
fprintf('Temperature Rise: %.2f °C\n', T_rise);
fprintf('Time to reach 40°C: %.1f min\n', time_to_40C/60);
fprintf('Maximum Heating Rate: %.3f °C/s\n\n', dT_dt_max);

fprintf('HEAT GENERATION ANALYSIS:\n');
fprintf('-----------------------------------\n');
fprintf('Average Heat Generation: %.2f W\n', Q_avg);
fprintf('Peak Heat Generation: %.2f W\n', Q_max);
fprintf('Average Convective Loss: %.2f W\n', Q_loss_avg);
fprintf('Thermal Time Constant: %.1f s\n\n', (m_total * c_p) / (h_conv * A_surface));

fprintf('BATTERY CONDITION:\n');
fprintf('-----------------------------------\n');
fprintf('Final State-of-Charge: %.1f %%\n', SOC(end));
fprintf('Final Internal Resistance: %.4f Ω\n\n', R_internal(end));

% ========================================================================
% SECTION 7: VISUALIZATION
% ========================================================================

% Create comprehensive analysis figure
figure('Name', 'EV Battery Thermal Analysis', 'NumberTitle', 'off');
set(gcf, 'Position', [100, 100, 1200, 800]);

% Subplot 1: Temperature evolution
subplot(2,3,1);
plot(t_vec/60, T_battery, 'b-', 'LineWidth', 2);
hold on;
yline(40, 'r--', 'LineWidth', 1.5); % Upper optimal limit
yline(25, 'g--', 'LineWidth', 1.5); % Lower optimal limit
yline(T_ambient, 'k:', 'LineWidth', 1);
hold off;
xlabel('Time [minutes]', 'FontSize', 11);
ylabel('Temperature [°C]', 'FontSize', 11);
title('Battery Pack Temperature Evolution', 'FontSize', 12, 'FontWeight', 'bold');
grid on; grid minor;
legend('T_{battery}', 'Upper Limit (40°C)', 'Lower Limit (25°C)', 'T_{ambient}');

% Subplot 2: Heat generation vs dissipation
Q_loss_vec = h_conv * A_surface * (T_battery - T_ambient);
subplot(2,3,2);
plot(t_vec/60, Q_total, 'r-', 'LineWidth', 2);
hold on;
plot(t_vec/60, Q_loss_vec, 'b-', 'LineWidth', 2);
hold off;
xlabel('Time [minutes]', 'FontSize', 11);
ylabel('Power [W]', 'FontSize', 11);
title('Heat Generation vs. Dissipation', 'FontSize', 12, 'FontWeight', 'bold');
grid on; grid minor;
legend('Generated Heat', 'Convective Loss');

% Subplot 3: Internal resistance variation
subplot(2,3,3);
plot(t_vec/60, R_internal*1000, 'g-', 'LineWidth', 2);
xlabel('Time [minutes]', 'FontSize', 11);
ylabel('Resistance [mΩ]', 'FontSize', 11);
title('Temperature-Dependent Internal Resistance', 'FontSize', 12, 'FontWeight', 'bold');
grid on; grid minor;

% Subplot 4: State-of-charge
subplot(2,3,4);
plot(t_vec/60, SOC, 'k-', 'LineWidth', 2);
xlabel('Time [minutes]', 'FontSize', 11);
ylabel('State of Charge [%]', 'FontSize', 11);
title('Battery State-of-Charge Profile', 'FontSize', 12, 'FontWeight', 'bold');
grid on; grid minor;

% Subplot 5: Terminal voltage
subplot(2,3,5);
plot(t_vec/60, V_terminal, 'm-', 'LineWidth', 2);
xlabel('Time [minutes]', 'FontSize', 11);
ylabel('Terminal Voltage [V]', 'FontSize', 11);
title('Battery Terminal Voltage', 'FontSize', 12, 'FontWeight', 'bold');
grid on; grid minor;

% Subplot 6: Heating rate
dT_dt_vec = [0; diff(T_battery) / dt];
subplot(2,3,6);
plot(t_vec/60, dT_dt_vec, 'c-', 'LineWidth', 2);
xlabel('Time [minutes]', 'FontSize', 11);
ylabel('Rate [°C/s]', 'FontSize', 11);
title('Temperature Heating Rate', 'FontSize', 12, 'FontWeight', 'bold');
grid on; grid minor;

% ========================================================================
% SECTION 8: EXPORT RESULTS
% ========================================================================

% Create results table
results_table = table(t_vec'/60, T_battery', Q_total', Q_loss_vec', ...
                      SOC', R_internal'*1000, V_terminal', ...
                      'VariableNames', {'Time_min', 'Temp_C', 'Heat_Gen_W', ...
                                       'Heat_Loss_W', 'SOC_pct', 'R_internal_mOhm', 'V_terminal_V'});

% Save results to CSV
writetable(results_table, 'battery_thermal_results.csv');
fprintf('Results exported to: battery_thermal_results.csv\n');

% Save figure
savefig('battery_thermal_analysis.fig');
print('-dpng', 'battery_thermal_analysis.png', '-r300');
fprintf('Figures saved: battery_thermal_analysis.fig, battery_thermal_analysis.png\n');

%==========================================================================
% END OF SCRIPT
%==========================================================================
