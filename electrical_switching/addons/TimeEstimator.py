import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

from pymeasure.display.Qt import QtCore, QtGui


class TimeEstimator(QtGui.QWidget):
    def __init__(self, parent, auto_update=True):
        super().__init__(parent)
        self._parent = parent

        self.update_timer = QtCore.QTimer(self)
        self.update_timer.timeout.connect(self.update_estimates)

        self._get_fields()

        self._setup_ui()
        self._layout()
        self._add_to_interface()

        self.update_estimates()

        if auto_update:
            self.update_box.setCheckState(1)

    def _get_fields(self):
        proc = self._parent.make_procedure()
        self.number_of_lines = len(proc.get_time_estimates())

    def _setup_ui(self):

        self.line_edits = list()
        for idx in range(self.number_of_lines):
            qlb = QtGui.QLabel(self)

            qle = QtGui.QLineEdit(self)
            qle.setEnabled(False)
            qle.setAlignment(QtCore.Qt.AlignRight)

            self.line_edits.append((qlb, qle))


        # Add a checkbox for continuous updating
        self.update_box = QtGui.QCheckBox(self)
        self.update_box.setTristate(True)
        self.update_box.stateChanged.connect(self._set_continuous_updating)

        # Add a button for continuous updating
        self.update_button = QtGui.QPushButton("Update", self)
        self.update_button.clicked.connect(self.update_estimates)

    def _layout(self):
        f_layout = QtGui.QFormLayout(self)
        for row in self.line_edits:
            f_layout.addRow(*row)

        update_hbox = QtGui.QHBoxLayout()
        update_hbox.addWidget(self.update_box)
        update_hbox.addWidget(self.update_button)
        f_layout.addRow("Update continuously", update_hbox)

    def update_estimates(self):
        proc = self._parent.make_procedure()
        estimates = proc.get_time_estimates()

        for idx, estimate in enumerate(estimates):
            self.line_edits[idx][0].setText(estimate[0])
            self.line_edits[idx][1].setText(estimate[1])

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

