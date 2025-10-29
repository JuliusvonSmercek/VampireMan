import logging
import os
import subprocess
import sys

from ..data_structures import State
from ..utils import get_answer


def simulation_stage(state: State):
    """
    Runs the pflotran simulation.
    The function changes the cwd into each of the datapoints directories.
    Then, in the respective datapoint dir, it runs the pflotran simulation either with mpirun or directly depending on
    `vampireman.data_structures.GeneralConfig.mpirun`.
    """

    original_dir = os.getcwd()

    for index in range(state.general.number_datapoints):
        datapoint_path = state.general.output_directory / f"datapoint-{index}"
        os.chdir(datapoint_path)
        if os.path.isfile("pflotran.out") and os.path.isfile("pflotran.h5"):
            logging.warning(f"pflotran.out and pflotran.h5 files present in {datapoint_path}")
            if not get_answer(state, "Looks like the simulation already ran, run simulation again?"):
                os.chdir(original_dir)
                continue

        command: list[str] = []
        if state.general.mpirun:
            command += ["mpirun"]
            if state.general.mpirun_procs:
                command += ["-n", str(state.general.mpirun_procs)]
            # command += ["--"]  # Ends the command inputs for mpirun
        command += ["pflotran"]
        if state.general.mute_simulation_output:
            command += ["-screen_output", "off"]
        try:
            subprocess.run(command, check=True, close_fds=True)
        except subprocess.CalledProcessError:
            logging.critical(f"There was an error during executing the command `{" ".join(command)}`.")
            logging.critical(f"Please check the logs at '{datapoint_path}/pflotran.out'")
            sys.exit(1)

        # always go back to the original_dir as we use relative paths
        os.chdir(original_dir)
