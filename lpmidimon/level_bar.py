#
# Copyright 2021 - Looperlative Audio Products, LLC
#
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt

class LevelBar(QtWidgets.QWidget):

    def __init__(self, *args, **kwargs):
        super(LevelBar, self).__init__(*args, **kwargs)

        self.setSizePolicy(
            QtWidgets.QSizePolicy.MinimumExpanding,
            QtWidgets.QSizePolicy.MinimumExpanding
        )
        self.steps = 20
        self.level = 0
        self.level_valid = False

    def setLevel(self, new_level):
        self.level = new_level
        self.level_valid = True
        self.update()

    def paintEvent(self, e):
        if self.level_valid:
            painter = QtGui.QPainter(self)
            h = painter.device().height()
            w = painter.device().width()

            brush = QtGui.QBrush()
            brush.setColor(QtGui.QColor('black'))
            brush.setStyle(Qt.SolidPattern)
            rect = QtCore.QRect(0, 0, w, h)
            painter.fillRect(rect, brush)

            stepsize = 100.0 / self.steps
            steplevel = int((self.level + (stepsize / 2.0)) / stepsize)

            # x and y with origin at lower left.  Paint canvas has different origin
            # but we will adjust later.
            x = 5
            y = 5
            hh = h - 2 * y
            ww = w - 2 * x
            hstep = float(hh) / self.steps
            hbar = float(hstep) * 0.8
            y += hbar

            # print("h {}, hh {}, hstep {}, hbar {}".format(h, hh, hstep, hbar))

            brush.setColor(QtGui.QColor('red'))
            for i in range(steplevel):
                xd = (self.steps - i)/2
                r = QtCore.QRect(x, h - y, ww - xd * 2, hbar)
                y += hstep
                painter.fillRect(r, brush)

            painter.end()

    def sizeHint(self):
        return QtCore.QSize(40,100)
