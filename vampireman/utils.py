"""
This submodule encompasses utility functions that can be used throughout the code base.
"""

import cProfile
import functools
import hashlib
import io
import logging
import os
import pstats
import sys
import time
from pathlib import Path
from pstats import SortKey
from types import ModuleType
from typing import TYPE_CHECKING

from pydantic import BaseModel

from .data_structures import DataPoint

if TYPE_CHECKING:
    from .data_structures import State


def get_answer(state: "State", question: str, exit_if_no: bool = False) -> bool:
    """
    Ask a yes/no question on the command line and return True if the answer is yes and False if the answer is no.
    When CTRL+C is detected, the function will terminate the whole program returning an exit code of 0.
    """

    if not state.general.interactive:
        return True
    try:
        match input(f"{question} Y/n "):
            case "n" | "N" | "no" | "q":
                if exit_if_no:
                    logging.info("Exiting as instructed")
                    sys.exit(0)
                return False
            case _:
                return True
    except KeyboardInterrupt:
        logging.info("Exiting as instructed")
        sys.exit(0)


def get_sim_tool_implementation(sim_tool: str) -> ModuleType:
    """
    Returns a submodule, based on the switch-case value.
    Raises a `NotImplementedError` when the implementation could not be found.
    """

    match sim_tool:
        case "pflotran":
            from . import pflotran

            return pflotran
        case _:
            logging.error("%s simulation tool is not yet implemented", sim_tool)
            raise NotImplementedError("Simulation tool not implemented")


def profile_function(function):
    """
    This function wrapper can be used to profile other functions.
    To use, simply write

    @profile_function
    def my_function():
        pass

    This will write profiling information to the ./profiling directory and also print timings for the wrapped function.
    Profiling does not work when profiling is already enabled, so make sure not to nest profiled functions.
    """

    @functools.wraps(function)
    def wrapper(*args):
        state: State = args[0]

        if state.general.profiling:
            profile = cProfile.Profile()

            start_time = time.perf_counter()

            profile.enable()

            result = function(*args)

            profile.disable()

            end_time = time.perf_counter()
            run_time = end_time - start_time
            logging.info("Function %s.%s took %s", function.__module__, function.__name__, run_time)

            s = io.StringIO()
            ps = pstats.Stats(profile, stream=s).sort_stats(SortKey.CUMULATIVE)
            ps.print_stats()

            with open(
                f"profiling/{state.general.output_directory.name}_{function.__module__}.{function.__name__}.txt", "w"
            ) as file:
                file.write(s.getvalue())
        else:
            result = function(*args)

        return result

    return wrapper


def create_dataset_and_datapoint_dirs(state: "State"):
    """
    For each of the `DataPoint`s create a directory.
    """

    for index in range(state.general.number_datapoints):
        datapoint_dir = state.general.output_directory / f"datapoint-{index}"
        try:
            os.makedirs(datapoint_dir, exist_ok=True)
        except OSError as error:
            logging.critical("Directory at %s could not be created, cannot proceed", datapoint_dir)
            raise error


def write_data_to_verified_json_file(state: "State", target_path: Path, data: BaseModel):
    """
    Write a `pydantic.main.BaseModel` to a file and ask the user how to proceed, if there is already a file present
    with different contents than the data that is represented in `data`.
    The data will be written in JSON format.
    """

    need_to_write_file = True

    # Write hash of permeability content into permeability field
    # This avoids putting hundreds of MB of numbers into the file when handling large perm fields
    if isinstance(data, DataPoint):
        perm = data.data.get("permeability")
        assert perm is not None  # Should never happen, make the linter happy
        perm_value = perm.value
        data.data["permeability"].value = hashlib.sha256(perm.model_dump_json(indent=2).encode()).hexdigest()

    # Check if there already is a target file
    if os.path.isfile(target_path):
        with open(target_path, encoding="utf8") as target_file:
            target_file_content = target_file.read()

        # Calculate the hash from the data object and the existing target file
        hash_in_memory = hashlib.sha256(data.model_dump_json(indent=2).encode()).hexdigest()
        hash_target_file = hashlib.sha256(target_file_content.encode()).hexdigest()

        # If there is, compare the contents to let the user abort
        if hash_in_memory != hash_target_file:
            logging.warning("Target file '%s' has different contents than data structure!", target_path)
            if not get_answer(state, f"Different target file already in {target_path}, overwrite?"):
                need_to_write_file = False
        else:
            logging.debug("File '%s' doesn't need to be written", target_path)

    if need_to_write_file:
        with open(target_path, "w", encoding="utf8") as target_file:
            target_file.write(data.model_dump_json(indent=2))

    if isinstance(data, DataPoint):
        # Restore the previous actual value
        perm.value = perm_value  # pyright: ignore


def copy_settings_to_yaml(args, state):
    # copy file to output directory: self.general.output_directory / "settings.yaml"
    if args.settings_file:
        with open(args.settings_file) as f:
            settings = f.read()
        with open(state.general.output_directory / "settings.yaml", "w") as f:
            f.write(settings)
