import sys
sys.modules["cloudpickle"] = None

import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

from pymeasure.display.Qt import QtGui
from pymeasure.display.windows import ManagedWindow
from pymeasure.experiment import Procedure, Results, unique_filename, \
    Parameter, FloatParameter, BooleanParameter, IntegerParameter
from pymeasure.instruments.keithley import Keithley6221, Keithley2700
from pymeasure.instruments.oxfordinstruments import ITC503

import zhinst.utils

from time import sleep, time
from pathlib import Path
from shutil import copy
from datetime import datetime
from git import cmd, Repo, exc
import numpy as np
import ctypes
import yaml


# Initialize logger & log to file
log = logging.getLogger("")
file_handler = logging.FileHandler("electrical_switching.log", "a")
file_handler.setFormatter(logging.Formatter(
    fmt="%(asctime)s : %(message)s (%(levelname)s)",
    datefmt="%m/%d/%Y %I:%M:%S %p"
))
log.addHandler(file_handler)

# Register as separate software
myappid = "fna.MeasurementSoftware.ElectricalSwitching"
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
# TODO: more complicated pulsing and probing schemes


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

    AAC_folder = Parameter("Measurement folder",
                           default="D:\\data\\temp\\")
    AAD_filename_base = Parameter("Measurement filename base",
                                  default="electrical_switching")
    AAE_yaml_config_file = Parameter("YAML configuration file",
                                     default="config.yml")

    # general parameters
    number_of_repeats = IntegerParameter("Number of repeats",
                                         default=8)
    probe_delay = FloatParameter("pulse - probe delay", units="s",
                                 default=1)

    # # pulsing parameters
    pulse_amplitude = FloatParameter("Pulse amplitude",
                                     units="A", default=0.1)
    pulse_compliance = FloatParameter("Pulse compliance",
                                      units="V", default=10)
    pulse_length = FloatParameter("Pulse length",
                                  units="ms", default=3)
    pulse_delay = FloatParameter("Delay between pulses within burst",
                                 units="s", default=5)
    pulse_burst_length = IntegerParameter("Number of pulses per burst",
                                          default=1)
    pulse_number_of_bursts = IntegerParameter("Number of bursts",
                                              default=1)

    # probing parameters
    probe_amplitude = FloatParameter("Probe amplitude",
                                     units="V", default=5)
    probe_sensitivity = FloatParameter("Probe sensitivity",
                                       units="V", default=1e-1)
    probe_frequency = FloatParameter("Probe frequency",
                                     units="Hz", default=79)
    probe_time_constant = FloatParameter("Probe time constant",
                                         units="s", default=0.1)
    probe_duration = FloatParameter("Probe duration",
                                    units="s", default=10)

    probe_series_resistance = FloatParameter("Probe series resistance",
                                             units="Ohm", default=2e4)

    # Temperature controller settings
    temperature_control = BooleanParameter("Temperature control",
                                           default=True)
    temperature = FloatParameter("Temperature Set-point",
                                 units="K", default=300.)

    # Define data columns
    DATA_COLUMNS = [
        "Timestamp (s)",
        "Temperature (K)",
        "Pulse number",
        "Pulse configuration",
        "Pulse hits compliance",
        "Probe configuration",
        "Probe amplitude (V)",
        "Probe sensitivity (V)",
        "Probe frequency (Hz)",
        "Probe time constant (s)",
    ]

    max_number_of_probes = 6
    probe_columns = list()
    for i in range(max_number_of_probes):
        probe_columns.extend(
            ["Probe %d x (V)" % (i + 1), "Probe %d y (V)" % (i + 1)]
        )

    DATA_COLUMNS.extend(probe_columns)

    # pre-define default variables
    config = dict()
    row_pulse_hi = 5
    row_pulse_lo = 6
    row_lia_inA = 1
    row_lia_inB = 2
    row_lia_outA = 3
    row_lia_outB = 4

    pulses = {
        "pulse 1": {"high": 1, "low": 2},
        "pulse 2": {"high": 3, "low": 4}
    }

    probes = {
        "Rxy": {"current high": 7,
                "current low": 8,
                "voltage high": 5,
                "voltage low": 6},
    }

    probe_name_mapping = dict()
    pulse_name_mapping = dict()
    pulse_sequence = list()

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

    # Define start-up sequence
    def startup(self):
        """ Set up the properties and devices required for the measurement.
        First the config file is loaded, then the devices are connected and
        the default parameters are set.
        """

        # Load YAML config files
        self.load_yaml_config()
        self.extract_config()

        # Determine pulse sequence
        self.determine_probe_mapping()
        self.determine_pulse_parameters()
        self.determine_probe_parameters()

        # Connect and set up Keithley 2700 as switchboard
        self.k2700 = Keithley2700("GPIB::30::INSTR")

        # Enable to set text on the display of the Keithley 2700
        self.k2700.text_enabled = True
        self.k2700.display_text = "STARTING"

        # Connect everything to ground
        self.k2700.open_all_channels()

        # Connect and set up MFLI as probing lock-in amplifier
        log.info("Connecting to and setting up lock-in amplifier")
        (daq, device, props) = zhinst.utils.create_api_session("dev4285", 6)
        self.lockin = daq
        self.lockin.setInt("/dev4285/sigouts/0/on", 0)
        self.lockin.setInt("/dev4285/sigouts/0/enables/0", 1)
        self.lockin.setInt("/dev4285/sigouts/0/enables/1", 0)
        self.lockin.setInt("/dev4285/sigouts/0/enables/2", 0)
        self.lockin.setInt("/dev4285/sigouts/0/enables/3", 0)

        self.lockin.setInt("/dev4285/sigouts/0/diff", 1)
        self.lockin.setInt("/dev4285/sigins/0/diff", 1)

        self.lockin.setInt('/dev4285/sigins/0/ac', 1)

        self.lockin.setInt('/dev4285/demods/0/enable', 1)
        self.lockin.setInt('/dev4285/demods/1/enable', 0)
        self.lockin.setInt('/dev4285/demods/2/enable', 0)
        self.lockin.setInt('/dev4285/demods/3/enable', 0)

        self.lockin.setInt('/dev4285/demods/0/order', 3)
        self.lockin.setInt('/dev4285/demods/0/oscselect', 0)
        self.lockin.setInt('/dev4285/demods/0/adcselect', 0)
        self.lockin.setDouble('/dev4285/demods/0/harmonic', 1)
        self.lockin.setDouble('/dev4285/demods/0/phaseshift', 0)
        self.lockin.setInt('/dev4285/sigins/0/float', 0)
        self.lockin.setInt('/dev4285/sigins/0/imp50', 0)
        self.lockin.setInt('/dev4285/sigouts/0/imp50', 0)

        # Connect and set up Keithley 6221 as pulsing device
        log.info("Connecting to and setting up pulse source")
        self.k6221 = Keithley6221("GPIB::13::INSTR")
        self.k6221.waveform_abort()
        self.k6221.source_enabled = False

        # Connect and set up temperature controller
        log.info("Connecting to and setting up temperature controller")
        self.temperatureController = ITC503("GPIB::24")
        self.temperatureController.control_mode = "RU"
        self.temperatureController.heater_gas_mode = "AUTO"
        self.temperatureController.auto_pid = True
        self.temperatureController.sweep_status = 0

    # Define measurement procedure
    def execute(self):
        """ Execute the actual measurement. Here only the global outline of
        the measurement is defined, all the actual activities are handled by
        helper functions (in the helpers section of this class).
        """

        # Set (and wait for) the temperature
        if self.temperature_control:
            log.info(f"Setting temperature to {self.temperature} K.")
            self.temperatureController.temperature_setpoint = self.temperature

            log.info("Waiting for temperature.")
            for i in range(8):
                try:
                    self.temperatureController.wait_for_temperature(
                        error=self.temperature * 0.005,
                        timeout=3600 * 4,
                        should_stop=self.should_stop)
                except ValueError:
                    log.error(
                        "Could not complete wait for temperature due to ValueError" +
                        f" Attempt #{i + 1}."
                    )

        # Perform the measurement
        for n in range(self.number_of_repeats):
            for i, pulse_idx in enumerate(self.pulse_sequence):

                # Apply pulse sequence
                self.last_pulse_number += 1
                self.last_pulse_config = pulse_idx
                self.perform_pulsing(pulse_idx)

                # Wait between pulsing and probing
                sleep(self.probe_delay)

                # Check for stop command
                if self.should_stop():
                    return

                # Perform all probes
                for probe_idx in self.probes.keys():
                    self.perform_probing(probe_idx)

                    # Check for stop command
                    if self.should_stop():
                        return

                # Update progress
                self.emit("progress", (n + (i + 1) / len(self.pulse_sequence)
                                       ) / self.number_of_repeats * 100)

            # Update progress
            self.emit("progress", (n + 1) / self.number_of_repeats * 100)

            # Check for stop command
            if self.should_stop():
                return

    # Define stop sequence
    def shutdown(self):
        """ Wrap up the measurement.
        """
        log.info("Shutting down. Setting devices in a safe state.")

        # Disconnect everything
        self.lockin.setInt("/dev4285/sigouts/0/on", 0)
        self.lockin.setInt("/dev4285/sigouts/0/enables/0", 0)
        self.lockin.setInt("/dev4285/sigouts/0/enables/1", 0)
        self.lockin.setInt("/dev4285/sigouts/0/enables/2", 0)
        self.lockin.setInt("/dev4285/sigouts/0/enables/3", 0)

        self.k2700.open_all_channels()
        self.k2700.display_text = "FINISHED!!!!"

        log.info("Finished measurement.")

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
        read_cfg = True
        file = Path(self.AAC_folder) / self.AAE_yaml_config_file
        file_with_software = Path(self.AAE_yaml_config_file)

        # Determine if the YAML file exists in the data folder or the software folder
        if file.is_file():
            log.info("Loading YAML config file from data folder")
        elif file_with_software.is_file():
            log.info("Copying YAML config file to data folder")
            copy(file_with_software, file)
        else:
            log.info("Not using a YAML config file")
            read_cfg = False

        # read or write the config file
        if read_cfg:
            with open(file, "r") as yml_file:
                self.cfg = yaml.full_load(yml_file)
        else:
            log.info("Writing default config (only for the columns) to data folder")

            cfg = {
                "columns": {
                    "pulsing": self.pulses,
                    "probing": self.probes,
                }
            }

            with open(file, "w") as yml_file:
                yaml.dump(cfg, yml_file, default_flow_style=False)

    def extract_config(self):
        """ Extract the loaded config and save to the appropriate variables.
        """
        if "rows" in self.cfg:
            rows_cfg = self.cfg.pop("rows")

            self.row_pulse_hi = rows_cfg["pulse high"]
            self.row_pulse_lo = rows_cfg["pulse low"]
            self.row_lia_inA = rows_cfg["lock-in input A"]
            self.row_lia_inB = rows_cfg["lock-in input B"]
            self.row_lia_outA = rows_cfg["lock-in output A"]
            self.row_lia_outB = rows_cfg["lock-in output B"]

        if "columns" in self.cfg:
            cols_cfg = self.cfg.pop("columns")
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

    def determine_probe_mapping(self):
        """ Map a number to each probe configuration for correct reference throughout
        the measurement script.
        """
        new_probes = dict()

        for i, (probe, probe_params) in enumerate(self.probes.items(), 1):

                self.probe_name_mapping[i] = probe
                new_probes[i] = probe_params

        self.probes = new_probes

    def determine_pulse_parameters(self):
        """ Determine the pulse sequence from either "pulse_number_of_bursts" or (if
        defined) from the "number of bursts" in the config file. The sequence is stored
        in the parameter "pulse_sequence".
        """
        self.pulse_sequence = list()

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
        for probe_params in self.probes.values():
            if "amplitude" not in probe_params:
                probe_params["amplitude"] = self.probe_amplitude
            if "sensitivity" not in probe_params:
                probe_params["sensitivity"] = self.probe_sensitivity
            if "frequency" not in probe_params:
                probe_params["frequency"] = self.probe_frequency
            if "time constant" not in probe_params:
                probe_params["time constant"] = self.probe_time_constant
            if "duration" not in probe_params:
                probe_params["duration"] = self.probe_duration

    def perform_pulsing(self, pulse_idx):
        """ Perform pulsing with the parameters associated with puls_idx

        :param puls_idx: the index/name for the to-be-used probe
        """
        log.info("Pulsing with pulse {}".format(pulse_idx))
        self.k2700.display_text = f"PULSE {pulse_idx}, {self.last_pulse_number:3d}"

        # Get pulse information associated with pulse_idx
        pulse = self.pulses[pulse_idx]

        # Connect pulse channels
        self.k2700.open_all_channels()
        self.k2700.close_rows_to_columns(
            rows=[self.row_pulse_hi, self.row_pulse_lo],
            columns=[pulse["high"], pulse["low"]]
        )

        # Apply pulses
        pulse_timestamp, pulse_hits_compliance = self.apply_pulses()

        # Store the measured voltage
        self.store_measurement({
            "Timestamp (s)": pulse_timestamp,
            "Pulse hits compliance": pulse_hits_compliance,
        })

        # Disconnect pulse channels
        self.k2700.open_all_channels()

    def perform_probing(self, probe_idx):
        """ Perform probing with the parameters associated with probe_idx

        :param probe_idx: the index/name for the to-be-used probe
        """
        log.info("Probing with probe {}".format(probe_idx))
        self.k2700.display_text = f"PROBE {probe_idx}, {self.last_pulse_number:3d}"

        # Get probe information associated with probe_idx
        probe = self.probes[probe_idx]

        # Connect probe channels
        self.k2700.open_all_channels()
        self.k2700.close_rows_to_columns(
            rows=[
                self.row_lia_outA, self.row_lia_outB,
                self.row_lia_inA, self.row_lia_inB,
            ],
            columns=[
                probe["current high"], probe["current low"],
                probe["voltage high"], probe["voltage low"],
            ])

        # Set parameters on lock-in
        self.lockin.set([
            ("/dev4285/demods/0/timeconstant", probe["time constant"]),
            ("/dev4285/oscs/0/freq", probe["frequency"]),
            ("/dev4285/sigouts/0/range", 20),
            ("/dev4285/sigouts/0/amplitudes/0", probe["amplitude"] * np.sqrt(2)),
            ("/dev4285/sigins/0/range", probe["sensitivity"]),
        ])

        time_constant = self.lockin.getDouble("/dev4285/demods/0/timeconstant")
        frequency = self.lockin.getDouble("/dev4285/oscs/0/freq")
        sine_voltage = self.lockin.getDouble("/dev4285/sigouts/0/amplitudes/0") / np.sqrt(2)
        sensitivity = self.lockin.getDouble("/dev4285/sigins/0/range")

        delay = time_constant * 5

        self.lockin.setInt("/dev4285/sigouts/0/on", 1)
        sleep(delay)

        self.lockin.setInt("/dev4285/sigins/0/autorange", 1)

        sleep(delay * 3)

        self.lockin.sync()

        start = time()
        while True:
            # Wait for value to settle
            sleep(delay)

            sample = self.lockin.getSample("/dev4285/demods/0/sample")
            # Probe
            self.store_measurement({
                "Probe configuration": probe_idx,
                "Probe %d x (V)" % (probe_idx): sample["x"][0],
                "Probe %d y (V)" % (probe_idx): sample["y"][0],
                "Probe amplitude (V)": sine_voltage,
                "Probe sensitivity (V)": sensitivity,
                "Probe frequency (Hz)": frequency,
                "Probe time constant (s)": time_constant,
            })

            # stop probing after duration or on should_stop
            if time() - start > probe["duration"] or self.should_stop():
                break

        # Turn off lock-in output
        self.lockin.setInt("/dev4285/sigouts/0/on", 0)
        sleep(1 + delay)

        # # Disconnect probe channels
        self.k2700.open_all_channels()

    def store_measurement(self, data_dict=dict()):
        """ Create the data structure and save data to file.

        :param data_dict: a dictionary containing the data to be saved.
            Keys in this dictionary overwrite the auto-generated values.
        """

        # Create empty data dictionary
        data = {
            "Timestamp (s)": time(),
            "Temperature (K)": np.nan,
            "Pulse number": self.last_pulse_number,
            "Pulse configuration": self.last_pulse_config,
            "Pulse hits compliance": np.nan,
            "Probe configuration": np.nan,
            "Probe amplitude (V)": np.nan,
            "Probe sensitivity (V)": np.nan,
            "Probe frequency (Hz)": np.nan,
            "Probe time constant (s)": np.nan,
        }
        for key in self.probe_columns:
            data[key] = np.nan

        # Fill the appropriate column with data
        data.update(data_dict)

        # Grab temperature if necessary
        if np.isnan(data["Temperature (K)"]):
            for i in range(2):
                try:
                    temperature = self.temperatureController.temperature_1
                except ValueError:
                    log.error(
                        f"Could not get temperature due to ValueError. Attempt #{i + 1}."
                    )
                else:
                    data["Temperature (K)"] = temperature
                    break

        # Write the data
        self.emit("results", data)

    def apply_pulses(self):
        """ Apply the actual pulses. This function is responsible for
        communicating with the devices that are required for the pulsing.
        """

        # For defining single pulses, use a square wave with 100% duty-cycle
        # for a single cycle; pulse-length is then defined by 1 / frequency
        self.k6221.clear()

        self.k6221.waveform_function = "square"
        self.k6221.waveform_amplitude = self.pulse_amplitude
        self.k6221.waveform_offset = 0
        self.k6221.source_compliance = self.pulse_compliance
        self.k6221.waveform_dutycycle = 100
        self.k6221.waveform_frequency = 1e3 / self.pulse_length
        self.k6221.waveform_ranging = "best"
        self.k6221.waveform_duration_cycles = 1

        # Arm the waveform
        self.k6221.waveform_arm()

        pulse_timestamp = None

        # Apply the pulses; each start triggers a single pulse
        for i in range(self.pulse_burst_length):
            sleep(self.pulse_delay)
            self.k6221.waveform_start()

            # Get time stamp for the pulse
            if pulse_timestamp is None:
                pulse_timestamp = time()

            sleep(self.pulse_length * 1e-3)

            # Break if aborted
            if self.should_stop():
                break

        # Wait to ensure the pulse is over and the waveform can be aborted
        sleep(15e-3)

        # Disarm the waveform
        self.k6221.waveform_abort()

        # Check whether the compliance was hit during the pulse
        # This makes use of the status bit registers and specifically reads
        # bit 3 (compliance) of the Measurement Event Register
        event_bytes = self.k6221.measurement_events
        pulse_hits_compliance = int(format(event_bytes, "08b")[-4])

        return pulse_timestamp, pulse_hits_compliance


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
                "pulse_delay",
                "pulse_number_of_bursts",
                "probe_delay",
                "probe_amplitude",
                "probe_sensitivity",
                "probe_frequency",
                "probe_time_constant",
                "probe_duration",
                "probe_series_resistance",
                "temperature_control",
                "temperature",
            ),
            x_axis="Pulse number",
            y_axis="Probe 1 x (V)",
            displays=(
                "pulse_amplitude",
                "pulse_compliance",
                "pulse_length",
                "pulse_burst_length",
                "temperature",
            ),
            sequencer=True,
            inputs_in_scrollarea=True,
        )

    def queue(self, *args, procedure=None):
        if procedure is None:
            procedure = self.make_procedure()

        folder = procedure.AAC_folder
        filename = procedure.AAD_filename_base

        filename = unique_filename(
            folder,
            prefix=filename,
            ext="txt",
            datetimeformat="",
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
