from os import path
from fcntl import ioctl
from struct import pack, unpack
from time import localtime, time, timezone

from Tools.Directories import fileExists
from Components.SystemInfo import BoxInfo

def getBoxProcType():
	procmodeltype = "unknown"
	try:
		if fileExists("/proc/stb/info/type"):
			procmodeltype = open("/proc/stb/info/type", "r").readline().strip().lower()
	except IOError:
		print("[StbHardware] getBoxProcType failed!")
	return procmodeltype

def getBoxProc():
	procmodel = "unknown"
	try:
		if fileExists("/proc/stb/info/hwmodel"):
			procmodel = open("/proc/stb/info/hwmodel", "r").readline().strip().lower()
		elif fileExists("/proc/stb/info/azmodel"):
			procmodel = open("/proc/stb/info/model", "r").readline().strip().lower()
		elif fileExists("/proc/stb/info/gbmodel"):
			procmodel = open("/proc/stb/info/gbmodel", "r").readline().strip().lower()
		elif fileExists("/proc/stb/info/vumodel") and not fileExists("/proc/stb/info/boxtype"):
			procmodel = open("/proc/stb/info/vumodel", "r").readline().strip().lower()
		elif fileExists("/proc/stb/info/boxtype") and not fileExists("/proc/stb/info/vumodel"):
			procmodel = open("/proc/stb/info/boxtype", "r").readline().strip().lower()
		elif fileExists("/proc/boxtype"):
			procmodel = open("/proc/boxtype", "r").readline().strip().lower()
		elif fileExists("/proc/device-tree/model"):
			procmodel = open("/proc/device-tree/model", "r").readline().strip()[0:12]
		elif fileExists("/sys/firmware/devicetree/base/model"):
			procmodel = open("/sys/firmware/devicetree/base/model", "r").readline().strip()
		else:
			procmodel = open("/proc/stb/info/model", "r").readline().strip().lower()
	except IOError:
		print("[StbHardware] getBoxProc failed!")
	return procmodel

def getHWSerial():
	hwserial = "unknown"
	try:
		if fileExists("/proc/stb/info/sn"):
			hwserial = open("/proc/stb/info/sn", "r").read().strip()
		elif fileExists("/proc/stb/info/serial"):
			hwserial = open("/proc/stb/info/serial", "r").read().strip()
		elif fileExists("/proc/stb/info/serial_number"):
			hwserial = open("/proc/stb/info/serial_number", "r").read().strip()
		else:
			hwserial = open("/sys/class/dmi/id/product_serial", "r").read().strip()
	except IOError:
		print("[StbHardware] getHWSerial failed!")
	return hwserial

def getBoxRCType():
	boxrctype = "unknown"
	try:
		if fileExists("/proc/stb/ir/rc/type"):
			boxrctype = open("/proc/stb/ir/rc/type", "r").read().strip()
	except IOError:
		print("[StbHardware] getBoxRCType failed!")
	return boxrctype


def getHWSerial():
	hwserial = "unknown"
	try:
		if fileExists("/proc/stb/info/sn"):
			hwserial = open("/proc/stb/info/sn", "r").read().strip()
		else:
			hwserial = open("/proc/stb/info/serial", "r").read().strip()
	except IOError:
		print("[StbHardware] getHWSerial failed!")
	return hwserial

def getBoxRCType():
	boxrctype = "unknown"
	try:
		if fileExists("/proc/stb/ir/rc/type"):
			boxrctype = open("/proc/stb/ir/rc/type", "r").read().strip()
	except IOError:
		print("[StbHardware] getBoxRCType failed!")
	return boxrctype

def getFPVersion():
	ret = "unknown"
	try:
		if BoxInfo.getItem("platform") == "dm4kgen" or BoxInfo.getItem("model") in ("dm520", "dm7080", "dm820"):
			ret = open("/proc/stb/fp/version", "r").read()
		else:
			fp = open("/dev/dbox/fp0")
			ret = ioctl(fp.fileno(), 0)
	except IOError:
		try:
			fp = open("/dev/dbox/fp0")
			ret = ioctl(fp.fileno(), 0)
			fp.close()
		except IOError:
			try:
				ret = open("/sys/firmware/devicetree/base/bolt/tag", "r").read().rstrip("\0")
			except:
				print "[StbHardware] getFPVersion failed!"
	return ret


def setFPWakeuptime(wutime):
	try:
		open("/proc/stb/fp/wakeup_time", "w").write(str(wutime))
	except IOError:
		try:
			fp = open("/dev/dbox/fp0")
			ioctl(fp.fileno(), 6, pack('L', wutime)) # set wake up
			fp.close()
		except IOError:
			print "[StbHardware] setFPWakeupTime failed!"


def setRTCoffset(forsleep=None):
	forsleep = 7200 + timezone if localtime().tm_isdst == 0 else 3600 - timezone
	# t_local = localtime(int(time()))  # This line does nothing!
	# Set RTC OFFSET (diff. between UTC and Local Time)
	try:
		open("/proc/stb/fp/rtc_offset", "w").write(str(forsleep))
		print "[RTC] set RTC offset to %s sec." % (forsleep)
	except IOError:
		print "[StbHardware] setRTCoffset failed!"


def setRTCtime(wutime):
	if path.exists("/proc/stb/fp/rtc_offset"):
		setRTCoffset()
	try:
		open("/proc/stb/fp/rtc", "w").write(str(wutime))
	except IOError:
		try:
			fp = open("/dev/dbox/fp0")
			ioctl(fp.fileno(), 0x101, pack('L', wutime)) # set wake up
			fp.close()
		except IOError:
			print "[StbHardware] setRTCtime failed!"


def getFPWakeuptime():
	ret = 0
	try:
		ret = long(open("/proc/stb/fp/wakeup_time", "r").read())
	except IOError:
		try:
			fp = open("/dev/dbox/fp0")
			ret = unpack('L', ioctl(fp.fileno(), 5, '    '))[0] # get wakeuptime
			fp.close()
		except IOError:
			print "[StbHardware] getFPWakeupTime failed!"
	return ret


wasTimerWakeup = None


def getFPWasTimerWakeup():
	global wasTimerWakeup
	if wasTimerWakeup is not None:
		return wasTimerWakeup
	wasTimerWakeup = False
	try:
		wasTimerWakeup = int(open("/proc/stb/fp/was_timer_wakeup", "r").read()) and True or False
	except:
		try:
			fp = open("/dev/dbox/fp0")
			wasTimerWakeup = unpack('B', ioctl(fp.fileno(), 9, ' '))[0] and True or False
			fp.close()
		except IOError:
			print "[StbHardware] wasTimerWakeup failed!"
	if wasTimerWakeup:
		# clear hardware status
		clearFPWasTimerWakeup()
	return wasTimerWakeup


def clearFPWasTimerWakeup():
	try:
		open("/proc/stb/fp/was_timer_wakeup", "w").write('0')
	except:
		try:
			fp = open("/dev/dbox/fp0")
			ioctl(fp.fileno(), 10)
			fp.close()
		except IOError:
			print "[StbHardware] clearFPWasTimerWakeup failed!"
