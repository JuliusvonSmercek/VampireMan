import pandas as pd
import numpy as np

def get_month_index(month_name: str, num_time_steps: int) -> int:
    """Returns the index of the starting month in the time series data."""
    month_name = month_name.lower()
    month_to_index = {
        "january": 0, "february": 1, "march": 2, "april": 3,
        "may": 4, "june": 5, "july": 6, "august": 7,
        "september": 8, "october": 9, "november": 10, "december": 11
    }
    if month_name not in month_to_index:
        raise ValueError(f"Invalid month name: {month_name}")
    
    month_index = month_to_index[month_name]
    steps_per_month = num_time_steps // 12
    return month_index * steps_per_month


years = 27.5
full_years = int(years)             # = 27
fraction = years - full_years       # = 0.5

starting_month = "May"
input_name = "cooling_load_ratio"
input_file = input_name + ".csv"

output_name = f"{input_name}_{starting_month}"

# 1. Read CSV
time_series = pd.read_csv(input_file, on_bad_lines="skip")

# 2. Compute normalization constants
num_time_steps = len(time_series)
min_val = time_series["water_ratio"].min()
max_val = time_series["water_ratio"].max()

# 3. Create normalized base arrays
time_norm = np.arange(num_time_steps) / num_time_steps
ratio_norm = (time_series["water_ratio"] - min_val) / (max_val - min_val)

# Convert ratio to m³/s (0.0001–0.01)
ratio_scaled = ratio_norm * (0.01 - 0.0001) + 0.0001

# Rotate starting month to front
rotation = num_time_steps - get_month_index(starting_month, num_time_steps)
rotated_ratio_scaled = np.roll(ratio_scaled, rotation)

# 4. Allocate output array (including fractional year)
total_steps = int(years * num_time_steps)
out = np.zeros((total_steps, 2))

# 5. Fill whole years
for year in range(full_years):
    start = year * num_time_steps
    end = start + num_time_steps
    out[start:end, 0] = time_norm + year
    out[start:end, 1] = rotated_ratio_scaled

# 6. Fill fractional part (e.g., 0.5 year)
remaining_steps = total_steps - full_years * num_time_steps
if remaining_steps > 0:
    out[full_years * num_time_steps:, 0] = time_norm[:remaining_steps] + full_years
    out[full_years * num_time_steps:, 1] = rotated_ratio_scaled[:remaining_steps]

# 7. Write output file
output_file = output_name + ".txt"
with open(output_file, "w") as f:
    for n in range(out.shape[0]):
        f.write(f"{out[n,0]}:\t{out[n,1]}\n")

print("Done")
