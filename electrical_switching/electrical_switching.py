import sys
sys.modules["cloudpickle"] = None

import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import numpy as np

from pymeasure.display.Qt import QtGui
from pymeasure.display.windows import ManagedWindow
from pymeasure.experiment import Procedure, Results, unique_filename
from pymeasure.experiment import Parameter, FloatParameter, BooleanParameter, IntegerParameter, ListParameter

from pymeasure.instruments.keithley import Keithley2400
from pymeasure.instruments.keithley import Keithley2700
from pymeasure.instruments.srs import SR830

from time import sleep, time

from datetime import datetime
from git import cmd, Repo, exc
import ctypes
import yaml
from pathlib import Path

from pprint import pprint

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

class MeasurementProcedure(Procedure):
    # Define parameters
    AAA = Parameter("Software version", default=version)
    AAB = Parameter("Measurement date", default=date)


    AAC_folder = Parameter('Measurement folder',
                           default='D:\\data\\temp\\')
    AAD_filename_base = Parameter('Measurement filename base',
                                  default='electrical_switching')
    AAE_yaml_config_file = Parameter('YAML channel configuration file',
                                     default='config.yml')

    # # pulsing parameters
    # pulse_amplitude
    # pulse_length
    # pulse_burst_length
    # pulse_burst_delay

    # pulse_probe_delay
    
    # # probing parameters
    # probe_amplitude
    # probe_sensitivity
    # probe_frequency
    # probe_time_constant
    # probe_duration
    # probe_series_resistance



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
        '1': {'high': 1, 'low': 2},
        '2': {'high': 3, 'low': 4}
    }

    probes = {
        'Rxy': {'current high': 7,
                'current low': 8,
                'voltage high': 5,
                'voltage low': 6},
    }

    # Define start-up sequence
    def startup(self):
        # Load YAML config files
        self.load_yaml_config()
        self.extract_config()

        # Connect and set up Keithley 2700 as switchboard

        # Connect everything to ground

        # Connect and set up SR830 as probing lock-in amplifier

        # Connect and set up Keithley 2400 as pulsing device

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
            self.cfg = yaml.safe_load(yml_file)

    def extract_config(self):
        """ Extract the loaded config and save to the appropriate variables.
        """
        if 'rows' in self.cfg:
            rows_cfg = self.cfg.pop('rows')

            row_ground = rows_cfg["ground"]
            row_pulse_hi = rows_cfg["pulse high"]
            row_pulse_lo = rows_cfg["pulse low"]
            row_lia_inA = rows_cfg["lock-in input A"]
            row_lia_inB = rows_cfg["lock-in input B"]
            row_lia_out = rows_cfg["lock-in output"]

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

    # Define measurement procedure
    def execute(self):
        # Connect pulse channels
        # Apply pulses
        # Disconnect pulse channels

        # Connect probe channels
        # Probe
        # Disconnect probe channels
        pass

    # Define stop sequence
    def shutdown(self):
        # Disconnect everything
        pass


class MainWindow(ManagedWindow):
    def __init__(self):
        super(MainWindow, self).__init__(
            procedure_class=MeasurementProcedure,
            inputs=(
                "AAC_folder",
                "AAD_filename_base",
                "AAE_yaml_config_file",

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
# self.emit("progress", progress) progress = 0 - 100
