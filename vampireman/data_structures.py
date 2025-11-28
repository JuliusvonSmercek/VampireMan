"""
This file holds all data structures that are used throughout the software.
"""

# ruff: noqa: F722
import datetime
import enum
import inspect
import logging
import warnings
from pathlib import Path
from types import NoneType

import numpy as np

# This supresses unwanted output as the library tries to write to its installation directory
with warnings.catch_warnings(action="ignore"):
    from numpydantic import NDArray, Shape
from pydantic import BaseModel, ConfigDict, Field, PositiveInt, field_validator, model_validator
from ruamel.yaml import YAML

yaml = YAML(typ="safe")


def make_value_3d(value: list[float] | NDArray) -> list[float] | NDArray:
    """
    Ensure a value is given in three dimensional space.
    When a two dimensional item is given, the third dimension is amended as `1`.
    """

    if len(value) == 2:  # pyright: ignore
        if isinstance(value, NDArray):  # pyright: ignore
            value = np.append(value, 1)  # pyright: ignore
        else:
            value.append(1)  # pyright: ignore

    if len(value) != 3:  # pyright: ignore
        raise ValueError("Value must be given in three dimensional space")

    return value


class Distribution(enum.StrEnum):
    """
    The distribution of the value during variation.
    """

    UNIFORM = "uniform"
    LOG = "logarithmic"


class Vary(enum.StrEnum):
    """
    This represents the vary mode of `Parameter.vary`.
    """

    FIXED = "fixed"
    """
    Don't vary the `Parameter` at all.
    Variation stage simply takes `Parameter.value` and copy it over to the `Data` item in the `DataPoint`.
    """

    CONST = "const_within_datapoint"
    """
    The `Parameter` will be varied constantly within the `DataPoint`, so the `Parameter.value` won't change within this
    `DataPoint`.
    The value will, however, be varied across the whole datasets, i.e., `State.datapoints`.
    """

    SPACE = "spatially_vary_within_datapoint"
    """
    `Parameter.value` will be varied spatially within the `DataPoint` and also across the dataset.
    E.g., this could be the permeability that varies within the `DataPoint` with a perlin noise function.
    """


class SimTool(enum.StrEnum):
    """
    Enum behind `GeneralConfig.sim_tool`.
    """

    PFLOTRAN = "pflotran"
    """
    The reference implementation and therefore the default value.
    """


class ValueTimeSpan(BaseModel):
    """
    The timespan that the simulation tool should simulate.
    Value and unit are separated for more flexibility.
    """

    final_time: float = 27.5
    """
    Value component.
    """

    unit: str = "year"
    """
    The default unit is `year`, so when the value is omitted in the settings file, years is assumed.
    Using SI units here doesn't make much sense as we are unlikely to simulate anything other than years.
    """

    model_config = ConfigDict(extra="forbid")

    def __str__(self) -> str:
        """
        Returns time including unit, e.g., `27.5 [year]`.
        """

        return f"{self.final_time} {self.unit}"


class ValueMinMax(BaseModel):
    """
    Datastructure to represent a `min` and a `max` value, e.g., for `Parameter.value`.
    """

    min: float
    max: float

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def ensure_max_ge_min(self):
        """
        Ensure the `ValueMinMax.min` value is smaller or equal to the `ValueMinMax.max` value.
        """

        if self.max < self.min:
            raise ValueError("`max` value must be greater or equal to `min`")
        return self

    def __str__(self) -> str:
        return f"[{self.min} <= {self.max}]"


class ValueTimeSeries(BaseModel):
    """
    This represents a time series value.
    """

    time_unit: str = "year"
    """
    The unit of each of the float values in the `values` dict.
    For valid options see https://docs.opengosim.com/manual/input_deck/units_conventions/ (these are for PFLOTRAN,
    though).
    """

    values: dict[float, ValueMinMax | float]
    """
    Values that represent timesteps and their respective values.
    E.g., `{0: 10, 1: 15}` means, that at timestep `0`, the value is `10` and at timestep `1` the value is `15`.
    """

    def __str__(self) -> str:
        string = []
        for key, value in self.values.items():
            string.append(f"\n[{key} {self.time_unit}]: {value}")
        return "".join(string)


class ValueXYZ(BaseModel):
    """
    Datastructure to represent a vector of three float values.
    """

    x: float
    y: float
    z: float

    model_config = ConfigDict(extra="forbid")

    def __str__(self) -> str:
        # This "hack" is needed as there is some problem when serializing otherwise
        if inspect.stack()[1].function == "model_dump_json":
            return {"x": self.x, "y": self.y, "z": self.z}  # pyright: ignore
        return super().__str__()


