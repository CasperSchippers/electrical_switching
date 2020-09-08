import numpy as np


class FieldFileReader:
    _factor_table = {
        1: np.array([0.82356, 1.10875e-6, +4.12751e-11]),
        2: np.array([0.93704, 1.65654E-6, -5.64052E-10]),
        3: np.array([0.89828, 2.66293e-6, -2.03706e-10]),
        4: np.array([0.60054, 2.39780E-7, -2.62400E-10]),
        5: np.array([0.89660, 2.11722E-6, -4.56451E-10]),
    }

    _cell = 1
    _file = "current.txt"

    def __init__(self, cell=1, file=None, **kwargs):
        self.cell = cell

        if file is not None:
            self._file = file

    @property
    def field_factors(self):
        """ Grab the field factors that correspond to the present cell value. """
        return self._factor_table[self.cell]

    @property
    def cell(self):
        """ Read the cell property of the class. """
        return self._cell

    @cell.setter
    def cell(self, cell):
        """ Set the cell property of the class. """
        if cell in [1, 2, 3, 4, 5]:
            self._cell = cell
        else:
            raise ValueError("cell should be in range 1 to 5")

    def get_current_values(self):
        """ Read the first line of the file and convert to floats. """
        with open(self._file) as f:
            line = f.readline().strip()

        values = list(map(float, line.split()))

        return values

    def current_to_field(self, current):
        """ Convert the given current (in kA) to a magnetic field (in T). """

        f = self.field_factors

        B = current * f[0] + current**3 * f[1] + current**5 * f[2]

        return B

    @property
    def field(self):
        """ Property that returns the current magnetic field value. """

        vals = self.get_current_values()

        field = self.current_to_field(vals[0])

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
