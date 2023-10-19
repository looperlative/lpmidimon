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
import queue
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

class LP2CtrlApp(QtWidgets.QMainWindow, lp2ctrlui.Ui_MainWindow):
    def __init__(self, parent=None):
        super(LP2CtrlApp, self).__init__(parent)
        self.lpFunctions = LPFunctions()
        self.setupUi(self)

        self.searchReturnLock = threading.Lock()
        self.searchReturn = []
        self.upgradeFileLock = threading.Lock()
        self.upgradeFile = ""

        self.upgradeFlag = False

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
        self.stepboxes = []
        self.effects1 = []
        self.effects2 = []

        self.currentStatus = LPStatus()
        self.lp2_cmd = 0
        self.lp_sysex_q = queue.Queue()
        self.parsingEffectConfig = False
        self.requestEffectButtons = True
        self.sendEffectConfig = False

        self.endStatusTask = False
        self.statusTh = None

        self.endIPReceiver = False
        self.ipReceiverTh = None
        self.recvSock = None

        self.parsingMIDIButtonConfig = 0
        self.requestMIDIButton = 0

        self.midiclockcount = -1
        self.midiclockstarttime = -1.0

        self.restartStatusThread()

        self.midiButtonDict = {}
        self.midibtntypelist = [ "PgmChange", "CC", "Note" ]
        for i in self.midibtntypelist:
            self.midibtntype.addItem(i)
        for i in range(0,128):
            self.midibtnnum.addItem(str(i))
        self.midibtntype.currentIndexChanged.connect(self.midibtntypeChanged)
        self.midibtnnum.currentIndexChanged.connect(self.midibtnnumChanged)

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

            self.stepboxes.append(QtWidgets.QComboBox(self.gridLayoutWidget_2))
            row = 1 + int((i-1) / 4)
            col = 1 + ((i-1) & 3)
            self.gridLayout_3.addWidget(self.stepboxes[i-1], row, col, 1, 1)
            for k in self.lpFunctions.keysLP1():
                self.stepboxes[i-1].addItem(self.lpFunctions.get(k))
            self.stepboxes[i-1].currentIndexChanged.connect(self.stepChanged)

        bpm = QtWidgets.QLabel(self.gridLayoutWidget)
        self.gridLayout.addWidget(bpm, 7, 0, 1, 1)
        bpm.setText("BPM")

        self.midiclock = QtWidgets.QLabel(self.gridLayoutWidget)
        self.gridLayout.addWidget(self.midiclock, 7, 1, 1, 1)
        self.midiclock.setText("???")

        self.plainTextEdit.setReadOnly(True)

        self.actionEdit_Effect_Buttons.triggered.connect(self.handleEffectButtons)
        self.actionSave_LP_configuration.triggered.connect(self.handleSaveLPConf)
        self.actionLoad_LP_configuration.triggered.connect(self.handleLoadLPConf)

        self.action_Upgrade.triggered.connect(self.handleUpgrade)
        self.action_Status.triggered.connect(self.handleStatus)
        self.action_MIDI_Status.triggered.connect(self.handleMIDIStatus)
        self.actionRe_boot.triggered.connect(self.handleReboot)
        self.actionSD_Directory.triggered.connect(self.handleDirectory)

        self.timer = QTimer()
        self.timer.timeout.connect(self.handleTimer)
        self.timer.start(250)

    def stopStatusThread(self):
        if self.statusTh != None:
            self.endStatusTask = True
            self.statusTh.join()
            self.endStatusTask = False
            self.statusTh = None

    def restartStatusThread(self):
        self.stopStatusThread()
        self.statusTh = threading.Thread(target=self.statusThread)
        self.statusTh.start()

    def startIPReceiver(self):
        self.ipReceiverTh = threading.Thread(target=self.ipReceiverThread)
        self.ipReceiverTh.start()

    def stopIPReceiver(self):
        if self.ipReceiverTh != None:
            self.endIPReceiver = True
            self.ipReceiverTh.join()
            self.endIPReceiver = False
            self.ipReceiverTh = None

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
        self.innames = set(mido.get_input_names())
        self.outnames = set(mido.get_output_names())

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

    def processSysex(self, b):
        if b[1:5] == [0, 2, 0x33, 2]:
            s = LPStatus()
            s.parseMIDIStatus(b)
            self.currentStatus.setStatus(s)
        elif b[1:5] == [0, 2, 0x33, 3] and b[5] != 0xf7:
            self.currentStatus.appendLog(''.join(map(chr, b[5:-1])))
        elif b[1:5] == [0, 2, 0x33, 9]:
            self.parseEffectConfig(b[5:])
        elif b[1:5] == [0, 2, 0x33, 15]:
            self.parseButtonConfig(b[5:])
        elif b[1:5] == [0, 2, 0x33, 24]:
            # user pressed a button b[5]=button type, b[6]=button number
            self.midibtntype.setCurrentIndex(int(b[5]))
            self.midibtnnum.setCurrentIndex(int(b[6]))
            pass
        else:
            pass

    def processMIDI(self, msg):
        b = msg.bytes()
        if msg.type == 'sysex':
            self.processSysex(b)
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

    def ipReceiverThread(self):
        sock = self.recvSock
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        print(sock)

        while not self.endIPReceiver:
            try:
                sock.settimeout(1)
                (brcv, address) = sock.recvfrom(2048)
                if brcv[0] == 0 and len(brcv) == 232:
                    s = LPStatus()
                    s.parseIPStatus(brcv)
                    self.currentStatus.setStatus(s)
                elif brcv[0] == 0xf0:
                    self.processSysex(list(brcv))
                else:
                    m = re.search('<log>(.*)</log>', brcv.decode("utf-8"), re.DOTALL)
                    if m:
                        self.currentStatus.appendLog(m.group(1))

            except socket.timeout:
                pass
            except OSError as msg:
                print(msg)

    def pollIPStatus(self, ipaddr):
        time.sleep(0.05)

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        lpip = (ipaddr, 5667)

        statusreq = bytes("<query>status compact</query>\0", "utf-8")
        logreq = bytes("<query>log</query>\0", "utf-8")
        sock.sendto(statusreq, lpip)
        print(sock)
        self.recvSock = sock.dup()
        self.startIPReceiver()

        while not self.endStatusTask:
            sock.sendto(statusreq, lpip)
            time.sleep(0.1)
            sock.sendto(logreq, lpip)
            time.sleep(0.1)

            if self.lp2_cmd != 0:
                cmdreq = bytes("<userinput>{}</userinput>\0".format(chr(self.lp2_cmd)), "utf-8")
                print(cmdreq)
                sock.sendto(cmdreq, lpip)
                self.lp2_cmd = 0
            elif not self.lp_sysex_q.empty():
                msg = bytes([0xf0] + self.lp_sysex_q.get() + [0xf7])
                sock.sendto(msg, lpip)
            elif self.requestMIDIButton < 384:
                msb = (self.requestMIDIButton >> 7) & 0x7f
                lsb = self.requestMIDIButton & 0x7f
                msg = bytes([0xf0] + [0,2,0x33,14,msb,lsb,8] + [0xf7])
                sock.sendto(msg, lpip)
                self.requestMIDIButton += 8

            time.sleep(0.1)

            self.upgradeFileLock.acquire()
            fileName = self.upgradeFile
            self.upgradeFile = ""
            self.upgradeFileLock.release()

            if len(fileName) > 0:
                self.doIPUpgrade(fileName, lpip)

        sock.close()
        self.stopIPReceiver()

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
                if self.upgradeFlag:
                    total_lines = float(len(self.upgradeMessages))
                    target_percent = 5.0
                    count = 0.0
                    for i in self.upgradeMessages:
                        outport.send(i)
                        time.sleep(0.07)
                        count += 1.0
                        percent = (count / total_lines) * 100.0
                        if percent >= target_percent:
                            self.currentStatus.appendLog(str(int(percent)) + '% complete\n')
                            target_percent += 5.0
                    self.upgradeMessages = None
                    self.upgradeFlag = False
                    self.currentStatus.appendLog("Completed\n");
                elif self.lp2_cmd != 0:
                    cmdRequest = mido.Message('sysex', data=[0,2,0x33,4,self.lp2_cmd])
                    outport.send(cmdRequest)
                    self.lp2_cmd = 0
                elif not self.lp_sysex_q.empty():
                    msg = self.lp_sysex_q.get()
                    btnReq = mido.Message('sysex', data=msg)
                    outport.send(btnReq)
                elif self.requestEffectButtons:
                    self.requestEffectButtons = False
                    btnReq = mido.Message('sysex', data=[0,2,0x33,9])
                    outport.send(btnReq)
                elif self.requestMIDIButton < 384:
                    msb = (self.requestMIDIButton >> 7) & 0x7f
                    lsb = self.requestMIDIButton & 0x7f
                    btnReq = mido.Message('sysex', data=[0,2,0x33,14,msb,lsb,8])
                    outport.send(btnReq)
                    self.requestMIDIButton += 8
                    time.sleep(0.05)
                elif self.sendEffectConfig:
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
                else:
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
                try:
                    self.upgradeMessages = mido.read_syx_file(fileName)
                    self.upgradeFlag = True
                except:
                    self.upgradeMessages = None
                    currentStatus.appendLog("Error reading MIDI Sysex file\n")

    def handleEffectButtons(self):
        self.requestEffectButtons = True
        self.requestMIDIButton = 0

    def handleSaveLPConf(self):
        fileName, _ = QFileDialog.getSaveFileName(self, "Save to file", "",
                                                  "Configuration files (*.cfg)")
        if len(fileName) > 0:
            if not fileName.endswith(".cfg"):
                fileName = fileName + ".cfg"
            self.saveLPConfig(fileName)

    def handleLoadLPConf(self):
        fileName, _ = QFileDialog.getOpenFileName(self, "Load from file", "",
                                                  "Configuration files (*.cfg)")
        if len(fileName) > 0:
            self.loadLPConfig(fileName)

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