class ValuePerlin(BaseModel):
    """
    Datastructure to represent a perlin noise value for `Parameter.value`.
    """

    frequency: ValueMinMax | list[float]
    """
    The larger these values are, the more fine grained the perlin field will be (i.e., the smaller the "dots" are and
    how many of them).

    Can either be a fixed three dimensional list of floats, in which case the value will simply be taken as is,
    or `ValueMinMax`, in which case the min and max values describe a range in which three floats are
    being generated.
    """

    max: float
    min: float

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def ensure_3d_if_list(self):
        """
        If frequency is a list, check if it is 3d.
        """

        if isinstance(self.frequency, list):
            make_value_3d(self.frequency)
        return self

    @model_validator(mode="after")
    def ensure_max_ge_min(self):
        """
        Ensure the `ValuePerlin.min` value is smaller or equal to the `ValuePerlin.max` value.
        """

        if self.max < self.min:
            raise ValueError("`max` value must be greater or equal to `min`")
        return self

    def __str__(self) -> str:
        return f"Freq: {self.frequency}, [{self.min} <= {self.max}]"


class HeatPump(BaseModel):
    """
    Datastructure representing a single heat pump.
    A heat pump has a location, an injection temperature and an injection rate.
    """

    location: list[float] | None
    """
    The location where the `HeatPump` should be.
    It is given in cells, the program translates the cell-based location into coordinates matching the domain by
    multiplying it by the `GeneralConfig.cell_resolution`.
    If the `HeatPump` shall be varied spatially, set this to None as otherwise the user would have to provide unique
    values for the locations to circumvent the duplicates check.
    """

    injection_temp: ValueTimeSeries | ValueMinMax | float
    """
    The injection temperature of the `HeatPump` in degree Celsius.
    """

    injection_rate: ValueTimeSeries | ValueMinMax | float
    """
    The injection rate of the `HeatPump` in m^3/s.
    """

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def check_and_fix_location(self):
        """
        If location is given, make it 3d.
        """
        if isinstance(self.location, list):
            make_value_3d(self.location)
        return self

    def __str__(self) -> str:
        location_string = (
            f"X:{self.location[0]} Y:{self.location[1]} Z:{self.location[2]}" if self.location is not None else "None"
        )
        return f"{location_string}\nTemp: {self.injection_temp}\nRate: {self.injection_rate}"


class HeatPumps(BaseModel):
    """
    Datastructure representing a set of heat pumps.
    During the `vampireman.pipeline.prepare_parameters` stage, the individual `HeatPump`s will be generated from this.

    Using `State.get_rng`, values between min and max are chosen for each of the generated `HeatPump`s.
    """

    number: PositiveInt
    """
    How many `HeatPump`s to generate.
    """

    injection_temp: ValueTimeSeries | ValueMinMax | float
    injection_rate: ValueTimeSeries | ValueMinMax | float

    model_config = ConfigDict(extra="forbid")


class Parameter(BaseModel):
    """
    This class encompasses all information needed to derive a concrete value for a given data item in a data point.
    All entries from the `heatpump_parameters` and the `hydrogeological_parameters` section in the settings file will
    get parsed into this data structure.
    """

    name: str
    """
    The name of the parameter.
    This is set to the name of the key in the settings file.
    """

    value: (
        float
        | list[int]
        | HeatPumps
        | HeatPump
        | ValuePerlin
        | ValueMinMax
        | ValueXYZ
        | Path  # Could use pydantic.FilePath here, but then tests fail as cwd does not match
        | NDArray[Shape["*, ..."], (np.float64,)]  # pyright: ignore
    )
    """
    There are so many different options for the value so the settings file can be as flexible as it is.
    Parameter values are parsed from the settings file and checked for a match in the order of appearance in the type
    list.
    """

    distribution: Distribution = Distribution.UNIFORM
    vary: Vary = Vary.FIXED

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    @field_validator("value")
    @classmethod
    def make_path(cls, value):
        """
        If NDArray is of type path, make it a Path.
        """

        if isinstance(value, np.ndarray) and value.ndim == 0:
            return Path(str(value))

        return value

    @model_validator(mode="after")
    def check_heatpump_location(self):
        """
        If HeatPump location is None, the vary mode must be SPACE.
        """

        if (
            isinstance(self.value, HeatPump)
            and isinstance(self.value.location, NoneType)
            and self.vary is not Vary.SPACE
        ):
            raise ValueError("HeatPump location is only allowed to be null/None when vary mode is SPACE")

        return self

    def __str__(self) -> str:
        value_string = str(self.value)
        value_string = value_string.split("\n")
        value_string = "\n      ".join(value_string)
        return (
            f"===== {self.name}: Distribution: {self.distribution}, "
            f"Vary: {self.vary}, type(): {type(self.value)}\n"
            f"      Value: {value_string}\n"
        )


