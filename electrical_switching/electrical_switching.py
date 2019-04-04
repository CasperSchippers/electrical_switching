import logging
import sys
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import numpy as np

from pymeasure.display.Qt import QtGui
from pymeasure.display.windows import ManagedWindow
from pymeasure.experiment import Procedure, Results, unique_filename
from pymeasure.experiment import Parameter, FloatParameter, BooleanParameter, IntegerParameter
from pymeasure.instruments.agilent import Agilent33220A
from pymeasure.instruments.srs import SR830

from relaisbox import RelaisBox
from time import sleep, time

from datetime import datetime
# from git import cmd, Repo, exc

# try:
#     version = cmd.Git(Repo(search_parent_directories=True)).describe()
# except exc.GitCommandError:
version = "none"

date = datetime.now()


class MeasurementProcedure(Procedure):
    # Define parameters
    AAA = Parameter("Software version", default=version)
    AAB = Parameter("Measurement date", default=date)

    repeats = IntegerParameter("Repeats", default=20)
    delay = FloatParameter("Delay", default=100, units="s")
    alternations = IntegerParameter("Alternations", default=2)

    total_number_of_pulsetrains = repeats.value * alternations.value
    # measurements = IntegerParameter("Measurements per pulse", default=4)

    LIA_voltage = FloatParameter("Lock-in voltage", default=1, units="V")
    LIA_ramprate = FloatParameter("Lock-in ramp rate", default=1, units="V/s")

    AWG_voltage = FloatParameter("Pulse voltage", default=5, units="V")
    AWG_pulsewidth = FloatParameter("Pulse width", default=200e-6, units="s")
    AWG_pulsespace = FloatParameter("Pulse spacing", default=400e-6, units="s")
    AWG_number = FloatParameter("Number of pulses", default=50000)

    train_length = AWG_number.value * \
        (AWG_pulsespace.value + AWG_pulsewidth.value)
    AWG_pulsetrain_length = FloatParameter("Length of pulse-train",
                                           default=train_length, units="s")

    DATA_COLUMNS = [
        "Timestamp (s)",
        "Pulse number",
        "Pulse direction",
        "Lock-In 1 X (V)",
        "Lock-In 1 Y (V)",
        "Lock-In 1 V (V)",
        "Lock-In 1 f (Hz)",
    ]

    bit_seq_M = [0, 0, 0, 0, 1, 1, 1, 1]
    bit_seq_W1 = [1, 1, 0, 0, 0, 0, 0, 0]
    bit_seq_W2 = [0, 0, 1, 1, 0, 0, 0, 0]

    pulse_number = 0
    last_pulse_dir = 0

    # Define start-up sequence
    def startup(self):
        self.LIA = SR830("GPIB::1")

        self.AWG = Agilent33220A("GPIB::10", clear_buffer=True)

        # Pulse shape
        self.AWG.shape = "pulse"
        self.AWG.pulse_hold = "width"
        self.AWG.pulse_width = self.AWG_pulsewidth
        self.AWG.pulse_period = self.AWG_pulsespace + self.AWG_pulsewidth
        self.AWG.amplitude = self.AWG_voltage
        self.AWG.offset = self.AWG_voltage / 2

        # Pulse Train properties
        self.AWG.burst = True
        self.AWG.burst_ncycles = self.AWG_number
        self.AWG.burst_mode = "TRIGGERED"
        self.AWG.trigger_source = "BUS"

        self.RelBox = RelaisBox(self.LIA, "dac1")
        self.RelBox.pattern = 0

    # Define measurement procedure
    def execute(self):
        self.measure_hall_voltage()
        for i in range(self.alternations):
            for j in range(self.repeats):
                self.set_write_pulsetrain(i % 2)
                self.measure_hall_voltage()
                progress = (i * self.repeats + j + 1) / \
                          self.total_number_of_pulsetrains * 100
                print(progress)
                self.emit('progress', progress)

    def measure_hall_voltage(self):
        self.RelBox.pattern = self.bit_seq_M

        self.LIA_ramp_to_voltage(self.LIA_voltage)

        sleep(self.delay)

        self.measure()

        self.LIA_ramp_to_voltage()
        sleep(self.delay)

        self.RelBox.pattern = 0

    def measure(self):
        data = {
            "Timestamp (s)": time(),
            "Pulse number": self.pulse_number,
            "Pulse direction": self.last_pulse_dir,
            "Lock-In 1 X (V)": self.LIA.x,
            "Lock-In 1 Y (V)": self.LIA.y,
            "Lock-In 1 V (V)": self.LIA.sine_voltage,
            "Lock-In 1 f (Hz)": self.LIA.frequency,
        }
        self.emit("results", data)

    def set_write_pulsetrain(self, direction, ):
        if direction == 0:
            bit_seq = self.bit_seq_W1
        elif direction == 1:
            bit_seq = self.bit_seq_W2

        self.RelBox.pattern = bit_seq

        sleep(self.delay)

        self.AWG.trigger()

        sleep(self.train_length)
        sleep(self.delay)
        self.AWG.wait_for_trigger()

        self.RelBox.pattern = 0

        self.last_pulse_dir = direction
        self.pulse_number += 1

    def LIA_ramp_to_voltage(self, target_voltage=0.004):
        current_voltage = self.LIA.sine_voltage
        n = round(abs(current_voltage - target_voltage) /
                  self.LIA_ramprate) * 10 + 1

        for V in np.linspace(current_voltage, target_voltage, n):
            self.LIA.sine_voltage = V
            sleep(0.1)

    # Define stop sequence
    def shutdown(self):
        self.RelBox.pattern = 0
        self.LIA_ramp_to_voltage()


class MainWindow(ManagedWindow):
    def __init__(self):
        super(MainWindow, self).__init__(
            procedure_class=MeasurementProcedure,
            inputs=(
                "repeats",
                "delay",
                "alternations",
                "LIA_voltage",
                "AWG_voltage",
                "AWG_pulsewidth",
                "AWG_pulsespace",
                "AWG_number",
            ),
            x_axis="Pulse number",
            y_axis="Lock-In 1 X (V)",
        )

    def queue(self):
        filename = unique_filename(r"E:\Data\Temp")

        procedure = MeasurementProcedure()

        results = Results(procedure, filename)

        experiment = self.new_experiment(results)
        self.manager.queue(experiment)


if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
