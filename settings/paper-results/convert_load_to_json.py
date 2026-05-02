import pandas as pd
import json
import os
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np

hp_power_kW = 100 # kW, Nominal Thermal Power of heat pump
ambient_groundwater_temp = 10.6  # °C
diff_temp = 5.0  # °C (Delta T)
number_heat_pumps = 15

def process_and_visualize(cooling_file, heating_file, output_json_file):
    print("Reading files...")
    try:
        df_cool = pd.read_csv(cooling_file, names=['date', 'water_ratio', 'comment'], skiprows=1)
    except:
        df_cool = pd.read_csv(cooling_file)
        
    df_cool['date'] = pd.to_datetime(df_cool['date'])
    df_cool['cooling_ratio'] = pd.to_numeric(df_cool['water_ratio'], errors='coerce').fillna(0)
    df_cool = df_cool[['date', 'cooling_ratio']]

    df_heat = pd.read_csv(heating_file)
    df_heat['date'] = pd.to_datetime(df_heat['date'])
    df_heat['heating_ratio'] = pd.to_numeric(df_heat['water_ratio'], errors='coerce').fillna(0)
    df_heat = df_heat[['date', 'heating_ratio']]

    df = pd.merge(df_cool, df_heat, on='date', how='outer').fillna(0)
    df = df.sort_values('date')

    df['day_of_year'] = df['date'].dt.dayofyear
    df['year_fraction'] = (df['day_of_year'] - 1) / 365.0

    df['injection_rate'] = df['cooling_ratio'] + df['heating_ratio']

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

    print("Generating plot...")
    
    # NeurIPS paper standard settings
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Computer Modern Roman", "DejaVu Serif"],
        "font.size": 10,          # NeurIPS standard text size
        "axes.labelsize": 10,
        "legend.fontsize": 8,     # Slightly smaller for legend
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "figure.dpi": 300,
        "pdf.fonttype": 42        # Ensures fonts are embedded in PDF
    })

    # NeurIPS text width is 5.5 inches. Aspect ratio adjusted for readability.
    fig, ax1 = plt.subplots(figsize=(5.5, 3.0))

    color_temp = '#1f77b4' # Muted blue, translates better to grayscale
    ax1.set_xlabel('Date')
    ax1.set_ylabel('Injection Temp. (°C)', color='black')
    
    ln1 = ax1.step(df['date'], df['injection_temp'], where='post', color=color_temp, linewidth=1.5, label='Injection Temp')
    
    ax1.tick_params(axis='y')
    ax1.set_ylim(ambient_groundwater_temp - diff_temp - 1, ambient_groundwater_temp + diff_temp + 1)
    
    # Groundwater reference line
    ax1.axhline(y=ambient_groundwater_temp, color='black', linestyle=':', linewidth=1, label=f'Groundwater ({ambient_groundwater_temp}°C)')

    ax2 = ax1.twinx()
    ax2.set_ylabel('Load Ratio', color='black')

    # Use fill_between for the rate to visually distinguish from temperature lines
    color_rate = 'gray'
    ln2 = ax2.fill_between(df['date'], df['injection_rate'], color=color_rate, alpha=0.3)
    ax2.set_ylim(0, 0.13) # Bound ratio cleanly
    ax2.tick_params(axis='y')

    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%b'))
    ax1.xaxis.set_major_locator(mdates.MonthLocator())
    
    # Remove heavy gridlines to reduce clutter; keep minimal y-axis grid if necessary
    ax1.grid(True, axis='y', linestyle='--', alpha=0.3)

    import matplotlib.patches as mpatches
    patch = mpatches.Patch(color=color_rate, alpha=0.3, label='Injection Rate')
    lines = ln1
    labels = [l.get_label() for l in lines]
    
    # Place legend outside plot area to prevent data occlusion, horizontal layout
    ax1.legend(lines + [ax1.lines[-1], patch], 
               labels + [f'Ambient temperature ({ambient_groundwater_temp}°C)', 'Injection Rate'], 
               loc='upper center', bbox_to_anchor=(0.5, 1.18), ncol=3, frameon=False)

    plt.tight_layout()
    # Save as PDF for lossless LaTeX vector integration
    plt.savefig('simulation_config_plot.pdf', format='pdf', bbox_inches='tight')
    plt.close()
    print("Plot saved as 'simulation_config_plot.pdf'")

if __name__ == "__main__":
    COOLING_CSV = 'cooling_load_ratio.csv'
    HEATING_CSV = 'heating_load_ratio.csv'
    OUTPUT_JSON = 'hps_settings.json'

    if os.path.exists(COOLING_CSV) and os.path.exists(HEATING_CSV):
        process_and_visualize(COOLING_CSV, HEATING_CSV, OUTPUT_JSON)
    else:
        print("CSV files not found. Please check filenames.")