class Data(BaseModel):
    """
    This class represents a data item.
    A data item is a concrete value for a `Parameter` in a given `DataPoint`.
    """

    name: str
    """
    This is set to `Parameter.name`.
    """

    value: int | float | list[int] | list[float] | HeatPump | ValueXYZ | NDArray | str
    """
    Calculated value, derived from `Parameter.value` and `Parameter.vary` in a specific `DataPoint`.
    """

    model_config = ConfigDict(extra="forbid")

    def __str__(self) -> str:
        value = "ndarray" if isinstance(self.value, np.ndarray) else self.value
        return f"===== {self.name} [{type(self.value)}]: {value}"


class DataPoint(BaseModel):
    """
    A collection of several data points.
    """

    index: int
    """
    To enumerate `DataPoint`s.
    """

    data: dict[str, Data]
    """
    All `Data` items for this data point.
    """

    model_config = ConfigDict(extra="forbid")

    def __str__(self) -> str:
        data_strings = []

        for _, value in self.data.items():
            value_string = str(value)
            value_string = value_string.split("\n")
            value_string = "\n      ".join(value_string)

            data_strings.append(value_string)

        return f"=== DataPoint #{self.index}\n" f"{"\n".join(data_strings)}"


class ModelParameters(BaseModel):
    """
    This class holds model parameters for the neural network.

    This information will be used to calculate what the output size of the model will be, such that heatpumps can be places only within the valid output region.
    """

    kernel_size: int
    stride: int
    padding: int
    depth: int
    convs_per_block: int
    boundary_buffer: float  # buffer around the output region where heatpumps cannot be placed in percent


class GeneralConfig(BaseModel):
    """
    The `GeneralConfig` holds values that don't change during execution of the program.
    It can be seen as a collection of all "numerical" and VampireMan parameters.
    """

    number_cells: NDArray[Shape["3 number_cells"], int] | NDArray[Shape["2 number_cells"], int] = Field(  # pyright: ignore[reportInvalidTypeArguments]
        default_factory=lambda: np.array([32, 256, 1])
    )
    """
    Specifies the number of cells for the simulation.
    Must be either two or three dimensional.
    """

    cell_resolution: float = 5.0
    """
    Resolution of the cells.
    Cells can only be cubic.
    """

    shuffle_datapoints: bool = True
    """
    Whether or not to shuffle the order the calculated `Data` from each parameter appears in the `DataPoint`s.
    """

    interactive: bool = True
    """
    Whether or not to run interactively.
    Setting this to `False` is useful in a CI or an unattended run on an HPC Cluster.

    When running in interactive mode, the execution halts between each of the selected stages and asks the user for
    confirmation to proceed.
    Also, if any expected problems occur during execution, e.g., the `pflotran.h5` file is already present, the user is
    asked what to do.

    When running in non-interactive mode, like a `--force` option, data loss can happen.
    """

    output_directory: Path = Path(f"./datasets_out/{datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")}")
    """
    The directory to output the generated datasets.
    Will be created if not existing.

    The default is in the format `2024-08-17T10:06:15+00:00` and is hopefully supported by the common file systems.
    """

    # This forces every run to be reproducible by default
    random_seed: None | int = 0
    """
    This random seed will be passed to the numpy random number generator.
    By default the value is 0, meaning that a given set of input parameters (read from a settings file) always produces
    the same outputs.
    If the used simulation tool is deterministic, then the same inputs yield the same simulation results.
    This is the case for PFLOTRAN.

    Setting this to another fixed value will yield (still deterministic) different results.

    Setting this value to `None`, or rather `null` in a YAML settings file, will always use a random value for the
    random seed, making it nondeterministic.
    """

    number_datapoints: PositiveInt = 1
    """
    The number of datapoints to be generated.
    """

    time_to_simulate: ValueTimeSpan = Field(default_factory=lambda: ValueTimeSpan())
    """
    Influences the timespan of the simulation.
    """

    sim_tool: SimTool = SimTool.PFLOTRAN
    """
    In essence, this states which simulation tool specific functions should be called during later stages of the
    pipeline.
    """

    profiling: bool = False
    """
    If set to `True`, the stages are being profiled and `<case-name>_<stage-name>.<function-name>.txt` files are
    being written in the `./profiling` directory.
    Also, the execution times of the stages are logged. This can help during development but is probably not something a
    user of the program should use.
    """

    mpirun: bool = True
    """
    If the simulation tool should be called by running `mpirun -n x <simulationtool>` or simply `<simulationtool>`.
    """

    mpirun_procs: None | PositiveInt = 1
    """
    When `GeneralConfig.mpirun` is set to `True`, specifies the number of ranks being used, i.e. the `x` in `mpirun -n x
    <simulationtool>`.
    Setting this to `None` is equal to running `mpirun <simulationtool>` without the `-n` and will make mpirun use all
    available cores, you probably want to use this, however it breaks reproducibility.
    Therefore, the value of `1` is the default.
    """

    mpirun_gpu: bool = False
    """
    When `GeneralConfig.mpirun_gpu` is set to `True`, the simulation tool is run with GPU support.
    This requires that the simulation tool was compiled with GPU support.

    Attention: Please set `GeneralConfig.mpirun_procs` accordingly to the number of available GPUs, e.g. if you have 2
    GPUs, set `GeneralConfig.mpirun_procs` to `2`.
    """

    mute_simulation_output: bool = False
    """
    Some simulation tools produce output that can be muted.
    This option disables the output.
    """

    skip_visualization: bool = False
    """
    Whether to skip the visualization stage or not.
    Useful for generating data sets with many data points.
    """

    model_parameters: ModelParameters = None
    """
    If the parameters for the neural network model
    """


    # This makes pydantic fail if there is extra data in the YAML settings file that cannot be parsed
    model_config = ConfigDict(extra="forbid")

    _validated_3d = field_validator("number_cells")(make_value_3d)

    def __str__(self) -> str:
        mpi_string = "disabled" if not self.mpirun else "enabled"
        if self.mpirun and self.mpirun_procs:
            mpi_string += f", {self.mpirun_procs} procs"
        return (
            f"=== GeneralConfig\n"
            f"    mpirun: {mpi_string}\n"
            f"    Interactive: {self.interactive}\n"
            f"    Output directory: {self.output_directory}\n"
            f"    Random seed: {self.random_seed}\n"
            f"    Number of datapoints: {self.number_datapoints}\n"
            f"    Using simulation tool: {self.sim_tool}\n"
            f"    Number of cells: {self.number_cells}\n"
            f"    Cell resolution: {self.cell_resolution}\n"
            f"    Time to simulate: {str(self.time_to_simulate)}\n"
            f"    Profiling: {self.profiling}\n"
        )


