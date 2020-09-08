import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

from pymeasure.display.Qt import QtCore, QtGui


class TimeEstimator(QtGui.QWidget):
    def __init__(self, parent, inputs=None):
        super().__init__(parent)
        self._parent = parent

        self.update_timer = QtCore.QTimer(self)
        self.update_timer.timeout.connect(self.update_estimates)

        self._get_fields()

        self._layout()
        self._add_to_interface()

        self.update_estimates()

    def _get_fields(self):
        proc = self._parent.make_procedure()
        self.keys = proc.get_time_estimates().keys()

    def _layout(self):
        f_layout = QtGui.QFormLayout(self)

        self.line_edits = dict()

        for key in self.keys:
            qle = QtGui.QLineEdit(self)
            qle.setEnabled(False)
            qle.setAlignment(QtCore.Qt.AlignRight)

            self.line_edits[key] = qle

            f_layout.addRow(key, qle)

        # Add a checkbox for continuous updating
        self.update_box = QtGui.QCheckBox()
        f_layout.addRow("Update continuously", self.update_box)
        self.update_box.setTristate(True)
        self.update_box.stateChanged.connect(self._set_continuous_updating)

    def update_estimates(self):
        proc = self._parent.make_procedure()
        estimates = proc.get_time_estimates()

        for key, estimate in estimates.items():
            self.line_edits[key].setText(estimate)

    def _add_to_interface(self):
        dock = QtGui.QDockWidget('Time estimator')
        dock.setWidget(self)
        dock.setFeatures(QtGui.QDockWidget.NoDockWidgetFeatures)
        self._parent.addDockWidget(QtCore.Qt.LeftDockWidgetArea, dock)

    def _set_continuous_updating(self):
        state = self.update_box.checkState()

        if state == 0:
            self.update_timer.stop()
        elif state == 1:
            self.update_timer.setInterval(2000)
            self.update_timer.start()
        elif state == 2:
            self.update_timer.setInterval(100)
            self.update_timer.start()