#        print("Num tracks {}".format(s.tracks))
#        for i in range(s.tracks,8):
#            self.tracktitles[i].hide()
#            self.lengths[i].hide()
#            self.positions[i].hide()
#            self.statuses[i].hide()
#            self.psliders[i].hide()
#            self.vsliders[i].hide()
#            self.fsliders[i].hide()

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

    def saveLPConfig(self, fileName):
        config = {'MIDIButtons' : self.midiButtonDict,
                  'LP2Effects1' : self.effects1,
                  'LP2Effects2' : self.effects2}

        with open(fileName, 'w') as fp:
            json.dump(config, fp)

    def loadLPConfig(self, fileName):
        try:
            with open(fileName) as fp:
                config = json.load(fp)
                if config.get('MIDIButtons'):
                    self.setDeviceMIDIButtons(config['MIDIButtons'])
                if config.get('LP2Effects1') and config.get('LP2Effects2'):
                    self.setEffects(config['LP2Effects1'], config['LP2Effects2'])
        except FileNotFoundError:
            pass

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

    def parseButtonConfig(self, b):
        self.parsingMIDIButtonConfig += 1
        bti = self.midibtntype.currentIndex()
        btn = self.midibtnnum.currentIndex()
        currentbtn = bti * 128 + btn

        btnnum = (b[0] << 7) + b[1]
        btncnt = b[2]

        bi = 3;
        if btnnum != 0x3fff and btncnt == 8:
            for i in range(0, btncnt):
                flist = []
                for fi in range(0, 8):
                    func = (b[bi] << 7) + b[bi+1]
                    if func == 0x3fff:
                        func = -1
                    flist.append(func)
                    bi += 2
                self.midiButtonDict[btnnum] = flist
                if btnnum == currentbtn:
                    for si in range(0, 8):
                        idx = self.lpFunctions.keysLP1().index(flist[si])
                        self.stepboxes[si].setCurrentIndex(idx)
                btnnum += 1
        self.parsingMIDIButtonConfig -= 1

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

    def setEffects(self, neweffects1, neweffects2):
        if len(neweffects1) != 8 or len(neweffects2) != 8:
            return

        self.effects1 = neweffects1
        self.effects2 = neweffects2
        self.parsingEffectConfig = True
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
        self.sendEffectConfig = True

    def stepChanged(self, idx):
        if self.parsingMIDIButtonConfig == 0:
            bti = self.midibtntype.currentIndex()
            btn = self.midibtnnum.currentIndex()
            currentbtn = bti * 128 + btn
            flist = self.midiButtonDict.get(currentbtn, [-1,-1,-1,-1,-1,-1,-1,-1])

            altered = False
            for i in range(0, 8):
                vi = self.stepboxes[i].currentIndex()
                v = self.lpFunctions.keysLP1()[vi]
                if v != flist[i]:
                    altered = True
                    flist[i] = v

            if altered:
                self.midiButtonDict[currentbtn] = flist

                msb = (currentbtn >> 7) & 0x7f
                lsb = currentbtn & 0x7f
                msg = [0,2,0x33,16,msb,lsb]
                for f in flist:
                    msg.append((f >> 7) & 0x7f)
                    msg.append(f & 0x7f)
                self.lp_sysex_q.put(msg)

    def setDeviceMIDIButtons(self, newbtns):
        for k in newbtns.keys():
            btn = int(k)
            flist = self.midiButtonDict.get(btn, [-1,-1,-1,-1,-1,-1,-1,-1])

            listsEqual = True
            for i in range(0, 8):
                if newbtns[k][i] != flist[i]:
                    listsEqual = False
                    break

            if not listsEqual:
                flist = newbtns[k]
                self.midiButtonDict[btn] = flist
                msb = (btn >> 7) & 0x7f
                lsb = btn & 0x7f
                msg = [0,2,0x33,16,msb,lsb]
                for f in flist:
                    msg.append((f >> 7) & 0x7f)
                    msg.append(f & 0x7f)
                self.lp_sysex_q.put(msg)

                i = self.midibtntype.currentIndex()
                n = self.midibtnnum.currentIndex()
                displaybtn = i * 128 + n
                if displaybtn == btn:
                    self.parsingMIDIButtonConfig += 1
                    for si in range(0, 8):
                        idx = self.lpFunctions.keysLP1().index(flist[si])
                        self.stepboxes[si].setCurrentIndex(idx)
                    self.parsingMIDIButtonConfig -= 1

    def midibtntypeChanged(self, idx):
        self.parsingMIDIButtonConfig += 1
        bti = self.midibtntype.currentIndex()
        btn = self.midibtnnum.currentIndex()
        currentbtn = bti * 128 + btn

        flist = self.midiButtonDict.get(currentbtn, [-1,-1,-1,-1,-1,-1,-1,-1])
        for si in range(0, 8):
            idx = self.lpFunctions.keysLP1().index(flist[si])
            self.stepboxes[si].setCurrentIndex(idx)
        self.parsingMIDIButtonConfig -= 1

    def midibtnnumChanged(self, idx):
        self.midibtntypeChanged(0)

def main():
    app = QApplication(sys.argv)
    form = LP2CtrlApp()
    form.show()
    app.exec_()

if __name__ == "__main__":
    main()
