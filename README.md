# VampireMan

This tool generates data sets based on user input.
It allows a user to declaratively describe how parameters for a data set should be varied.

The software is built in modular stages, forming a pipeline that passes and modifies data.
When given a settings file, the program does the parameter variation for all data points and runs simulations (see [stages](#stages) for more information).

Currently, only the reference implementation of the simulation software `pflotran` is realized.
The minimum required Python version is 3.11.

After installing the dependencies, run `pdoc3 --http localhost:8080 vampireman` and open <http://localhost:8080> in your web browser to enter an interactive code documentation.
For a developer documentation read the [DEV_README.md](./docs/DEV_README.md) file.

## Quickstart

After installing the dependencies (#installation-of-the-software), you can run the default case ([settings](#settings)) by executing `python -m vampireman`.
This command interactively guides you through the stages of the pipeline.
It also renders all files needed to execute a PFLOTRAN simulation to the `output_directory`, which is by default the date in UTC ISO 8601 format `./datasets_out/2024-08-17T10:06:15+00:00`.
Afterwards, the simulations are run and the simulation results are visualized.

When the program has exited successfully, `cd <name of the output directory>` into the directory and look at the results.

Also, have a look at the [tutorial](./docs/TUTORIAL.md).

## Installation of the Software

Currently, there are three supported ways of installing and running the software.
Depending on your environment, choose one of the following.

### Ubuntu

1. Install at least Python 3.11 (e.g., `apt install python3`)
1. Install poetry (e.g., `apt install python3-poetry` or `pip install poetry` if no root rights)
1. [Install PFLOTRAN 6.0.0](https://www.pflotran.org/documentation/user_guide/how_to/installation/installation.html) and remember to include the PFLOTRAN executable in your `PATH` (e.g. by `export PATH="$PFLOTRAN_DIR/bin:$PATH"`)
1. Clone this repository and `cd` into it
1. Install the dependencies from the project root (i.e., `poetry install`)
1. Enter a poetry shell (e.g., `poetry shell`, in newer versions: `eval $(poetry env activate)`)

You can also have a look at the example [Dockerfile](./Dockerfile) to see how to get VampireMan running.

### Installing Nix on a non-NixOS system

This is primarily intended for installing Nix on Uni Stuttgart IPVS Servers.

1. Clone the repository
1. Make sure you have `wget` installed
1. Read ./setup.sh and make sure you understand what it does
1. Run `bash setup.sh` in the project root
1. Log out and in again to apply the changes to the `PATH` environment variable
1. Enter `nix develop` to load the Nix environment

### Nix

1. If you have [Nix](https://nixos.org) and [direnv](https://direnv.net/) installed, simply enter the project root and type in `direnv allow`. Wait for a shell and you are done!

If you don't have direnv, run `nix --experimental-features 'nix-command flakes' develop`.

## Stages

The proposed software has seven stages that are run in sequence, each processing and enhancing the data of the previous stage.
- Loading stage: The configuration file provided by the user is processed and interpreted in this stage.
  Parameters relevant to the simulation are extracted from the loaded configuration.
- Preparation stage: This stage preprocesses supplementary input files, such as permeability field definitions stored in [HDF5](https://www.hdfgroup.org/solutions/hdf5/) files or heat pump configurations in [JSON](https://www.json.org/json-en.html) format, and calculates or expands the required parameter values accordingly.
- Validation stage: This stage ensures that the resulting configuration, after reading in any files and expanding parameters, is valid, i.e., at least the parameters `pressure_gradient`, `permeability`, and `temperature` are set and there is at least one heat pump in the domain.
- Variation stage: The variation stage generates data points based on parameter values and associated metadata.
- Render stage: This stage prepares the simulation environment by compiling and storing all necessary input files in their designated directories for the integration with the simulation program.
- Simulation stage: In this stage, the simulation program is invoked, optionally with additional command line switches, depending on the user provided settings.
- Visualization stage: After the simulation stage has completed, visualization stage renders the output of the simulations to facilitate understanding and analysis of the groundwater heat pump system's behavior.

## Settings / Example Cases

There are several example settings in [the settings directory](./settings).
Those settings are written in [YAML](https://yaml.org/) represent test cases and are also semantically validated when running Pytest.
These files can also include other files by specifying a file path as a value.
Supported file formats are ASCII, JSON and HDF5.

In these examples, all grids are cartesian and have three dimensions with a cell resolution of 5 meters in each dimension.
Two dimensional grids are implicitly converted to three dimensions by adding a `z` coordinate with the value of 1, meaning a height of 1 cell.

Further, all cases have the similarities:
- random seed is always set to `0`
- output directory is set to `./datasets_out/<casename>`.
- simulation tool is `pflotran`
- profiling is disabled
- simulation time is 27.5 years
- interactive is set to false
- groundwater temperature is always fix to 10.6 degrees Celsius, except case 10, there it is varying const

| case                                           | grid          | datapoint(s) | heat pump(s)   | permeability | pressure gradient | additional specialties                                           |
|------------------------------------------------|---------------|--------------|----------------|--------------|-------------------|------------------------------------------------------------------|
| [0](./settings/case0_default.yaml)             | (32,256,1)    | 1            | 1 fix          | fix          | fix               |                                                                  |
| [1](./settings/case1_vary-pressure-const.yaml) | (32,256,1)    | 2            | 1 fix          | const        | const             |                                                                  |
| [2](./settings/case2_vary-hp-positions.yaml)   | (32,512,1)    | 2            | 1 fix, 2 space | fix          | fix               |                                                                  |
| [3](./settings/case3_allin1.yaml)              | (32,512,1)    | 3            | 2 space        | space        | fix               |                                                                  |
| [4](./settings/case4_extend-plumes.yaml)       | (32,1280,1)   | 3            | 1 fix          | space        | const             |                                                                  |
| [5](./settings/case5_3d.yaml)                  | (32,256,32)   | 1            | 1 fix          | fix          | fix               |                                                                  |
| [6](./settings/case6_vertical_aniso.yaml)      | (32,256,32)   | 1            | 1 fix          | space        | fix               | vertical anisotropy ratio of 10                                  |
| [7](./settings/case7_read-from-files.yaml)     | (32,256,1)    | 1            | 1 fix          | fix          | fix               | heat pump, permeability and pressure gradient are read from file |
| [8](./settings/case8_heatpumps-in-detail.yaml) | (32,256,1)    | 3            | 4 fix, 2 space | fix          | fix               | operational heatpump parameters specified in more detail         |
| [9](./settings/case9_seasonal-changes.yaml)    | (32,512,1)    | 1            | 2 fix          | fix          | fix               | time based changes in heat pump injection temperature and rate   |
| [10](./settings/case10_all-features.yaml)      | (32,256,1)    | 3            | 2 fix, 5 space | space        | fix               | case shows all supported features of the software                |
| [11](./settings/case11_large-domain.yaml)      | (320,2560,32) | 1            | 50 space       | space        | fix               |                                                                  |
| [seasonal](./settings/seasonal/seasonal.yaml)  | (1000,1000,1) | 26           | 15 space       | space        | fix               |                                                                  |


## Additional Authors

Julius von Smercek and Johanna Betz contributed the seasonal test case and usability improvements.

### Seasonal test case

The seasonal case is defined in [`./settings/seasonal/seasonal.yaml`](./settings/seasonal/seasonal.yaml). It models one full year with 26 data points and uses seasonal heating and cooling load ratios (`heating_load_ratio.csv` and `cooling_load_ratio.csv`) derived from [https://github.com/tum-ens/UrbanHeatPro](https://github.com/tum-ens/UrbanHeatPro) together with building data from Munich.

Run it like the other example cases by passing the settings file to the program:

```bash
python -m vampireman ./settings/seasonal/seasonal.yaml
```

The PFLOTRAN template assumes cyclic injection data by default and stores intermediate results every 0.5 years.

### Related changes

- fixed a compatibility issue with PFLOTRAN command-line arguments
- added visualization of progress and an estimate when data generation has finished
- added GPU-based data generation
- added support for placing randomly generated heat pumps in the middle of the domain instead of near the boundaries
- added support for specifying the minimum distance between two randomly generated heat pump locations
