import numpy as np
import os.path

import warnings


class FieldFileReader:
    _field_factors = [0.0, 0.90181, 0.0, 1.38851e-06, 0.0, -1.15628e-10]
    _cell_list = [1, 2, 3, 4, 5]
    _cell = 1
    _folder = "S:/"
    _filename = "current.txt"
    _filebase_cell = "cell%d.txt"

    def __init__(self, cell=1, folder=None, filename=None, **kwargs):
        if folder is not None:
            self._folder = folder

        if filename is not None:
            self._filename = filename

        self._file = os.path.join(self._folder, self._filename)

        self.cell = cell

    def read_cell_factors(self):
        file = os.path.join(self._folder, self._filebase_cell % self.cell)

        values = self.get_current_values(file)
        self._field_factors = np.array(values)

        if len(self._field_factors) < 6:
            self.read_cell_factors()

    @property
    def cell(self):
        """ Read the cell property of the class. """
        return self._cell

    @cell.setter
    def cell(self, cell):
        """ Set the cell property of the class and read the field-factors. """
        if cell in self._cell_list:
            self._cell = cell
        else:
            raise ValueError("cell should be in range 1 to 5")

        self.read_cell_factors()

    def get_current_values(self, file=None):
        """ Read the first line of the file and convert to floats. """

        if file is None:
            file = self._file

        with open(file) as f:
            line = f.readline().strip()

        values = list(map(float, line.split()))

        if len(values) == 0:
            values = self.get_current_values(file)

        return values

    def current_to_field(self, current):
        """ Convert the given current (in kA) to a magnetic field (in T). """

        f = self._field_factors

        # Novel implementation, assumes that the factors are exponential
        # factors sorted in increasing order from 0 to 5
        b = np.polyval(f[::-1], current)

        # As upon testing only the terms 1, 3, and 5 were non-zero, a warning is
        # issued when other terms are non-zero
        if any([self._field_factors[0] != 0.,
                self._field_factors[2] != 0.,
                self._field_factors[4] != 0.]):
            warnings.warn("Field-factor terms 0, 2, or 4 is non-zero. Check if"
                          "Check if the behaviour is as expected! If the "
                          "behaviour is as intended, this warning can be "
                          "removed.", category=RuntimeWarning)

        # archaic implementation
        # b = current * f[1] + current**3 * f[3] + current**5 * f[5]

        return b

    @property
    def field(self):
        """ Property that returns the current magnetic field value. """

        values = self.get_current_values()

        field = self.current_to_field(values[0])

        return field

    @property
    def coil_resistance_deviations(self):
        """ Property that returns the current coil-resistance deviations. """

        vals = self.get_current_values()

        return vals[1:4]

    @property
    def field_and_coil(self):
        """ Property that returns both the current magnetic field and
        coil-resistance deviations. """

        vals = self.get_current_values()

        field = self.current_to_field(vals[0])

        return field, vals[1:4]

    @property
    def magnet_current(self):
        """ Property that returns the current magnet-current. """
        vals = self.get_current_values()

        return vals[0]
