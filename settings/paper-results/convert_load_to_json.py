import pandas as pd
import json
import os
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np

hp_power_kW = 50 # kW, Nominal Thermal Power of heat pump
ambient_groundwater_temp = 10.6  # °C
diff_temp = 5.0  # °C (Delta T)
number_heat_pumps = 15

def process_and_visualize(cooling_file, heating_file, output_json_file):
    
    # --- 1. Load and Clean Data ---
    print("Reading files...")
    
    # Load Cooling
    try:
        # Handling the specific comment issue in the cooling file
        df_cool = pd.read_csv(cooling_file, names=['date', 'water_ratio', 'comment'], skiprows=1)
    except:
        # Fallback if the file structure is standard
        df_cool = pd.read_csv(cooling_file)
        
    df_cool['date'] = pd.to_datetime(df_cool['date'])
    df_cool['cooling_ratio'] = pd.to_numeric(df_cool['water_ratio'], errors='coerce').fillna(0)
    df_cool = df_cool[['date', 'cooling_ratio']]

    # Load Heating
    df_heat = pd.read_csv(heating_file)
    df_heat['date'] = pd.to_datetime(df_heat['date'])
    df_heat['heating_ratio'] = pd.to_numeric(df_heat['water_ratio'], errors='coerce').fillna(0)
    df_heat = df_heat[['date', 'heating_ratio']]

    # Merge
    df = pd.merge(df_cool, df_heat, on='date', how='outer').fillna(0)
    df = df.sort_values('date')

    # --- 2. Calculate Physics Parameters ---

    # Time: Fraction of Year
    df['day_of_year'] = df['date'].dt.dayofyear
    df['year_fraction'] = (df['day_of_year'] - 1) / 365.0

    # Injection Rate: SUM
    df['injection_rate'] = df['cooling_ratio'] + df['heating_ratio']

    # Injection Temp: Weighted Average based on diff_temp Kelvin Delta
    # T_inj = ambient_groundwater_temp + diff_temp * (Cooling - Heating) / Total
    df['net_load'] = df['cooling_ratio'] - df['heating_ratio']

    conditions = [
        df['net_load'] > 0,
        df['net_load'] < 0
    ]
    choices = [
        ambient_groundwater_temp + diff_temp,
        ambient_groundwater_temp - diff_temp
    ]

    df['injection_temp'] = np.select(conditions, choices, default=ambient_groundwater_temp)

    # --- 3. Generate JSON ---
    temp_values = {}
    rate_values = {}

    hp_capacity_w = hp_power_kW * 1000 # Nominal Thermal Power of heat pump in W.
    density_water = 1000.0        # kg/m3
    specific_heat_water = 4186.0  # J/(kg*K)
    max_flow_rate_m3s = hp_capacity_w / (density_water * specific_heat_water * diff_temp)

    max_rate = df['injection_rate'].max(axis=0)

    for _, row in df.iterrows():
        time = row['year_fraction']
        key = f"{time:.5f}"
        temp_values[key] = row['injection_temp']
        rate_values[key] = max(0, max_flow_rate_m3s * (row['injection_rate'] / max_rate))

    output_data = {
        "number": number_heat_pumps,
        "injection_temp": {
            "time_unit": "year",
            "values": temp_values
        },
        "injection_rate": {
            "time_unit": "year",
            "values": rate_values
        }
    }

    with open(output_json_file, 'w') as f:
        json.dump(output_data, f, indent=2)
    print(f"JSON config saved to: {output_json_file}")

    # --- 4. Visualization ---
    print("Generating plot...")
    
    fig, ax1 = plt.subplots(figsize=(14, 7))

    # --- Left Axis: Injection Temperature ---
    color_temp = 'purple'
    ax1.set_xlabel('Date')
    ax1.set_ylabel('Injection Temperature (°C)', color=color_temp, fontsize=12, fontweight='bold')
    
    ln1 = ax1.step(df['date'], df['injection_temp'], where='post', color=color_temp, linewidth=2, label='Injection Temp (Fixed Delta T)')
    
    ax1.tick_params(axis='y', labelcolor=color_temp)
    ax1.set_ylim(ambient_groundwater_temp - diff_temp - 2, ambient_groundwater_temp + diff_temp + 2)
    ax1.axhline(y=ambient_groundwater_temp, color='purple', linestyle=':', alpha=0.8, label=f'Groundwater ({ambient_groundwater_temp}°C)')

    ax2 = ax1.twinx()
    ax2.set_ylabel('Load Ratio (0-1)', color='black', fontsize=12, fontweight='bold')
    
    # Plot Total Rate ( Flow)
    ln2 = ax2.fill_between(df['date'], df['injection_rate'], color='gray', alpha=0.3, label='Injection Rate (Variable Flow)')
    
    ln3 = ax2.plot(df['date'], df['heating_ratio'], color='tab:red', linewidth=1, linestyle='--', alpha=0.6, label='Heating Load')
    ln4 = ax2.plot(df['date'], df['cooling_ratio'], color='tab:blue', linewidth=1, linestyle='--', alpha=0.6, label='Cooling Load')

    ax2.tick_params(axis='y', labelcolor='black')

    # Formatting
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%b'))
    ax1.xaxis.set_major_locator(mdates.MonthLocator())
    plt.title(f'Simulation Config: Fixed Delta T ({diff_temp}K) & Variable Flow', fontsize=14)
    ax1.grid(True, linestyle='--', alpha=0.5)

    # Legend Handling
    import matplotlib.patches as mpatches
    patch = mpatches.Patch(color='gray', alpha=0.3, label='Injection Rate (Flow)')
    lines = ln1 + ln3 + ln4
    labels = [l.get_label() for l in lines]
    
    ax1.legend(lines + [patch], labels + ['Injection Rate (Flow)'], loc='upper left', frameon=True, fancybox=True, framealpha=0.9)

    plt.tight_layout()
    plt.savefig('simulation_config_plot.png', dpi=300)
    plt.close()
    print("Plot saved as 'simulation_config_plot.png'")

if __name__ == "__main__":
    # Ensure these match your actual filenames
    COOLING_CSV = 'cooling_load_ratio.csv'
    HEATING_CSV = 'heating_load_ratio.csv'
    OUTPUT_JSON = 'hps_settings.json'

    if os.path.exists(COOLING_CSV) and os.path.exists(HEATING_CSV):
        process_and_visualize(COOLING_CSV, HEATING_CSV, OUTPUT_JSON)
    else:
        print("CSV files not found. Please check filenames.")
