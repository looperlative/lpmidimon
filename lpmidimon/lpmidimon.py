#!/usr/bin/env python3
#
# Copyright 2021 - Looperlative Audio Products, LLC
#
# On Windows: install Visual C++ from Microsoft
# On All Systems: pip install mido python-rtmidi PyQt5

import mido
import mido.backends.rtmidi
import sys
import time
import threading
import json
import psutil
import socket
import re
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
from lpfunctions import LPFunctions

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
        self.lpFunctions = LPFunctions()
        self.setupUi(self)

        self.searchReturnLock = threading.Lock()
        self.searchReturn = []
        self.upgradeFileLock = threading.Lock()
        self.upgradeFile = ""

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
        self.effect1boxes = []
        self.effect2boxes = []

        self.currentStatus = LPStatus()
        self.endStatusTask = False
        self.lp2_cmd = 0
        self.parsingEffectConfig = False
        self.requestEffectButtons = True
        self.sendEffectConfig = False
        self.statusTh = None

        self.midiclockcount = -1
        self.midiclockstarttime = -1.0

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

            self.effect1boxes.append(QtWidgets.QComboBox(self.gridLayoutWidget_2))
            self.gridLayout_2.addWidget(self.effect1boxes[i-1], i, 1, 1, 1)
            self.effect1boxes[i-1].currentIndexChanged.connect(self.effectChanged)

            self.effect2boxes.append(QtWidgets.QComboBox(self.gridLayoutWidget_2))
            self.gridLayout_2.addWidget(self.effect2boxes[i-1], i, 2, 1, 1)
            self.effect2boxes[i-1].currentIndexChanged.connect(self.effectChanged)

        bpm = QtWidgets.QLabel(self.gridLayoutWidget)
        self.gridLayout.addWidget(bpm, 7, 0, 1, 1)
        bpm.setText("BPM")

        self.midiclock = QtWidgets.QLabel(self.gridLayoutWidget)
        self.gridLayout.addWidget(self.midiclock, 7, 1, 1, 1)
        self.midiclock.setText("???")

        self.plainTextEdit.setReadOnly(True)

        self.actionEdit_Effect_Buttons.triggered.connect(self.handleEffectButtons)
        self.action_Upgrade.triggered.connect(self.handleUpgrade)
        self.action_Status.triggered.connect(self.handleStatus)
        self.action_MIDI_Status.triggered.connect(self.handleMIDIStatus)
        self.actionRe_boot.triggered.connect(self.handleReboot)
        self.actionSD_Directory.triggered.connect(self.handleDirectory)

        self.timer = QTimer()
        self.timer.timeout.connect(self.handleTimer)
        self.timer.start(250)

    def restartStatusThread(self):
        if self.statusTh != None:
            self.endStatusTask = True
            self.statusTh.join()
            self.endStatusTask = False

        self.statusTh = threading.Thread(target=self.statusThread)
        self.statusTh.start()

    def stopStatusThread(self):
        if self.statusTh != None:
            self.endStatusTask = True
            self.statusTh.join()
            self.endStatusTask = False
            self.statusTh = None

    def processINDevice(self, chk):
        if not chk:
            return

        self.midiInDevice = self.sender().data()
        for a in self.action_in_devices:
            a.setChecked(a == self.sender())

        ip = re.search('^(\d+\.\d+\.\d+\.\d+) ', self.midiInDevice)
        if len(self.midiOutDevice) == 0 or (ip and self.midiOutDevice != self.midiInDevice):
            self.midiOutDevice = self.midiInDevice
            for a in self.action_out_devices:
                a.setChecked(a.data() == self.midiOutDevice)

        self.restartStatusThread()
        self.saveConfig()

    def processOUTDevice(self, chk):
        if not chk:
            return

        self.midiOutDevice = self.sender().data()
        for a in self.action_out_devices:
            a.setChecked(a == self.sender())

        ip = re.search('^(\d+\.\d+\.\d+\.\d+) ', self.midiOutDevice)
        if len(self.midiInDevice) == 0 or (ip and self.midiOutDevice != self.midiInDevice):
            self.midiInDevice = self.midiOutDevice
            for a in self.action_in_devices:
                a.setChecked(a.data() == self.midiInDevice)

        self.restartStatusThread()
        self.saveConfig()


    def searchForDeviceThread(self, baddr):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        b = bytes("<query>id</query>\0", "utf-8")
        sock.sendto(b, (baddr, 5667))

        while True:
            try:
                sock.settimeout(2)
                (brcv, address) = sock.recvfrom(1024)
                m = re.search('<id>(.*)</id>', brcv.decode("utf-8"))
                mitem = "{} {}".format(address[0], m.group(1))
                self.searchReturnLock.acquire()
                self.searchReturn.append(mitem)
                self.searchReturnLock.release()
            except socket.timeout:
                sock.close()
                return

    def searchForDevice(self, baddr):
        th = threading.Thread(target=self.searchForDeviceThread, args=(baddr, ))
        th.daemon = True
        th.start()

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

        # Look for IP Looperlative devices
        for name, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == socket.AF_INET:
                    if addr.broadcast:
                        self.searchForDevice(addr.broadcast)

    def processMIDI(self, msg):
        b = msg.bytes()
        if msg.type == 'sysex' and b[1:5] == [0, 2, 0x33, 2]:
            s = LPStatus()
            s.parseMIDIStatus(b)
            self.currentStatus.setStatus(s)
        elif msg.type == 'sysex' and b[1:5] == [0, 2, 0x33, 3] and b[5] != 0xf7:
            self.currentStatus.appendLog(''.join(map(chr, b[5:-1])))
        elif msg.type == 'sysex' and b[1:5] == [0, 2, 0x33, 9]:
            self.parseEffectConfig(b[5:])
        elif msg.type == 'clock':
            self.midiclockcount += 1

            if self.midiclockcount == 0:
                self.midiclockcount = 0
                self.midiclockstarttime = time.time()
            elif self.midiclockcount == 24:
                now = time.time()
                diff = now - self.midiclockstarttime
                self.midiclockstarttime = now
                self.midiclockcount = 0
                try:
                    self.midiclock.setText("{bpm:.2f}".format(bpm = (60.0 / diff)))
                except:
                    pass

    def doIPUpgrade(self, fileName, lpip):
        print("Upgrade {} with {}".format(lpip, fileName))
        with open(fileName, mode="rb") as upgradeFile:
            upgradeData = upgradeFile.read()
            upgradereq = bytes("<command>upgrade {}</command>".format(len(upgradeData)), "utf-8")
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.sendto(upgradereq, lpip)
                sock.settimeout(2)
                try:
                    (brcv, address) = sock.recvfrom(2048)
                except:
                    print("Upgrade response timeout")
                    return

                reqtype = int.from_bytes(brcv[0:2], "big")
                m = re.search('(.*)\0(.*)\0', brcv[2:].decode("utf-8"))
                if not m:
                    print("Bad response to upgrade")
                    return

                blockNum = 1
                filePos = 0
                nTrys = 0

                tftpip = (lpip[0], 4069)

                while filePos < len(upgradeData):
                    nTrys += 1
                    block = bytes([0, 3, int(blockNum / 256), int(blockNum % 256)])
                    block += upgradeData[filePos: filePos + 512]
                    sock.sendto(block, tftpip)
                    sock.settimeout(1)
                    try:
                        (brcv, address) = sock.recvfrom(2048)
                    except:
                        if nTrys > 10:
                            print("Upgrade too many tries")
                            return
                        continue
                    ack = int(brcv[1])
                    ackBlock = int.from_bytes(brcv[2:4], "big")
                    if ackBlock == blockNum:
                        blockNum += 1
                        blockNum &= 0xffff
                        nTrys = 0
                        filePos += 512
                    elif nTrys > 10:
                        print("Too many attempts")
                        return

    def pollIPStatus(self, ipaddr):
        time.sleep(0.05)

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        lpip = (ipaddr, 5667)

        statusreq = bytes("<query>status compact</query>\0", "utf-8")
        logreq = bytes("<query>log</query>\0", "utf-8")

        while not self.endStatusTask:
            sock.sendto(statusreq, lpip)

            try:
                sock.settimeout(2)
                (brcv, address) = sock.recvfrom(1024)
                if len(brcv) == 232:
                    s = LPStatus()
                    s.parseIPStatus(brcv)
                    self.currentStatus.setStatus(s)

            except socket.timeout:
                time.sleep(1)
                continue

            time.sleep(0.1)

            sock.sendto(logreq, lpip)

            try:
                sock.settimeout(2)
                (brcv, address) = sock.recvfrom(2048)
                m = re.search('<log>(.*)</log>', brcv.decode("utf-8"), re.DOTALL)
                if m:
                    self.currentStatus.appendLog(m.group(1))

            except socket.timeout:
                time.sleep(1)
                continue

            time.sleep(0.1)

            if self.lp2_cmd != 0:
                cmdreq = bytes("<userinput>{}</userinput>\0".format(chr(self.lp2_cmd)), "utf-8")
                print(cmdreq)
                sock.sendto(cmdreq, lpip)
                self.lp2_cmd = 0

            time.sleep(0.1)

            self.upgradeFileLock.acquire()
            fileName = self.upgradeFile
            self.upgradeFile = ""
            self.upgradeFileLock.release()

            if len(fileName) > 0:
                self.doIPUpgrade(fileName, lpip)

        sock.close()

    def statusThread(self):
        ip = re.search('^(\d+\.\d+\.\d+\.\d+) ', self.midiOutDevice)
        if ip:
            self.pollIPStatus(ip.group(1))
            return

        ip = re.search('^(\d+\.\d+\.\d+\.\d+) ', self.midiInDevice)
        if ip:
            self.pollIPStatus(ip.group(1))
            return

        try:
            outport = mido.open_output(self.midiOutDevice)
        except:
            print("Couldn't open {}".format(self.midiOutDevice))
            return

        try:
            inport = mido.open_input(self.midiInDevice, callback=self.processMIDI)
        except:
            print("Couldn't open {}".format(self.midiInDevice))
            outport.close()
            return

        try:
            statusRequest = mido.Message('sysex', data=[0,2,0x33,2])
            logRequest = mido.Message('sysex', data=[0,2,0x33,3])

            while not self.endStatusTask:
                if self.lp2_cmd != 0:
                    cmdRequest = mido.Message('sysex', data=[0,2,0x33,4,self.lp2_cmd])
                    outport.send(cmdRequest)
                    self.lp2_cmd = 0
                if self.requestEffectButtons:
                    self.requestEffectButtons = False
                    btnReq = mido.Message('sysex', data=[0,2,0x33,9])
                    outport.send(btnReq)
                if self.sendEffectConfig:
                    self.sendEffectConfig = False
                    b = [0, 2, 0x33, 10, 8]
                    for i in self.effects1:
                        b.append((i >> 7) & 0x7f)
                        b.append(i & 0x7f)
                    for i in self.effects2:
                        b.append((i >> 7) & 0x7f)
                        b.append(i & 0x7f)
                    saveEffectsReq = mido.Message('sysex', data=b)
                    outport.send(saveEffectsReq)
                    time.sleep(0.3)
                    # print(saveEffectsReq)

                outport.send(logRequest)
                time.sleep(0.2)
                outport.send(statusRequest)
                time.sleep(0.2)
        except Exception as err:
            print(type(err))
            print(err.args)
            print(err)
        finally:
            outport.close()
            inport.close()

    def handleStatus(self):
        self.lp2_cmd = ord('s')

    def handleMIDIStatus(self):
        self.lp2_cmd = ord('m')

    def handleReboot(self):
        self.lp2_cmd = ord('b')

    def handleDirectory(self):
        self.lp2_cmd = ord('d')

    def handleUpgrade(self):
        if re.search('^(\d+\.\d+\.\d+\.\d+) ', self.midiOutDevice):
            fileName, _ = QFileDialog.getOpenFileName(self, "Open upgrade file", "",
                                                      "Firmware files (*.bin)")
            if len(fileName) > 0:
                self.upgradeFileLock.acquire()
                self.upgradeFile = fileName
                self.upgradeFileLock.release()
        else:
            fileName, _ = QFileDialog.getOpenFileName(self, "Open upgrade file", "",
                                                      "MIDI Sysex files (*.syx)")
            if len(fileName) > 0:
                th = threading.Thread(target=lp2_upgrade,
                                      args=[self.midiOutDevice, self.currentStatus, fileName])
                th.start()

    def handleEffectButtons(self):
        self.requestEffectButtons = True
        pass

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

        if self.midiclockcount >= 0:
            now = time.time()
            diff = now - self.midiclockstarttime
            if diff > 4.0:
                self.midiclockcount = -1;
                self.midiclock.setText("no clock")

        self.searchReturnLock.acquire()
        searchlist = self.searchReturn.copy()
        self.searchReturn = []
        self.searchReturnLock.release()

        for n in searchlist:
            self.action_in_devices.append(QtWidgets.QAction(self))
            d = self.action_in_devices[-1]
            d.setCheckable(True)
            d.setChecked(n == self.midiInDevice)
            d.setText(n)
            d.setData(n)
            d.triggered.connect(self.processINDevice)
            self.menuMIDI_IN_device.addAction(self.action_in_devices[-1])

            self.action_out_devices.append(QtWidgets.QAction(self))
            d = self.action_out_devices[-1]
            d.setCheckable(True)
            d.setChecked(n == self.midiOutDevice)
            d.setText(n)
            d.setData(n)
            d.triggered.connect(self.processOUTDevice)
            self.menuMIDI_OUT_device.addAction(self.action_out_devices[-1])


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

    def parseEffectConfig(self, b):
        self.parsingEffectConfig = True
        neffects = b[0]
        self.effects1 = []
        self.effects2 = []
        for i in range(0, neffects):
            effectid = b[1+i*2] * 128 + b[2+i*2]
            self.effects1.append(effectid)
            effectid = b[neffects*2+1+i*2] * 128 + b[neffects*2+2+i*2]
            self.effects2.append(effectid)

        for i in range(0, 8):
            self.effect1boxes[i].clear()
            index = 0
            for id in self.lpFunctions.keys():
                v = self.lpFunctions.get(id)
                self.effect1boxes[i].addItem(v)
                if id == self.effects1[i]:
                    self.effect1boxes[i].setCurrentIndex(index)
                index += 1

            self.effect2boxes[i].clear()
            index = 0
            for id in self.lpFunctions.keys():
                v = self.lpFunctions.get(id)
                self.effect2boxes[i].addItem(v)
                if id == self.effects2[i]:
                    self.effect2boxes[i].setCurrentIndex(index)
                index += 1
        self.parsingEffectConfig = False

    def effectChanged(self, idx):
        if not self.parsingEffectConfig:
            ids = self.lpFunctions.keys()
            for i in range(0, 8):
                self.effects1[i] = ids[self.effect1boxes[i].currentIndex()]
                self.effects2[i] = ids[self.effect2boxes[i].currentIndex()]
            self.sendEffectConfig = True

def main():
    app = QApplication(sys.argv)
    form = LP2CtrlApp()
    form.show()
    app.exec_()

if __name__ == "__main__":
    main()
