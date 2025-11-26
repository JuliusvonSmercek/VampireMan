import json

def generate_json_file(output_path):
  t_steps = 10_000
  t_end = 27.5
  normal_flow = 0.00048
  nr_cooling_days = int(365 * 5.5)
  
  time_stamps = [(t_end * i * 365) / t_steps for i in range(t_steps)]
  t_seasonal = [0 if (time_stamps[i] % (nr_cooling_days*2)) > nr_cooling_days else normal_flow for i in range(t_steps)]

  print(t_seasonal)

  injection_rate_values = {}
  for i in range(0, t_steps):
    if 0 < i and i < t_steps - 1 and t_seasonal[i - 1] == t_seasonal[i] and t_seasonal[i] == t_seasonal[i + 1]:
      continue
    injection_rate_values[str(time_stamps[i] / 365)] = t_seasonal[i]

  data = {
    "number": 20,
    "injection_temp": 15.6,
    "injection_rate": {
      "time_unit": "year",
      "values": injection_rate_values
    }
  }

  with open(output_path, 'w') as json_file:
    json.dump(data, json_file, indent=4)
  print(f"JSON file generated and saved to {output_path}")

generate_json_file("./hps_settings.json")