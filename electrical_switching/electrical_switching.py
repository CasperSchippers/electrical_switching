import sys
sys.modules["cloudpickle"] = None

import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

from pymeasure.display.Qt import QtGui
from pymeasure.display.windows import ManagedWindow
from pymeasure.experiment import Procedure, Results, unique_filename, \
    Parameter, FloatParameter, BooleanParameter, \
    IntegerParameter, ListParameter
from pymeasure.instruments.keithley import Keithley2400, Keithley2700
from pymeasure.instruments.srs import SR830

from time import sleep, time
from pprint import pprint
from pathlib import Path
from datetime import datetime
from git import cmd, Repo, exc
import numpy as np
import ctypes
import yaml


# Initialize logger & log to file
log = logging.getLogger('')
file_handler = logging.FileHandler('electrical_switching.log', 'a')
file_handler.setFormatter(logging.Formatter(
    fmt='%(asctime)s : %(message)s (%(levelname)s)',
    datefmt='%m/%d/%Y %I:%M:%S %p'
))
log.addHandler(file_handler)

# Register as separate software
myappid = 'fna.MeasurementSoftware.ElectricalSwitching'
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

# get Git software version
try:
    version = cmd.Git(Repo(search_parent_directories=True)).describe()
except exc.GitCommandError:
    version = "none"

# Get date of measurement
date = datetime.now()

r"""
 _____    _____     ____     _____   ______   _____    _    _   _____    ______
|  __ \  |  __ \   / __ \   / ____| |  ____| |  __ \  | |  | | |  __ \  |  ____|
| |__) | | |__) | | |  | | | |      | |__    | |  | | | |  | | | |__) | | |__
|  ___/  |  _  /  | |  | | | |      |  __|   | |  | | | |  | | |  _  /  |  __|
| |      | | \ \  | |__| | | |____  | |____  | |__| | | |__| | | | \ \  | |____
|_|      |_|  \_\  \____/   \_____| |______| |_____/   \____/  |_|  \_\ |______|

"""


