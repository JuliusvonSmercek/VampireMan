import subprocess
from unittest.mock import patch

from vampireman import preparation_stage, simulation_stage
from vampireman.data_structures import State


def mock_pflotran_call(*args, **kwargs):
    return subprocess.CompletedProcess(args=args, returncode=0, stdout="Done", stderr="")


@patch("subprocess.run", side_effect=mock_pflotran_call)
def test_simulation(mock_run):
    state = State()
    state.general.interactive = False

    state.general.number_datapoints = 5
    state.general.mpirun = True
    state.general.mpirun_procs = 1
    state.general.mute_simulation_output = False
    state = preparation_stage(state)
    simulation_stage(state)
    assert mock_run.call_count == 5
    mock_run.assert_called_with(["mpirun", "-n", "1", "pflotran"], check=True, close_fds=True)

    state.general.mpirun = False
    state = preparation_stage(state)
    simulation_stage(state)
    mock_run.assert_called_with(["pflotran"], check=True, close_fds=True)

    state.general.mpirun = True
    state.general.mpirun_procs = None
    state.general.mute_simulation_output = True
    state = preparation_stage(state)
    simulation_stage(state)
    mock_run.assert_called_with(["mpirun", "pflotran", "-screen_output", "off"], check=True, close_fds=True)
