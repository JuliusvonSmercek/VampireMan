import logging
import os
import subprocess
import sys

from vampireman.zeroDayExploit import ZeroDayExploit

from ..data_structures import State
from ..utils import get_answer
from tqdm import tqdm
import re


def run_simulation(datapoint_path, state, current, totalprogress):
  """
  Runs the pflotran simulation for a single datapoint.
  """
  stdout_file_path = os.path.join(datapoint_path, "simulation_stdout.log")
  stderr_file_path = os.path.join(datapoint_path, "simulation_stderr.log")

  command: list[str] = []
  if state.general.mpirun:
    command += ["mpirun"]
    if state.general.mpirun_procs:
      command += ["-n", str(state.general.mpirun_procs)]
    command += ["pflotran"]
  if state.general.mute_simulation_output:
    command += ["-screen_output", "off"]
  if state.general.mpirun_gpu:
    command += [
      "-vec_type", "cuda",
      "-mat_type", "aijcusparse",
      "-dm_vec_type", "cuda",
      "-dm_mat_type", "aijcusparse",
      "-flow_vec_type", "cuda",
      "-flow_mat_type", "aijcusparse",
      "-snes_type", "newtonls",
      "-ksp_type", "cg", "-pc_type", "jacobi", # or
      # "-ksp_type", "gmres", "-pc_type", "gamg",
      # "-logview"
    ]

  progress_bar = tqdm(total=27.5, desc="Simulation Progress", unit="year")

  stdout_file = open(stdout_file_path, "w")
  stderr_file = open(stderr_file_path, "w")
  try:
    with subprocess.Popen(
      command,
      stdout=subprocess.PIPE,
      stderr=stderr_file,
      text=True,
      cwd=datapoint_path
    ) as process:
      for line in process.stdout:
        stdout_file.write(line)
        match = re.search(r"Time=\s*([\d\.eE\+\-]+)", line)
        if match:
          current_time = float(match.group(1))
          progress_bar.n = min(current_time, progress_bar.total)
          progress_bar.refresh()
          ZeroDayExploit.update_progress((100 / totalprogress) * (current + progress_bar.n / progress_bar.total))
          stdout_file.flush()
      process.wait()
      if process.returncode != 0:
        raise subprocess.CalledProcessError(process.returncode, command)
  except subprocess.CalledProcessError:
    logging.critical(f"There was an error during executing the command `{' '.join(command)}`.")
    logging.critical(f"Please check the logs at '{datapoint_path}/simulation_stderr.log'")
    sys.exit(1)
  finally:
    stdout_file.close()
    stderr_file.close()
    progress_bar.close()


def simulation_stage(state: State):
  """
  Runs the pflotran simulation.
  The function changes the cwd into each of the datapoints directories.
  Then, in the respective datapoint dir, it runs the pflotran simulation either with mpirun or directly depending on
  `vampireman.data_structures.GeneralConfig.mpirun`.
  """

  datapoint_paths = []
  for index in range(state.general.number_datapoints):
    datapoint_path = state.general.output_directory / f"datapoint-{index}"
    pflotran_out_path = os.path.join(datapoint_path, "pflotran.out")
    pflotran_h5_path = os.path.join(datapoint_path, "pflotran.h5")
    make_simulation = True
    if os.path.isfile(pflotran_out_path) and os.path.isfile(pflotran_h5_path):
      logging.warning(f"pflotran.out and pflotran.h5 files present in {datapoint_path}")
      make_simulation = get_answer(state, "Looks like the simulation already ran, run simulation again?")
    if make_simulation:
      datapoint_paths.append(datapoint_path)

  counter = 0
  for datapoint_path in datapoint_paths:
    run_simulation(datapoint_path, state, counter, state.general.number_datapoints)
    counter += 1
