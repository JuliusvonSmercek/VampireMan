"""
This is the pipeline that executes the seven stages of VampireMan in their order.
The stages are:

1. `vampireman.loading_stage.loading_stage.loading_stage`
1. `vampireman.preparation_stage.preparation_stage.preparation_stage`
1. `vampireman.validation_stage.validation_stage.validation_stage`
1. `vampireman.variation_stage.variation_stage.variation_stage`
1. `vampireman.render_stage.render_stage`
1. `vampireman.simulation_stage.simulation_stage`
1. `vampireman.visualization_stage.visualization_stage`

When running interactively (depending on `vampireman.data_structures.GeneralConfig.interactive`), the execution flow
will be interrupted after the `validation_stage` and after printing the resulting `State` object, asking the user if the
pipeline should continue.
If the user denies, VampireMan will exit.
"""

import logging
from argparse import Namespace

from .loading_stage import loading_stage
from .preparation_stage import preparation_stage
from .render_stage import render_stage
from .simulation_stage import simulation_stage
from .utils import copy_settings_to_yaml, get_answer
from .validation_stage import validation_stage
from .variation_stage import variation_stage
from .visualization_stage import visualization_stage


def run(args: Namespace):
    """Runs all pipeline stages."""

    logging.debug("Running all stages now.")
    state = loading_stage(args)
    state = preparation_stage(state)
    copy_settings_to_yaml(args, state)
    state = validation_stage(state)

    print("This is the state that is going to be used:")
    print(state)

    get_answer(state, "Do you want to run the variation stage?", True)
    state = variation_stage(state)

    get_answer(state, "Do you want to run the render stage?", True)
    render_stage(state)

    get_answer(state, "Do you want to run the simulation stage?", True)
    simulation_stage(state)

    get_answer(state, "Do you want to run the visualization stage?", True)
    visualization_stage(state)
