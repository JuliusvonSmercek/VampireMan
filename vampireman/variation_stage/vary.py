import logging
from copy import deepcopy
from typing import cast

import numpy as np
from numpy.typing import ArrayLike

from ..data_structures import (
    Data,
    DataPoint,
    Distribution,
    HeatPump,
    HeatPumps,
    Parameter,
    State,
    ValueMinMax,
    ValuePerlin,
    ValueTimeSeries,
    Vary,
)
from .vary_perlin import create_perlin_field


def copy_parameter(state: State, parameter: Parameter) -> Data:
    """
    This function simply copies all values from a `Parameter` to a `Data` object without any transformation.
    """

    if isinstance(parameter.value, HeatPump):
        return vary_heatpump(state, parameter)
    return Data(name=parameter.name, value=deepcopy(parameter.value))


def vary_heatpump(state: State, parameter: Parameter) -> Data:
    """
    This function calculates operational parameters for `vampireman.data_structures.HeatPump`s.
    If the `vampireman.data_structures.Vary` mode is SPACE, the location will be drawn randomly.
    """

    hp = deepcopy(parameter.value)
    assert isinstance(hp, HeatPump)

    hp = handle_heatpump_values(state.get_rng(), hp)

    result_location = np.array(hp.location)
    if parameter.vary == Vary.SPACE:
        result_location = generate_heatpump_location(state)  # XXX: Is this handling location clashes correctly?
        resolution = state.general.cell_resolution
        # This is needed as we need to calculate the heatpump coordinates for pflotran.in
        result_location = (np.array(result_location) - 1) * resolution + (resolution * 0.5)

    return Data(
        name=parameter.name,
        value=HeatPump(
            location=cast(list[float], result_location),
            injection_temp=hp.injection_temp,
            injection_rate=hp.injection_rate,
        ),
    )


def vary_parameter(state: State, parameter: Parameter, index: int) -> Data:
    """
    This function does the variation of `vampireman.data_structures.Parameter`s.
    It does so by implementing a large match-case that in turn invokes other functions that then work on the
    `vampireman.data_structures.Parameter.value` based on the `vampireman.data_structures.Parameter.vary` type.
    """

    assert not isinstance(parameter.value, HeatPumps)
    match parameter.vary:
        case Vary.FIXED:
            data = copy_parameter(state, parameter)

        case Vary.CONST:
            if isinstance(parameter.value, ValueMinMax):
                max = deepcopy(parameter.value.max)
                min = deepcopy(parameter.value.min)

                if parameter.distribution == Distribution.LOG:
                    max = np.log10(max)
                    min = np.log10(min)

                distance = max - min
                step_width = distance / (state.general.number_datapoints - 1)
                value = min + step_width * index

                if parameter.distribution == Distribution.LOG:
                    value = 10**value

                data = Data(
                    name=parameter.name,
                    value=value,
                )
            else:
                logging.error(
                    "No implementation for %s and %s in parameter %s",
                    type(parameter.value),
                    parameter.vary,
                    parameter.name,
                )
                raise NotImplementedError()

        case Vary.SPACE:
            if isinstance(parameter.value, ValuePerlin):
                data = Data(
                    name=parameter.name,
                    value=create_perlin_field(state, parameter),
                )
            elif isinstance(parameter.value, float):
                raise ValueError(
                    f"Parameter {parameter.name} is vary.space and has a float value, "
                    f"it should be set to vary.fixed with a min/max value instead; {parameter}"
                )
            # This should be inside the CONST block, yet it seems to make more sense to users to find it here
            elif isinstance(parameter.value, HeatPump):
                data = vary_heatpump(state, parameter)
            elif isinstance(parameter.value, ValueMinMax):
                raise ValueError(
                    f"Parameter {parameter.name} is vary.space and has min/max values, "
                    f"it should be set to vary.perlin instead; {parameter}"
                )
            else:
                raise NotImplementedError(f"Dont know how to vary {parameter}")

    return data


def handle_heatpump_values(rand: np.random.Generator, hp_data: HeatPump) -> HeatPump:
    """
    Processes each entry of the `vampireman.data_structures.ValueTimeSeries` in the operational heat pump parameters in
    sequence.
    If the value is a scalar, it is left as-is, if it is a `vampireman.data_structures.ValueMinMax`, a random value is
    calculated.
    """

    assert isinstance(hp_data.injection_temp, ValueTimeSeries)
    assert isinstance(hp_data.injection_rate, ValueTimeSeries)

    for timestep, value in hp_data.injection_temp.values.items():
        # Iterate over each of the heat pumps time value
        if isinstance(value, ValueMinMax):
            # Value is given as min/max
            hp_data.injection_temp.values[timestep] = value.max - (rand.random() * (value.max - value.min))

    for timestep, value in hp_data.injection_rate.values.items():
        # Iterate over each of the heat pumps time value
        if isinstance(value, ValueMinMax):
            # Value is given as min/max
            hp_data.injection_rate.values[timestep] = value.max - (rand.random() * (value.max - value.min))

    return hp_data


def generate_heatpump_location(state: State) -> list[float]:
    """
    Return a list of three random float values, cell based.
    """

    random_vector = state.get_rng().random(3)
    number_cells = np.array([360,360,1])
    viable_cells = number_cells + [76,76,1] # To avoid placing heat pumps on the edges
    random_location = random_vector * cast(np.ndarray, number_cells)
    return cast(list[float], np.ceil(random_location).tolist())


def vary_params(state: State) -> State:
    """
    Calls the `vary_parameter()` function for each `vampireman.data_structures.Parameter` in each
    `vampireman.data_structures.Datapoint` sequentially.
    """

    for datapoint_index in range(state.general.number_datapoints):
        data = {}

        # This syntax merges the hydrogeological_parameters and the heatpump_parameters dicts so we don't have to write
        # two separate for loops
        for _, parameter in (state.hydrogeological_parameters | state.heatpump_parameters).items():
            parameter_data = vary_parameter(state, parameter, datapoint_index)
            data[parameter.name] = parameter_data

        state.datapoints.append(DataPoint(index=datapoint_index, data=data))

    if state.general.shuffle_datapoints:
        state = shuffle_datapoints(state)
        logging.debug("Shuffled datapoints")

    return state


def shuffle_datapoints(state: State) -> State:
    """
    Shuffles all `vampireman.data_structures.Parameter`s randomly in between the different
    `vampireman.data_structures.DataPoint`s.
    This is needed when e.g. two parameters are generated as `vampireman.data_structures.Vary.CONST` with
    `vampireman.data_structures.ValueMinMax`, as otherwise they would both have min values in the first
    `vampireman.data_structures.DataPoint` and max values in the last one.
    """

    parameters: dict[str, list[Data]] = {}

    parameter_names = list(state.datapoints[0].data)
    for parameter in parameter_names:
        for datapoint in state.datapoints:
            param_list = parameters.get(parameter, [])
            param_list.append(datapoint.data[parameter])
            parameters[parameter] = param_list

        state.get_rng().shuffle(cast(ArrayLike, parameters[parameter]))

    for parameter in parameter_names:
        for index in range(state.general.number_datapoints):
            state.datapoints[index].data[parameter] = parameters[parameter][index]

    return state