class MeasurementProcedure(Procedure):
    r"""
     _____        _____            __  __ ______ _______ ______ _____   _____
    |  __ \ /\   |  __ \     /\   |  \/  |  ____|__   __|  ____|  __ \ / ____|
    | |__) /  \  | |__) |   /  \  | \  / | |__     | |  | |__  | |__) | (___
    |  ___/ /\ \ |  _  /   / /\ \ | |\/| |  __|    | |  |  __| |  _  / \___ \
    | |  / ____ \| | \ \  / ____ \| |  | | |____   | |  | |____| | \ \ ____) |
    |_| /_/    \_\_|  \_\/_/    \_\_|  |_|______|  |_|  |______|_|  \_\_____/

    """

    AAA = Parameter("Software version", default=version)
    AAB = Parameter("Measurement date", default=date)

    AAC_folder = Parameter('Measurement folder',
                           default='D:\\data\\temp\\')
    AAD_filename_base = Parameter('Measurement filename base',
                                  default='electrical_switching')
    AAE_yaml_config_file = Parameter('YAML configuration file',
                                     default='config.yml')

    # general parameters
    number_of_repeats = IntegerParameter("Number of repeats",
                                         default=8)
    probe_delay = FloatParameter("pulse - probe delay", units="s",
                                 default=1)

    # # pulsing parameters
    pulse_amplitude = FloatParameter("Pulse amplitude", units="A",
                                     default=1)
    pulse_compliance = FloatParameter("Pulse compliance", units="V",
                                     default=1)
    pulse_length = FloatParameter("Pulse length", units="V",
                                  default=1)
    pulse_burst_delay = FloatParameter("Pulse length", units="s",
                                  default=1)
    pulse_burst_length = IntegerParameter("Number of pulses per burst",
                                          default=1)
    pulse_number_of_bursts = IntegerParameter("Number of bursts",
                                              default=1)

    
    # # probing parameters
    probe_amplitude = FloatParameter("Probe amplitude", units="V",
                                     default=1)
    probe_sensitivity = FloatParameter("Probe sensitivity", units="V",
                                       default=1e-1)
    probe_frequency = FloatParameter("Probe frequency", units="Hz",
                                     default=79)
    probe_time_constant = FloatParameter("Probe time constant", units="s",
                                         default=0.1)
    probe_duration = FloatParameter("Probe duration", units="s",
                                    default=1)

    probe_series_resistance = FloatParameter("Probe series resistance", units="Ohm",
                                             default=1)


    # Define data columns
    DATA_COLUMNS = [
        "Timestamp (s)",
        "Pulse number",
        "Pulse direction",
    ]

    # pre-define default variables
    config = dict()
    row_ground = 4
    row_pulse_hi = 5
    row_pulse_lo = 6
    row_lia_inA = 1
    row_lia_inB = 2
    row_lia_out = 3

    pulses = {
        'pulse 1': {'high': 1, 'low': 2},
        'pulse 2': {'high': 3, 'low': 4}
    }

    probes = {
        'Rxy': {'current high': 7,
                'current low': 8,
                'voltage high': 5,
                'voltage low': 6,
                'sensitivity': 2e-4},
    }

    probe_name_mapping = Parameter("Probe name mapping", default=dict())
    pulse_name_mapping = Parameter("Pulse name mapping", default=dict())
    pulse_sequence = Parameter("Pulse sequence", default=list())

    # Pulse counter
    last_pulse_number = 0
    last_pulse_config = 0

    r"""
          ____    _    _   _______   _        _____   _   _   ______
         / __ \  | |  | | |__   __| | |      |_   _| | \ | | |  ____|
        | |  | | | |  | |    | |    | |        | |   |  \| | | |__
        | |  | | | |  | |    | |    | |        | |   | . ` | |  __|
        | |__| | | |__| |    | |    | |____   _| |_  | |\  | | |____
         \____/   \____/     |_|    |______| |_____| |_| \_| |______|
    
    """

    def __init__(self, **kwargs):
        super(MeasurementProcedure, self).__init__(**kwargs)

        # Load YAML config files
        self.load_yaml_config()
        self.extract_config()

        # Determine pulse sequence
        self.determine_pulse_parameters()
        self.determine_probe_parameters()


    # Define start-up sequence
    def startup(self):
        """ Set up the properties and devices required for the measurement.
        First the config file is loaded, then the devices are connected and
        the default parameters are set.
        """
        # Connect and set up Keithley 2700 as switchboard
        self.k2700 = Keithley2700('GPIB::30::INSTR')

        # Connect everything to ground
        self.k2700.close_rows_to_columns(self.row_ground, "all")

        # Connect and set up SR830 as probing lock-in amplifier
        self.lockin = SR830("GPIB::1")

        # Connect and set up Keithley 2400 as pulsing device
        self.k2400 = Keithley2400('GPIB::2::INSTR')


    # Define measurement procedure
    def execute(self):
        """ Execute the actual measurement. Here only the global outline of
        the measurement is defined, all the actual activities are handled by
        helper functions (in the helpers section of this class).
        """

        for n in range(self.number_of_repeats):
            for i, pulse_idx in enumerate(self.pulse_sequence):

                # Apply pulse sequence
                self.apply_pulses(pulse_idx)
                self.last_pulse_number += 1
                self.last_pulse_config = pulse_idx

                # Wait between pulsing and probing
                sleep(self.probe_delay)

                # Check for stop command
                if self.should_stop(): return

                # Perform all probes
                for probe_idx in self.probes.keys():
                    self.perform_probing(probe_idx)

                    # Check for stop command
                    if self.should_stop(): return

                # Update progress
                self.emit("progress", (n + (i + 1) / len(self.pulse_sequence)
                    ) / self.number_of_repeats * 100)

            # Update progress
            self.emit("progress", (n + 1) / self.number_of_repeats * 100)

            # Check for stop command
            if self.should_stop(): return


    # Define stop sequence
    def shutdown(self):
        """ Wrap up the measurement.
        """
        # Disconnect everything
        pass

    r"""
         _    _   ______   _        _____    ______   _____     _____
        | |  | | |  ____| | |      |  __ \  |  ____| |  __ \   / ____|
        | |__| | | |__    | |      | |__) | | |__    | |__) | | (___
        |  __  | |  __|   | |      |  ___/  |  __|   |  _  /   \___ \
        | |  | | | |____  | |____  | |      | |____  | | \ \   ____) |
        |_|  |_| |______| |______| |_|      |______| |_|  \_\ |_____/

    """

    # Define additional functions
    def load_yaml_config(self):
        """ Load the selected YAML.
        first tries to find the file in the output folder, if
        this cannot be found, load it from the software folder.
        """
        # Try to find config file in output folder
        file = Path(self.AAC_folder) / self.AAE_yaml_config_file

        if not file.is_file():
            file = Path(self.AAE_yaml_config_file)

        with open(file, 'r') as yml_file:
            self.cfg = yaml.full_load(yml_file)

    def extract_config(self):
        """ Extract the loaded config and save to the appropriate variables.
        """
        if 'rows' in self.cfg:
            rows_cfg = self.cfg.pop('rows')

            self.row_ground = rows_cfg["ground"]
            self.row_pulse_hi = rows_cfg["pulse high"]
            self.row_pulse_lo = rows_cfg["pulse low"]
            self.row_lia_inA = rows_cfg["lock-in input A"]
            self.row_lia_inB = rows_cfg["lock-in input B"]
            self.row_lia_out = rows_cfg["lock-in output"]

        if 'columns' in self.cfg:
            cols_cfg = self.cfg.pop('columns')
            if "pulsing" in cols_cfg:
                self.pulses = {
                    k.replace("pulse ", ""): v for k, v in cols_cfg["pulsing"].items()
                }
            if "probing" in cols_cfg:
                self.probes = {
                    k.replace("probe ", ""): v for k, v in cols_cfg["probing"].items()
                }

        if len(self.cfg.keys()) > 0:
            log.info("The config file has additional (unhandled) attributes")

    def determine_pulse_parameters(self):
        """ Determine the pulse sequence from either 'pulse_number_of_bursts' or (if
        defined) from the 'number of bursts' in the config file. The sequence is stored
        in the parameter 'pulse_sequence'.
        """

        for i, (pulse, pulse_params) in enumerate(self.pulses.items(), 1):

            # Check if number of bursts is defined for this pulse:
            if "number of bursts" in pulse_params:
                n = pulse_params["number of bursts"]
            else:
                n = self.pulse_number_of_bursts

            self.pulse_sequence.extend([pulse for _ in range(n)])
            self.pulse_name_mapping[i] = pulse

    def determine_probe_parameters(self):
        """ Determine the probe parameters per probing configuration and check
        whether all required parameters are present in the probe dictionary.
        """

        for i, (probe, probe_params) in enumerate(self.probes.items(), 1):
            if not "amplitude" in probe_params:
                probe_params["amplitude"] = self.probe_amplitude
            if not "sensitivity" in probe_params:
                probe_params["sensitivity"] = self.probe_sensitivity
            if not "frequency" in probe_params:
                probe_params["frequency"] = self.probe_frequency
            if not "time constant" in probe_params:
                probe_params["time constant"] = self.probe_time_constant
            if not "duration" in probe_params:
                probe_params["duration"] = self.probe_duration

                self.probe_name_mapping[i] = probe            

    def apply_pulses(self, pulse_idx):
        log.info('Pulsing with pulse {}'.format(pulse_idx))
        # Connect pulse channels
        # Apply pulses
        # Disconnect pulse channels
        pass

    def perform_probing(self, probe_idx):
        """ Perform probing with the parameters associated with probe_idx

        :param probe_idx: the index/name for the to-be-used probe
        """
        log.info('probing with probe {}'.format(probe_idx))

        probe = self.probes[probe_idx]

        # Connect probe channels
        self.k2700.open_all_channels()
        self.k2700.close_rows_to_columns(
            [
                self.row_lia_out, self.row_ground,
                self.row_lia_inA, self.row_lia_inB,
            ], [
                probe["current high"], probe["current low"],
                probe["voltage high"], probe["voltage low"],
            ])

        # Set parameters on lock-in
        self.lockin.sensitivity = probe["sensitivity"]
        self.lockin.frequency = probe["frequency"]
        self.lockin.time_constant = probe["time constant"]
        self.lockin.sine_voltage = probe["amplitude"]

        delay = probe["time constant"] * 5

        start = time()
        while True:
            # Wait for value to settle
            sleep(delay)

            # Probe
            print("probing", probe_idx)
            print("fix probing")

            # stop probing after duration
            if time() > start + probe["duration"]:
                break

        # Disconnect probe channels
        self.k2700.open_all_channels()
        self.k2700.close_rows_to_columns(self.row_ground, "all")


    def store_measurement(self, ):
        pass


