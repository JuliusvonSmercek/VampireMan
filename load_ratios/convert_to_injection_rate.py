import pandas as pd
import numpy as np

years = 27

input = "cooling_load_ratio"
input_file = input + ".csv"

# 1. Read CSV
time_series = pd.read_csv(input_file, on_bad_lines="skip")

# 2. Compute normalization constants
num_time_steps = len(time_series)
min_val = time_series["water_ratio"].min()
max_val = time_series["water_ratio"].max()

# 3. Create normalized base arrays
time_norm = np.arange(num_time_steps) / num_time_steps
ratio_norm = (time_series["water_ratio"] - min_val) / (max_val - min_val)
ratio_scaled = ratio_norm * 0.00024

# 4. Create output array for all years
output = np.zeros((years * num_time_steps, 2))

# 5. Fill output for each year
for year in range(years):
    start = year * num_time_steps
    end = start + num_time_steps
    output[start:end, 0] = time_norm + year        # time (shifted per year)
    output[start:end, 1] = ratio_scaled            # scaled ratio

# 6. Print a sample
with open(input + ".txt", "w") as f:
    for n in range(output.shape[0]):
        f.write(f"{output[n,0]}:\t{output[n,1]}\n")

print("Done")