class State(BaseModel):
    # Need to use field here, as otherwise it would be the same dict across several objects
    general: GeneralConfig = Field(default_factory=lambda: GeneralConfig())
    """
    The `GeneralConfig`.
    """

    hydrogeological_parameters: dict[str, Parameter] = Field(
        default_factory=lambda: {
            "permeability": Parameter(
                name="permeability",
                vary=Vary.FIXED,
                value=1.29e-10,
            ),
            "pressure_gradient": Parameter(
                name="pressure_gradient",
                vary=Vary.FIXED,
                value=-0.0025,
            ),
            "temperature": Parameter(
                name="temperature",
                vary=Vary.FIXED,
                value=10.6,
            ),
            "porosity": Parameter(
                name="porosity",
                vary=Vary.FIXED,
                value=0.25,
            ),
        }
    )
    """
    All parameters from the `hydrogeological_parameters` section of the settings file will be put into this dict.
    It defines some sane defaults that will be used if not provided by the user, removing the need to explicitly specify
    all values.
    If for instance a `porosity` value is supplied but nothing else, the `State` will still be initialized with the
    default values for `permeability`, `pressure_gradient`, and `temperature`.
    """

    heatpump_parameters: dict[str, Parameter] = Field(
        default_factory=lambda: {
            "hp1": Parameter(
                name="hp1",
                vary=Vary.FIXED,
                value=HeatPump(
                    location=[16, 32, 1],
                    injection_temp=13.6,
                    injection_rate=0.00024,
                ),
            )
        }
    )
    """
    All parameters from the `heatpump_parameters` section of the settings file will be put into this dict.
    This defines the default `heatpump_parameters`.
    It creates a single heat pump.

    IMPORTANT: if given a user settings file that specifies heat pump `hp2` and `hp3`, the `hp1` from the defaults will
    get discarded unlike the `hydrogeological_parameters`!
    If `hp1` should be used when there are other heat pumps, it must be specified along the others in the settings file.
    """

    datapoints: list[DataPoint] = Field(default_factory=lambda: [])
    """
    This represents the input portion of the data set.
    Cannot be provided via a settings file, this is generated and filled by VampireMan during execution.
    """

    _rng: np.random.Generator = np.random.default_rng(seed=0)
    """
    The random number generator that should be used whenever randomness is needed throughout the execution of the
    program.
    It is initialized with `GeneralConfig.random_seed`.
    When initialized with `None`, it will be nondeterministic.
    """

    # This makes pydantic fail if there is extra data in the YAML settings file that cannot be parsed
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    def put_parameter_name_into_data(cls, data):
        """
        This "validator" only copies the name of a parameter into the dict so it is accessible.
        """

        for name, parameter in data.get("hydrogeological_parameters", {}).items():
            parameter["name"] = name
        for name, parameter in data.get("heatpump_parameters", {}).items():
            parameter["name"] = name
        return data

    @model_validator(mode="after")
    def instantiate_random_number_generator(self):
        """
        This "validator" instantiates the global RNG.
        """

        self._rng = np.random.default_rng(seed=self.general.random_seed)
        return self

    @model_validator(mode="after")
    def check_all_or_none_file_paths(self):
        """
        Check if one of the parameters `permeability`, `pressure_gradient`, or `temperature` is a file, then all must
        be.
        """

        # Get all parameters
        permeability = self.hydrogeological_parameters.get("permeability")
        pressure_gradient = self.hydrogeological_parameters.get("pressure_gradient")
        temperature = self.hydrogeological_parameters.get("temperature")

        # Override with True where value is a Path to a file
        if permeability is not None and isinstance(permeability.value, Path):
            if not permeability.vary == Vary.FIXED:
                raise ValueError("When providing a Path, vary mode must be FIXED")
            permeability = True
        else:
            permeability = False
        if pressure_gradient is not None and isinstance(pressure_gradient.value, Path):
            if not pressure_gradient.vary == Vary.FIXED:
                raise ValueError("When providing a Path, vary mode must be FIXED")
            pressure_gradient = True
        else:
            pressure_gradient = False
        if temperature is not None and isinstance(temperature.value, Path):
            if not temperature.vary == Vary.FIXED:
                raise ValueError("When providing a Path, vary mode must be FIXED")
            temperature = True
        else:
            temperature = False

        # If any of the parameters is True, all must be. Otherwise if none is True, its also fine
        if not (permeability == pressure_gradient == temperature):
            raise ValueError(
                "If any of the parameters `permeability`, `pressure_gradient` or `temperature` is a Path, all must be"
            )

        return self

    @model_validator(mode="before")
    def prevent_datapoints_to_be_set(cls, data):
        """
        This prevents setting the `GeneralConfig.datapoints` property.
        """

        if data.get("datapoints") is not None:
            raise ValueError("Not allowed to specify `datapoints` parameter directly.")
        return data

    def override_with(self, other_state: "State"):
        """
        Override this `State` with another given `State` object.
        Will discard current `_rng`, `GeneralConfig`, current `heatpump_parameters`, and `datapoints`, but will merge
        `hydrogeological_parameters`.
        """

        self.general = other_state.general
        self.hydrogeological_parameters |= other_state.hydrogeological_parameters
        self.heatpump_parameters = other_state.heatpump_parameters
        self.datapoints = other_state.datapoints
        self._rng = other_state._rng

    def get_rng(self) -> np.random.Generator:
        """
        Returns the execution-wide same instance of the random number generator instantiated with
        `GeneralConfig.random_seed`.
        If using randomness of any kind, the RNG returned by this function should be used to make results as
        reproducible as possible.
        """

        return self._rng

    @staticmethod
    def from_yaml(settings_file_path: str) -> "State":
        """
        Reads in a YAML file from `settings_file_path` and returns a `State` object with the provided values.
        """

        logging.debug("Trying to load config from %s", settings_file_path)
        try:
            with open(settings_file_path, encoding="utf-8") as state_file:
                yaml_values = yaml.load(state_file)
        except OSError as err:
            logging.error("Could not open settings file '%s', %s", settings_file_path, err)
            raise err
        logging.debug("Loaded state from %s", settings_file_path)
        logging.debug("YAML: %s", yaml_values)

        return State(**yaml_values)

    def __str__(self) -> str:
        parameter_strings = []
        for _, parameter in (self.hydrogeological_parameters | self.heatpump_parameters).items():
            parameter_strings.append(str(parameter))

        return (
            f"=== This state will be used ===\n"
            f"\n"
            f"{self.general}\n"
            f"=== Parameters\n\n"
            f"{"\n".join(parameter_strings)}"
            f"\n"
        )
