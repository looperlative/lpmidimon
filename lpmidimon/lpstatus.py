#
# Copyright 2021 - Looperlative Audio Products, LLC
#
import threading
from copy import deepcopy

class LPStatus:
    def __init__(self):
        self.tracks = 0;
        self.selected_track = 0;
        self.levels = []
        self.pans = []
        self.feedbacks = []
        self.lengths = []
        self.positions = []
        self.statuses = []
        self.log = ""
        self.lock = threading.Lock()

    def __deepcopy__(self, memo):
        newone = type(self)()

        self.lock.acquire()
        newone.__dict__.update(self.__dict__)
        newone.levels = deepcopy(self.levels, memo)
        newone.pans = deepcopy(self.pans, memo)
        newone.feedbacks = deepcopy(self.feedbacks, memo)
        newone.lengths = deepcopy(self.lengths, memo)
        newone.positions = deepcopy(self.positions, memo)
        newone.statuses = deepcopy(self.statuses, memo)
        self.lock.release()

        newone.lock = threading.Lock()
        return newone

    def setStatus(self, nv):
        self.lock.acquire()
        self.tracks = nv.tracks
        self.selected_track = nv.selected_track
        self.levels = nv.levels
        self.pans = nv.pans
        self.feedbacks = nv.feedbacks
        self.lengths = nv.lengths
        self.positions = nv.positions
        self.statuses = nv.statuses
        self.lock.release()

    def __convert_7bit_packed_to_int(b):
        v = 0
        shift = 0
        for i in b:
            v += (i << shift)
            shift += 7
        return v

    def __parseMIDIStatusTrack(self, b):
        self.statuses.append(b[0])
        self.levels.append(-b[1])
        self.pans.append(b[2])
        self.feedbacks.append(b[3])
        self.lengths.append(float(LPStatus.__convert_7bit_packed_to_int(b[4:9])) / 48000.0)
        self.positions.append(float(LPStatus.__convert_7bit_packed_to_int(b[9:])) / 48000.0)


    def parseMIDIStatus(self, b):
        self.tracks = b[5]
        self.selected_track = b[6]

        self.__parseMIDIStatusTrack(b[7:21])
        self.__parseMIDIStatusTrack(b[21:35])
        self.__parseMIDIStatusTrack(b[35:49])
        self.__parseMIDIStatusTrack(b[49:63])

    def getStatusString(status):
        if status == 0:
            return 'empty'
        elif status == 1:
            return 'recording'
        elif status == 2:
            return 'overdubbing'
        elif status == 3:
            return 'stopped'
        elif status == 4:
            return 'playing'
        elif status == 5:
            return 'replacing'
        else:
            return 'unknown'

    def printStatusTrack(self, t):
        ts = "Track " + str(t) + " "
        ti = t - 1
        print(ts + "Status: " + LPStatus.getStatusString(self.statuses[ti])
              + ", Level: " + str(self.levels[ti])
              + ", Pan: " + str(self.pans[ti])
              + ", Feedback: " + str(self.feedbacks[ti])
              + ", Length: " + format(self.lengths[ti], '.2f')
              + ", Position: " + format(self.positions[ti], '.2f') )

    def printStatusLocked(self):
        self.lock.acquire()
        print("Selected Track: " + str(self.selected_track))
        for t in range(1, self.tracks + 1):
            self.printStatusTrack(t)
        self.lock.release()

    def printStatus(self):
        s = deepcopy(self)
        s.printStatusLocked()

    def getSnapshot(self):
        return deepcopy(self)

    def appendLog(self, text):
        self.lock.acquire()
        self.log += text
        self.lock.release()

    def getLog(self):
        self.lock.acquire()
        ltext = self.log
        self.log = ""
        self.lock.release()
        return ltext
