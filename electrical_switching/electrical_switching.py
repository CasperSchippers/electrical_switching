import logging
import sys
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

from pymeasure.display.Qt import QtGui
from pymeasure.display.windows import ManagedWindow
from pymeasure.experiment import Procedure, Results, unique_filename
from pymeasure.experiment import Parameter, FloatParameter, BooleanParameter


class MeasurementProcedure(Procedure):
    # Define parameters

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
            procedure_class=MeasurementProcedure)


if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
