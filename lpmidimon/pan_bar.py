#
# Copyright 2021 - Looperlative Audio Products, LLC
#
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt

class PanBar(QtWidgets.QWidget):

    def __init__(self, *args, **kwargs):
        super(PanBar, self).__init__(*args, **kwargs)

        self.setSizePolicy(
            QtWidgets.QSizePolicy.MinimumExpanding,
            QtWidgets.QSizePolicy.MinimumExpanding
        )
        self.steps = 20
        self.pan = 0
        self.pan_valid = False

    def setPan(self, new_pan):
        self.pan = new_pan
        self.pan_valid = True
        self.update()

    def paintEvent(self, e):
        if self.pan_valid:
            painter = QtGui.QPainter(self)
            h = painter.device().height()
            w = painter.device().width()

            brush = QtGui.QBrush()
            brush.setColor(QtGui.QColor('black'))
            brush.setStyle(Qt.SolidPattern)
            rect = QtCore.QRect(0, 0, w, h)
            painter.fillRect(rect, brush)

            stepsize = 100.0 / self.steps
            steppan = int((self.pan + (stepsize / 2.0)) / stepsize)
            if steppan < -10:
                steppan = -10
            elif steppan > 10:
                steppan = 10

            # x and y with origin at upper left.
            x = 5
            y = 5
            hh = h - 2 * y
            ww = w - 2 * x

            x += ww / 2
            x += steppan * (hh / 20.0)

            brush.setColor(QtGui.QColor('red'))
            r = QtCore.QRect(x - 2, y, 4, hh)
            painter.fillRect(r, brush)

            painter.end()

    def sizeHint(self):
        return QtCore.QSize(100,40)
