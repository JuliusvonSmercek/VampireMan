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


def calculate_unet_output(
    input_size: int,
    kernel_size: int,
    stride: int,
    padding: int,
    depth: int,
    convs_per_block: int
) -> int:
    """
    Calculates the valid output size of a U-Net architecture.
    
    Args:
        input_size: Dimension of the square input image.
        kernel_size: Size of the convolution kernel.
        stride: Stride of the convolution.
        padding: Zero-padding added to both sides.
        depth: Number of downsampling/upsampling levels.
        convs_per_block: Number of convolution layers per depth level.
        
    Returns:
        The final spatial dimension (height/width) of the output.
        
    Raises:
        ValueError: If feature map size becomes <= 0 during processing.
    """

    def apply_conv_block(size: int) -> int:
        """Applies N convolutions sequentially using: O = floor((I - K + 2P) / S) + 1"""
        for _ in range(convs_per_block):
            size = (size - kernel_size + 2 * padding) // stride + 1
            if size <= 0:
                raise ValueError(f"Feature map collapsed to {size} during encoding.")
        return size

    current_size = input_size

    # 1. Encoder Path (Conv Block -> MaxPool)
    for _ in range(depth):
        current_size = apply_conv_block(current_size)
        current_size //= 2

    # 2. Bottleneck (Conv Block only)
    current_size = apply_conv_block(current_size)

    # 3. Decoder Path (Upsample -> Conv Block)
    for _ in range(depth):
        current_size *= 2
        current_size = apply_conv_block(current_size)

    return current_size



def generate_heatpump_location(state: State) -> list[float]:
    """
    Return a list of three random float values, cell based.
    """

    assert 3 == len(state.general.number_cells)
    assert 1 == state.general.number_cells[2]

    complete_area = state.general.number_cells
    inner_area = [0, 0, 1]
    for i in [0, 1]:
      inner_area[i] = calculate_unet_output(
        input_size = complete_area[i],
        kernel_size = state.general.model_parameters.kernel_size,
        stride = state.general.model_parameters.stride,
        padding = state.general.model_parameters.padding,
        depth = state.general.model_parameters.depth,
        convs_per_block = state.general.model_parameters.convs_per_block
      )
      inner_area[i] *= 1 - state.general.model_parameters.boundary_buffer

    offset = (complete_area - inner_area) / 2

    random_vector = state.get_rng().random(3)
    random_location = offset + random_vector * cast(np.ndarray, inner_area)
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