r"""
        __          __  _____   _   _   _____     ____   __          __
        \ \        / / |_   _| | \ | | |  __ \   / __ \  \ \        / /
         \ \  /\  / /    | |   |  \| | | |  | | | |  | |  \ \  /\  / /
          \ \/  \/ /     | |   | . ` | | |  | | | |  | |   \ \/  \/ /
           \  /\  /     _| |_  | |\  | | |__| | | |__| |    \  /\  /
            \/  \/     |_____| |_| \_| |_____/   \____/      \/  \/


"""

class MainWindow(ManagedWindow):
    def __init__(self):
        super(MainWindow, self).__init__(
            procedure_class=MeasurementProcedure,
            inputs=(
                "AAC_folder",
                "AAD_filename_base",
                "AAE_yaml_config_file",
                "number_of_repeats",
                "pulse_amplitude",
                "pulse_compliance",
                "pulse_length",
                "pulse_burst_length",
                "pulse_burst_delay",
                "pulse_number_of_bursts",
                "probe_delay",
                'probe_amplitude',
                'probe_sensitivity',
                'probe_frequency',
                'probe_time_constant',
                'probe_duration',
                "probe_series_resistance",
            ),
            x_axis="Pulse number",
            y_axis="Pulse direction",
        )


    def queue(self, *args, procedure=None):
        if procedure is None:
            procedure = self.make_procedure()

        folder = procedure.AAC_folder
        filename = procedure.AAD_filename_base

        filename = unique_filename(
            folder,
            prefix=filename,
            ext='txt',
            datetimeformat='',
        )

        results = Results(procedure, filename)

        # manual define a curve to deal with nan values
        curve = self.new_curve(results, connect="finite")
        curve.setSymbol("o")
        curve.setSymbolPen(curve.pen)

        experiment = self.new_experiment(results, curve)

        self.manager.queue(experiment)


if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


# self.emit("results", data) data = dict()
