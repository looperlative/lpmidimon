#!/usr/bin/env python3
#
# Copyright 2021 - Looperlative Audio Products, LLC
#
# pip install: mido, rtmidi, python-rtmidi

import mido
import sys
import time
import threading
import json
from pathlib import Path
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QApplication, QFileDialog
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QTextCursor
from PyQt5.QtCore import Qt
from copy import copy
import lp2ctrlui
from lpstatus import LPStatus
from level_bar import LevelBar
from pan_bar import PanBar

def lp2_upgrade(portname, currentStatus, fileName):
    with mido.open_output(portname) as outport:
        try:
            messages = mido.read_syx_file(fileName)
        except:
            currentStatus.appendLog("Error reading MIDI Sysex file\n")
            return

        total_lines = float(len(messages))
        target_percent = 5.0

        count = 0.0
        for i in messages:
            outport.send(i)
            time.sleep(0.07)
            count += 1.0
            percent = (count / total_lines) * 100.0
            if percent >= target_percent:
                currentStatus.appendLog(str(int(percent)) + '% complete\n')
                target_percent += 5.0

    currentStatus.appendLog("Completed\n")

class LP2CtrlApp(QtWidgets.QMainWindow, lp2ctrlui.Ui_MainWindow):
    def __init__(self, parent=None):
        super(LP2CtrlApp, self).__init__(parent)
        self.setupUi(self)

        self.midiInDevice = ""
        self.midiOutDevice = ""
        self.loadConfig()
        self.initMIDIDeviceMenus()

        self.psliders = []
        self.vsliders = []
        self.lengths = []
        self.positions = []
        self.statuses = []
        self.fsliders = []
        self.tracktitles = []

        self.currentStatus = LPStatus()
        self.endStatusTask = False
        self.lp2_cmd = 0
        self.statusTh = None

        self.restartStatusThread()

        for i in range(1,9):
            self.tracktitles.append(QtWidgets.QLabel(self.gridLayoutWidget))
            self.tracktitles[i-1].setText("Track " + str(i))
            self.tracktitles[i-1].setHidden(True)
            self.gridLayout.addWidget(self.tracktitles[i-1], 0, i, 1, 1)

            self.lengths.append(QtWidgets.QLabel(self.gridLayoutWidget))
            self.gridLayout.addWidget(self.lengths[i-1], 1, i, 1, 1)

            self.positions.append(QtWidgets.QLabel(self.gridLayoutWidget))
            self.gridLayout.addWidget(self.positions[i-1], 2, i, 1, 1)

            self.statuses.append(QtWidgets.QLabel(self.gridLayoutWidget))
            self.gridLayout.addWidget(self.statuses[i-1], 3, i, 1, 1)

            self.psliders.append(PanBar(self.gridLayoutWidget))
            self.psliders[i-1].setObjectName("pan_" + str(i))
            self.gridLayout.addWidget(self.psliders[i-1], 4, i, Qt.AlignCenter)

            self.vsliders.append(LevelBar(self.gridLayoutWidget))
            self.vsliders[i-1].setObjectName("volume_" + str(i))
            self.gridLayout.addWidget(self.vsliders[i-1], 5, i, Qt.AlignCenter)

            self.fsliders.append(LevelBar(self.gridLayoutWidget))
            self.fsliders[i-1].setObjectName("feedback_" + str(i))
            self.gridLayout.addWidget(self.fsliders[i-1], 6, i, Qt.AlignCenter)

        self.plainTextEdit.setReadOnly(True)

        self.action_Upgrade.triggered.connect(self.handleUpgrade)
        self.action_Status.triggered.connect(self.handleStatus)
        self.action_MIDI_Status.triggered.connect(self.handleMIDIStatus)
        self.actionRe_boot.triggered.connect(self.handleReboot)

        self.timer = QTimer()
        self.timer.timeout.connect(self.handleTimer)
        self.timer.start(250)

    def restartStatusThread(self):
        if self.statusTh != None:
            self.endStatusTask = True;
            self.statusTh.join()
            self.endStatusTask = False;

        self.statusTh = threading.Thread(target=self.statusThread)
        self.statusTh.start()

    def processINDevice(self, chk):
        self.midiInDevice = self.sender().data()
        for a in self.action_in_devices:
            a.setChecked(a == self.sender())
        if len(self.midiOutDevice) == 0:
            self.midiOutDevice = self.midiInDevice
            for a in self.action_out_devices:
                a.setChecked(a.data() == self.midiOutDevice)

        self.restartStatusThread()
        self.saveConfig()

    def processOUTDevice(self, chk):
        self.midiOutDevice = self.sender().data()
        for a in self.action_out_devices:
            a.setChecked(a == self.sender())
        if len(self.midiInDevice) == 0:
            self.midiInDevice = self.midiOutDevice
            for a in self.action_in_devices:
                a.setChecked(a.data() == self.midiInDevice)

        self.restartStatusThread()
        self.saveConfig()

    def initMIDIDeviceMenus(self):
        self.innames = mido.get_input_names()
        self.outnames = mido.get_output_names()

        self.action_in_devices = []
        self.action_out_devices = []

        for n in self.innames:
            self.action_in_devices.append(QtWidgets.QAction(self))
            d = self.action_in_devices[-1]
            d.setCheckable(True)
            d.setChecked(n == self.midiInDevice)
            d.setText(n)
            d.setData(n)
            d.triggered.connect(self.processINDevice)
            self.menuMIDI_IN_device.addAction(self.action_in_devices[-1])

        for n in self.outnames:
            self.action_out_devices.append(QtWidgets.QAction(self))
            d = self.action_out_devices[-1]
            d.setCheckable(True)
            d.setChecked(n == self.midiOutDevice)
            d.setText(n)
            d.setData(n)
            d.triggered.connect(self.processOUTDevice)
            self.menuMIDI_OUT_device.addAction(self.action_out_devices[-1])

    def processMIDI(self, msg):
        b = msg.bytes()
        if msg.type == 'sysex' and b[1:5] == [0, 2, 0x33, 2]:
            s = LPStatus()
            s.parseMIDIStatus(b)
            self.currentStatus.setStatus(s)
        elif msg.type == 'sysex' and b[1:5] == [0, 2, 0x33, 3] and b[5] != 0xf7:
            self.currentStatus.appendLog(''.join(map(chr, b[5:-1])))

    def statusThread(self):
        try:
            outport = mido.open_output(self.midiOutDevice)
            inport = mido.open_input(self.midiInDevice, callback=self.processMIDI)
            statusRequest = mido.Message('sysex', data=[0,2,0x33,2])
            logRequest = mido.Message('sysex', data=[0,2,0x33,3])

            while not self.endStatusTask:
                if self.lp2_cmd != 0:
                    cmdRequest = mido.Message('sysex', data=[0,2,0x33,4,self.lp2_cmd])
                    outport.send(cmdRequest)
                    self.lp2_cmd = 0

                outport.send(logRequest)
                time.sleep(0.2)
                outport.send(statusRequest)
                time.sleep(0.2)

            outport.close()
            inport.close()
        except:
            pass

    def handleStatus(self):
        self.lp2_cmd = ord('s')

    def handleMIDIStatus(self):
        self.lp2_cmd = ord('m')

    def handleReboot(self):
        self.lp2_cmd = ord('b')

    def handleUpgrade(self):
        fileName, _ = QFileDialog.getOpenFileName(self, "Open upgrade file", "",
                                               "MIDI Sysex files (*.syx)")
        print(fileName)
        if len(fileName) > 0:
            th = threading.Thread(target=lp2_upgrade,
                                  args=[self.midiOutDevice, self.currentStatus, fileName])
            th.start()

    def handleTimer(self):
        s = self.currentStatus.getSnapshot()

        for i in range(0,s.tracks):
            self.tracktitles[i].setHidden(False)
        for i,j in zip(self.lengths, s.lengths):
            i.setText(str(format(j, '.2f')))
        for i,j in zip(self.positions, s.positions):
            i.setText(str(format(j, '.2f')))
        for i,j in zip(self.statuses, s.statuses):
            i.setText(LPStatus.getStatusString(j))
        for i,j in zip(self.psliders, s.pans):
            i.setPan(j)
        for i,j in zip(self.vsliders, s.levels):
            i.setLevel(100 + j)
        for i,j in zip(self.fsliders, s.feedbacks):
            i.setLevel(j)

        ltext = self.currentStatus.getLog()
        if len(ltext) > 0:
            logW = self.plainTextEdit
            logW.moveCursor(QTextCursor.End)
            logW.insertPlainText(ltext)
            logW.moveCursor(QTextCursor.End)

    def closeEvent(self, event):
        self.endStatusTask = True
        if self.statusTh != None:
            self.statusTh.join()
        event.accept()

    def saveConfig(self):
        config = {'midiInDevice' : self.midiInDevice,
                  'midiOutDevice' : self.midiOutDevice}

        cfile_name = str(Path.home()) + '/.lp2ctrl.json'
        with open(cfile_name, 'w') as fp:
            json.dump(config, fp)

    def loadConfig(self):
        cfile_name = str(Path.home()) + '/.lp2ctrl.json'
        try:
            with open(cfile_name) as fp:
                config = json.load(fp)
                if config['midiInDevice']:
                    self.midiInDevice = config['midiInDevice']
                if config['midiOutDevice']:
                    self.midiOutDevice = config['midiOutDevice']
        except FileNotFoundError:
            pass

def main():
    app = QApplication(sys.argv)
    form = LP2CtrlApp()
    form.show()
    app.exec_()

if __name__ == "__main__":
    main()
