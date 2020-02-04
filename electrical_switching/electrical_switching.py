import logging
import sys
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import numpy as np

from pymeasure.display.Qt import QtGui
from pymeasure.display.windows import ManagedWindow
from pymeasure.experiment import Procedure, Results, unique_filename
from pymeasure.experiment import Parameter, FloatParameter, BooleanParameter, IntegerParameter

from pymeasure.instruments.keithley import Keithley2400
from pymeasure.instruments.keithley import Keithley2700
from pymeasure.instruments.srs import SR830

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

    DATA_COLUMNS = [
        "Timestamp (s)",
        "Pulse number",
        "Pulse direction",
    ]

    # Define start-up sequence
    def startup(self):



        pass

    # Define measurement procedure
    def execute(self):
        pass

    # Define stop sequence
    def shutdown(self):
        pass


class MainWindow(ManagedWindow):
    def __init__(self):
        super(MainWindow, self).__init__(
            procedure_class=MeasurementProcedure,
            inputs=(

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


# self.emit("results", data) data = dict()
# self.emit("progress", progress) progress = 0 - 100