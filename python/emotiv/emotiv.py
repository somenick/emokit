try:
	import pywinusb.hid as hid
	windows = True
except:
	windows = False

import sys
import time
import os
import logging
import struct
import multiprocessing
import signal
import fcntl
import errno

from contextlib import contextmanager
from aes import rijndael

logger = logging.getLogger("emotiv")

consumer_key = '\x31\x00\x35\x48\x31\x00\x35\x54\x38\x10\x37\x42\x38\x00\x37\x50' # key on qdot's repo, works on my device
consumer_key2 = '\x31\x00\x35\x54\x38\x10\x37\x42\x31\x00\x35\x48\x38\x00\x37\x50' # key on original repo
research_key = '\x31\x00\x39\x54\x38\x10\x37\x42\x31\x00\x39\x48\x38\x00\x37\x50'

KEYS = {
        'first consumer key': consumer_key,
        'second consumer key': consumer_key2,
        'research key': research_key
        }

sensorBits = {
	'F3': [10, 11, 12, 13, 14, 15, 0, 1, 2, 3, 4, 5, 6, 7], 
	'FC6': [214, 215, 200, 201, 202, 203, 204, 205, 206, 207, 192, 193, 194, 195], 
	'P7': [84, 85, 86, 87, 72, 73, 74, 75, 76, 77, 78, 79, 64, 65], 
	'T8': [160, 161, 162, 163, 164, 165, 166, 167, 152, 153, 154, 155, 156, 157], 
	'F7': [48, 49, 50, 51, 52, 53, 54, 55, 40, 41, 42, 43, 44, 45], 
	'F8': [178, 179, 180, 181, 182, 183, 168, 169, 170, 171, 172, 173, 174, 175], 
	'T7': [66, 67, 68, 69, 70, 71, 56, 57, 58, 59, 60, 61, 62, 63], 
	'P8': [158, 159, 144, 145, 146, 147, 148, 149, 150, 151, 136, 137, 138, 139], 
	'AF4': [196, 197, 198, 199, 184, 185, 186, 187, 188, 189, 190, 191, 176, 177], 
	'F4': [216, 217, 218, 219, 220, 221, 222, 223, 208, 209, 210, 211, 212, 213], 
	'AF3': [46, 47, 32, 33, 34, 35, 36, 37, 38, 39, 24, 25, 26, 27], 
	'O2': [140, 141, 142, 143, 128, 129, 130, 131, 132, 133, 134, 135, 120, 121], 
	'O1': [102, 103, 88, 89, 90, 91, 92, 93, 94, 95, 80, 81, 82, 83], 
	'FC5': [28, 29, 30, 31, 16, 17, 18, 19, 20, 21, 22, 23, 8, 9]
}

sensorlist = sensorBits.keys()

MAX_RATE = 128

class DeviceNotFound(Exception):
        pass

class DeviceOff(Exception):
        pass

class UnknownKey(Exception):
        pass

class CannotOpenDevice(Exception):
        pass

@contextmanager
def timeout(seconds):
    def timeout_handler(signum, frame):
        pass

    original_handler = signal.signal(signal.SIGALRM, timeout_handler)

    try:
        signal.alarm(seconds)
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, original_handler)

class EmotivPacket(object):
	def __init__(self, data):
		self.counter = ord(data[0])
		self.sync = self.counter == 0xe9
		self.gyroX = ord(data[29]) - 102
		self.gyroY = ord(data[30]) - 104
		
		for name, bits in sensorBits.items():
			level = 0
			for i in range(13, -1, -1):
				level <<= 1
				b, o = (bits[i] / 8) + 1, bits[i] % 8
				level |= (ord(data[b]) >> o) & 1
			strength = 4#(ord(data[j]) >> 3) & 1
			setattr(self, name, (level, strength))

        def __repr__(self):
		return 'EmotivPacket(counter=%i, gyroX=%i, gyroY=%i)' % (
				self.counter, 
				self.gyroX, 
				self.gyroY, 
			)

class Emotiv(object):
	def __init__(self, rate = 128):
                self._packets = multiprocessing.Queue()
		
                if 0 < rate <= MAX_RATE:
                        self.rate = rate
                else:
                        raise Exception, "Maximum sampling rate is 128Hz"

		self.setup_win() if windows else self.setup_posix()

                self.detect_key()

                def process():
                        while True:
                                packet = self.read_posix()
                                self._packets.put(packet)

                self.reader = multiprocessing.Process(target = process)
                self.reader.start()

        def detect_key(self):
                for key_name, key in KEYS.iteritems():
                        self.rijn = rijndael(key, 16)
                        successive = []
                        
                        # Read a couple of times because first readings are misleading
                        for i in range(10): self.read_posix()
                        
                        # Sample the raw data 20 times
                        for i in range(20):
                                fst = self.read_posix()
                                snd = self.read_posix()

                                # Account for the counter resetting
                                if fst.counter != 127 and fst.counter != 230:
                                        successive.append((fst, snd))

                        # If the counter increments correctly, we got the right key!
                        if all(map(lambda pair: pair[0].counter+1 == pair[1].counter, successive)):
                                self._key = key
                                return

                raise UnknownKey, "Cannot decrypt data: Unknown key."
        
	def setup_win(self):
                try:        
                        filter = hid.HidDeviceFilter(vendor_id=0x21A1, product_name='Brain Waves')
                        devices = filter.get_devices()

                        self.device = devices[0]
                        self.device.open()
                        
                        def handle(data):
                                assert data[0] == 0
                                self.gotData(''.join(map(chr, data[1:])))

                                self.device.set_raw_data_handler(handle)

                except IndexError:
                        raise DeviceNotFound, "Device was not found."
                except:
                        raise CannotOpenDevice, "Error opening the device"
	
	def setup_posix(self):
                if os.path.exists('/dev/eeg/raw'):
                        self._decrypted = True
                        self.device = open('/dev/eeg/raw')
                else:
                        self._decrypted = False

                        if os.path.exists("/dev/hidraw2"):  
					self.device = open("/dev/hidraw2")
                        elif os.path.exists('/dev/hidraw1'):
					self.device = open("/dev/hidraw1")
                        else:
                                raise DeviceNotFound, "Device was not found."

        def read_posix(self):
                try:
                        with timeout(1):
                                data = self.device.read(32)
                except IOError:
                        raise DeviceOff, "Your dongle is there, now turn your device on!"

                if not self._decrypted:
                        data = self.rijn.decrypt(data[:16]) + self.rijn.decrypt(data[16:])

                return EmotivPacket(data)


	def dequeue(self):
		while True:
                        yield self._packets.get()
                        
	def close(self):
		if windows:
			self.device.close()
		else:
			self.reader.terminate()
			self.hidraw.close()

        def __del__(self):
                self.close()

