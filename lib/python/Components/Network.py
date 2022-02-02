import os
import re
import netifaces as ni
from socket import *
from Components.Console import Console
from Components.PluginComponent import plugins
from Plugins.Plugin import PluginDescriptor
from Components.config import config


class Network:
	def __init__(self):
		self.ifaces = {}
		self.configuredNetworkAdapters = []
		self.NetworkState = 0
		self.DnsState = 0
		self.nameservers = []
		self.ethtool_bin = "/usr/sbin/ethtool"
		self.console = Console()
		self.linkConsole = Console()
		self.restartConsole = Console()
		self.deactivateInterfaceConsole = Console()
		self.activateInterfaceConsole = Console()
		self.resetNetworkConsole = Console()
		self.dnsConsole = Console()
		self.pingConsole = Console()
		self.config_ready = None
		self.friendlyNames = {}
		self.lan_interfaces = []
		self.wlan_interfaces = []
		self.remoteRootFS = None
		self.getInterfaces()

	def onRemoteRootFS(self):
		if self.remoteRootFS is None:
			import Harddisk
			for parts in Harddisk.getProcMounts():
				if parts[1] == '/' and parts[2] == 'nfs':
					self.remoteRootFS = True
					break
			else:
				self.remoteRootFS = False
		return self.remoteRootFS

	def isBlacklisted(self, iface):
		return iface in ('lo', 'wifi0', 'wmaster0', 'sit0', 'tun0', 'sys0', 'p2p0')

	def getInterfaces(self, callback=None):
		self.configuredInterfaces = []
		for device in self.getInstalledAdapters():
			self.getAddrInet(device, callback)

	# helper function
	def regExpMatch(self, pattern, string):
		if string is None:
			return None
		try:
			return pattern.search(string).group()
		except AttributeError:
			return None

	# helper function to convert ips from a sring to a list of ints
	def convertIP(self, ip):
		return [int(n) for n in ip.split('.')]

	def getAddrInet(self, iface, callback):
		data = {'up': False, 'dhcp': False, 'preup': False, 'predown': False}
		try:
			data['up'] = open('/sys/class/net/%s/carrier' % iface).read()
			if data['up']:
				self.configuredInterfaces.append(iface)
			nit = ni.ifaddresses(iface)
			data['ip'] = self.convertIP(nit[ni.AF_INET][0]['addr']) # ipv4
			data['netmask'] = self.convertIP(nit[ni.AF_INET][0]['netmask'])
			data['bcast'] = self.convertIP(nit[ni.AF_INET][0]['broadcast'])
			data['mac'] = nit[ni.AF_LINK][0]['addr'] # mac
			data['gateway'] = self.convertIP(ni.gateways()['default'][ni.AF_INET][0]) # default gw
		except:
			data['dhcp'] = True
			data['ip'] = [0, 0, 0, 0]
			data['netmask'] = [0, 0, 0, 0]
			data['gateway'] = [0, 0, 0, 0]
		if iface in self.ifaces:
			self.ifaces[iface].update(data)
		else:
			self.ifaces[iface] = data
		self.loadNetworkConfig(iface, callback)

	def writeNetworkConfig(self):
		self.configuredInterfaces = []
		fp = file('/etc/network/interfaces', 'w')
		fp.write("# automatically generated by enigma2\n# do NOT change manually!\n\n")
		fp.write("auto lo\n")
		fp.write("iface lo inet loopback\n\n")
		for ifacename, iface in self.ifaces.items():
			if iface['up']:
				fp.write("auto " + ifacename + "\n")
				self.configuredInterfaces.append(ifacename)
			if iface['dhcp']:
				fp.write("iface " + ifacename + " inet dhcp\n")
				fp.write("udhcpc_opts -T1 -t9\n")
			if not iface['dhcp']:
				fp.write("iface " + ifacename + " inet static\n")
				if 'ip' in iface:
					print tuple(iface['ip'])
					fp.write("	address %d.%d.%d.%d\n" % tuple(iface['ip']))
					fp.write("	netmask %d.%d.%d.%d\n" % tuple(iface['netmask']))
					if 'gateway' in iface:
						fp.write("	gateway %d.%d.%d.%d\n" % tuple(iface['gateway']))
			if "configStrings" in iface:
				fp.write(iface["configStrings"])
			if iface["preup"] is not False and "configStrings" not in iface:
				fp.write(iface["preup"])
			if iface["predown"] is not False and "configStrings" not in iface:
				fp.write(iface["predown"])
			fp.write("\n")
		fp.close()
		self.configuredNetworkAdapters = self.configuredInterfaces
		self.writeNameserverConfig()

	def writeNameserverConfig(self):
		try:
			Console().ePopen('rm -f /etc/resolv.conf')
			fp = open('/etc/resolv.conf', 'w')
			for nameserver in self.nameservers:
				fp.write("nameserver %d.%d.%d.%d\n" % tuple(nameserver))
			fp.close()
			if config.usage.dns.value.lower() not in ("dhcp-router", "custom"):
				Console().ePopen('rm -f /etc/enigma2/nameserversdns.conf')
				fp = open('/etc/enigma2/nameserversdns.conf', 'w')
				for nameserver in self.nameservers:
					fp.write("nameserver %d.%d.%d.%d\n" % tuple(nameserver))
				fp.close()
			#self.restartNetwork()
		except:
			print "[Network] resolv.conf or nameserversdns.conf - writing failed"

	def loadNetworkConfig(self, iface, callback=None):
		interfaces = []
		# parse the interfaces-file
		try:
			fp = file('/etc/network/interfaces', 'r')
			interfaces = fp.readlines()
			fp.close()
		except:
			print "[Network.py] interfaces - opening failed"

		ifaces = {}
		currif = ""
		for i in interfaces:
			split = i.strip().split(' ')
			if split[0] == "iface":
				currif = split[1]
			if currif == iface: #read information only for available interfaces
				if currif not in ifaces:
					ifaces[currif] = {}
					if len(split) == 4 and split[3] == "dhcp":
						ifaces[currif]["dhcp"] = True
					else:
						ifaces[currif]["dhcp"] = False
				if split[0] == "address":
					ifaces[currif]["address"] = map(int, split[1].split('.'))
					if "ip" in self.ifaces[currif]:
						if self.ifaces[currif]["ip"] != ifaces[currif]["address"] and ifaces[currif]["dhcp"] == False:
							self.ifaces[currif]["ip"] = map(int, split[1].split('.'))
				if split[0] == "netmask":
					ifaces[currif]["netmask"] = map(int, split[1].split('.'))
					if "netmask" in self.ifaces[currif]:
						if self.ifaces[currif]["netmask"] != ifaces[currif]["netmask"] and ifaces[currif]["dhcp"] == False:
							self.ifaces[currif]["netmask"] = map(int, split[1].split('.'))
				if split[0] == "gateway":
					ifaces[currif]["gateway"] = map(int, split[1].split('.'))
					if "gateway" in self.ifaces[currif]:
						if self.ifaces[currif]["gateway"] != ifaces[currif]["gateway"] and ifaces[currif]["dhcp"] == False:
							self.ifaces[currif]["gateway"] = map(int, split[1].split('.'))
				if split[0] == "pre-up":
					if "preup" in self.ifaces[currif]:
						self.ifaces[currif]["preup"] = i
				if split[0] in ("pre-down", "post-down"):
					if "predown" in self.ifaces[currif]:
						self.ifaces[currif]["predown"] = i

		for ifacename, iface in ifaces.items():
			if ifacename in self.ifaces:
				self.ifaces[ifacename]["dhcp"] = iface["dhcp"]
		if not self.console.appContainers:
			# save configured interfacelist
			self.configuredNetworkAdapters = self.configuredInterfaces
			# load ns only once
			self.loadNameserverConfig()
			if config.usage.dns.value != "dhcp-router":
				self.writeNameserverConfig()
			print "read configured interface:", ifaces
			# remove any password before info is printed to the debug log
			safe_ifaces = self.ifaces.copy()
			for intf in safe_ifaces:
				if 'preup' in safe_ifaces[intf] and safe_ifaces[intf]['preup'] is not False:
					safe_ifaces[intf]['preup'] = re.sub(' -k "\S*" ', ' -k ********* ', safe_ifaces[intf]['preup'])
			print "self.ifaces after loading:", safe_ifaces
			self.config_ready = True
			self.msgPlugins()
			if callback is not None:
				callback(True)

	def loadNameserverConfig(self):
		ipRegexp = "[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}"
		nameserverPattern = re.compile("nameserver +" + ipRegexp)
		ipPattern = re.compile(ipRegexp)

		resolv = []
		try:
			if config.usage.dns.value.lower() in ("dhcp-router", "custom"):
				fp = open('/etc/resolv.conf', 'r')
			else:
				fp = open('/etc/enigma2/nameserversdns.conf', 'r')
			resolv = fp.readlines()
			fp.close()
			self.nameservers = []
		except:
			print "[Network] resolv.conf or nameserversdns.conf - opening failed"

		for line in resolv:
			if self.regExpMatch(nameserverPattern, line) is not None:
				ip = self.regExpMatch(ipPattern, line)
				if ip:
					self.nameservers.append(self.convertIP(ip))

		print "nameservers:", self.nameservers

	def getInstalledAdapters(self):
		return [x for x in os.listdir('/sys/class/net') if not self.isBlacklisted(x)]

	def getConfiguredAdapters(self):
		return self.configuredNetworkAdapters

	def getNumberOfAdapters(self):
		return len(self.ifaces)

	def getFriendlyAdapterName(self, x):
		if x in self.friendlyNames.keys():
			return self.friendlyNames.get(x, x)
		self.friendlyNames[x] = self.getFriendlyAdapterNaming(x)
		return self.friendlyNames.get(x, x) # when we have no friendly name, use adapter name

	def getFriendlyAdapterNaming(self, iface):
		name = None
		if self.isWirelessInterface(iface):
			if iface not in self.wlan_interfaces:
				name = _("WLAN connection")
				if len(self.wlan_interfaces):
					name += " " + str(len(self.wlan_interfaces) + 1)
				self.wlan_interfaces.append(iface)
		else:
			if iface not in self.lan_interfaces:
				if iface == "eth1":
					name = _("VLAN connection")
				else:
					name = _("LAN connection")
				if len(self.lan_interfaces) and not iface == "eth1":
					name += " " + str(len(self.lan_interfaces) + 1)
				self.lan_interfaces.append(iface)
		return name

	def getFriendlyAdapterDescription(self, iface):
		if not self.isWirelessInterface(iface):
			return _('Ethernet network interface')

		moduledir = self.getWlanModuleDir(iface)
		if moduledir:
			name = os.path.basename(os.path.realpath(moduledir))
			if name.startswith('ath') or name.startswith('carl'):
				name = 'Atheros'
			elif name.startswith('rt2') or name.startswith('rt3') or name.startswith('rt5') or name.startswith('rt6') or name.startswith('rt7'):
				name = 'Ralink'
			elif name.startswith('zd'):
				name = 'Zydas'
			elif name.startswith('rtl') or name.startswith('r8'):
				name = 'Realtek'
			elif name.startswith('smsc'):
				name = 'SMSC'
			elif name.startswith('peg'):
				name = 'Pegasus'
			elif name.startswith('rn'):
				name = 'RNDIS'
			elif name.startswith('mw') or name.startswith('libertas'):
				name = 'Marvel'
			elif name.startswith('p5'):
				name = 'Prism'
			elif name.startswith('as') or name.startswith('ax'):
				name = 'ASIX'
			elif name.startswith('dm'):
				name = 'Davicom'
			elif name.startswith('mcs'):
				name = 'MosChip'
			elif name.startswith('at'):
				name = 'Atmel'
			elif name.startswith('iwm'):
				name = 'Intel'
			elif name.startswith('brcm') or name.startswith('bcm'):
				name = 'Broadcom'
		elif os.path.isdir('/tmp/bcm/' + iface):
			name = 'Broadcom'
		else:
			name = _('Unknown')

		return name + ' ' + _('wireless network interface')

	def getAdapterName(self, iface):
		return iface

	def getAdapterList(self):
		return self.ifaces.keys()

	def getAdapterAttribute(self, iface, attribute):
		print "Getting attribute ", attribute, " for adapter", iface
		if self.ifaces.get(iface, {}).get('up', False):
			self.getAddrInet(iface, None)
		return self.ifaces.get(iface, {}).get(attribute)

	def setAdapterAttribute(self, iface, attribute, value):
		print "setting for adapter", iface, "attribute", attribute, " to value", value
		if iface in self.ifaces:
			self.ifaces[iface][attribute] = value

	def removeAdapterAttribute(self, iface, attribute):
		if iface in self.ifaces and attribute in self.ifaces[iface]:
			del self.ifaces[iface][attribute]

	def getNameserverList(self):
		if len(self.nameservers) == 0:
			return [[0, 0, 0, 0], [0, 0, 0, 0]]
		else:
			return self.nameservers

	def clearNameservers(self):
		self.nameservers = []

	def addNameserver(self, nameserver):
		if nameserver not in self.nameservers:
			self.nameservers.append(nameserver)

	def removeNameserver(self, nameserver):
		if nameserver in self.nameservers:
			self.nameservers.remove(nameserver)

	def changeNameserver(self, oldnameserver, newnameserver):
		if oldnameserver in self.nameservers:
			for i in range(len(self.nameservers)):
				if self.nameservers[i] == oldnameserver:
					self.nameservers[i] = newnameserver

	def resetNetworkConfig(self, mode='lan', callback=None):
		self.commands = []
		self.commands.append("/etc/init.d/avahi-daemon stop")
		for iface in self.ifaces.keys():
			if iface != 'eth0' or not self.onRemoteRootFS():
				self.commands.append("/sbin/ip addr flush dev " + iface + " scope global")
		self.commands.append("/etc/init.d/networking stop")
		self.commands.append("killall -9 udhcpc")
		self.commands.append("rm /var/run/udhcpc*")
		self.resetNetworkConsole.eBatch(self.commands, self.resetNetworkFinishedCB, [mode, callback], debug=True)

	def resetNetworkFinishedCB(self, extra_args):
		(mode, callback) = extra_args
		if not self.resetNetworkConsole.appContainers:
			self.writeDefaultNetworkConfig(mode, callback)

	def writeDefaultNetworkConfig(self, mode='lan', callback=None):
		fp = file('/etc/network/interfaces', 'w')
		fp.write("# automatically generated by enigma2\n# do NOT change manually!\n\n")
		fp.write("auto lo\n")
		fp.write("iface lo inet loopback\n\n")
		if mode == 'wlan':
			fp.write("auto wlan0\n")
			fp.write("iface wlan0 inet dhcp\n")
		if mode == 'wlan-mpci':
			fp.write("auto ath0\n")
			fp.write("iface ath0 inet dhcp\n")
		if mode == 'lan':
			fp.write("auto eth0\n")
			fp.write("iface eth0 inet dhcp\n")
		fp.write("\n")
		fp.close()

		self.commands = []
		if mode == 'wlan':
			self.commands.append("/sbin/ifconfig eth0 down")
			self.commands.append("/sbin/ifconfig ath0 down")
			self.commands.append("/sbin/ifconfig wlan0 up")
		if mode == 'wlan-mpci':
			self.commands.append("/sbin/ifconfig eth0 down")
			self.commands.append("/sbin/ifconfig wlan0 down")
			self.commands.append("/sbin/ifconfig ath0 up")
		if mode == 'lan':
			self.commands.append("/sbin/ifconfig eth0 up")
			self.commands.append("/sbin/ifconfig wlan0 down")
			self.commands.append("/sbin/ifconfig ath0 down")
		self.commands.append("/etc/init.d/avahi-daemon start")
		self.resetNetworkConsole.eBatch(self.commands, self.resetNetworkFinished, [mode, callback], debug=True)

	def resetNetworkFinished(self, extra_args):
		(mode, callback) = extra_args
		if not self.resetNetworkConsole.appContainers:
			if callback is not None:
				callback(True, mode)

	def checkNetworkState(self, statecallback):
		self.NetworkState = 0
		self.pingConsole = Console()
		for server in ("www.openpli.org", "www.google.nl", "www.google.com"):
			self.pingConsole.ePopen(("/bin/ping", "/bin/ping", "-c", "1", server), self.checkNetworkStateFinished, statecallback)

	def checkNetworkStateFinished(self, result, retval, extra_args):
		(statecallback) = extra_args
		if self.pingConsole is not None:
			if retval == 0:
				self.pingConsole = None
				statecallback(self.NetworkState)
			else:
				self.NetworkState += 1
				if not self.pingConsole.appContainers:
					statecallback(self.NetworkState)

	def restartNetwork(self, callback=None):
		self.config_ready = False
		self.msgPlugins()
		self.commands = []
		self.commands.append("/etc/init.d/avahi-daemon stop")
		for iface in self.ifaces.keys():
			if iface != 'eth0' or not self.onRemoteRootFS():
				self.commands.append(("/sbin/ifdown", "/sbin/ifdown", iface))
				self.commands.append("/sbin/ip addr flush dev " + iface + " scope global")
		self.commands.append("/etc/init.d/networking stop")
		self.commands.append("killall -9 udhcpc")
		self.commands.append("rm /var/run/udhcpc*")
		self.commands.append("/etc/init.d/networking start")
		self.commands.append("/etc/init.d/avahi-daemon start")
		self.restartConsole.eBatch(self.commands, self.restartNetworkFinished, callback, debug=True)

	def restartNetworkFinished(self, extra_args):
		(callback) = extra_args
		if callback is not None:
			callback(True)

	def getLinkState(self, iface, callback):
		self.linkConsole.ePopen((self.ethtool_bin, self.ethtool_bin, iface), self.getLinkStateFinished, callback)

	def getLinkStateFinished(self, result, retval, extra_args):
		(callback) = extra_args
		if not self.linkConsole.appContainers:
			callback(result)

	def stopPingConsole(self):
		if self.pingConsole is not None:
			self.pingConsole.killAll()

	def stopLinkStateConsole(self):
		self.linkConsole.killAll()

	def stopDNSConsole(self):
		if self.dnsConsole is not None:
			self.dnsConsole.killAll()

	def stopRestartConsole(self):
		self.restartConsole.killAll()

	def stopGetInterfacesConsole(self):
		self.console.killAll()

	def stopDeactivateInterfaceConsole(self):
		self.deactivateInterfaceConsole.killAll()

	def stopActivateInterfaceConsole(self):
		self.activateInterfaceConsole.killAll()

	def checkforInterface(self, iface):
		return self.getAdapterAttribute(iface, 'up')

	def checkDNSLookup(self, statecallback):
		self.DnsState = 0
		self.dnsConsole = Console()
		for server in ("www.openpli.org", "www.google.nl", "www.google.com"):
			self.dnsConsole.ePopen(("/usr/bin/nslookup", "/usr/bin/nslookup", server), self.checkDNSLookupFinished, statecallback)

	def checkDNSLookupFinished(self, result, retval, extra_args):
		(statecallback) = extra_args
		if self.dnsConsole is not None:
			if retval == 0:
				self.dnsConsole = None
				statecallback(self.DnsState)
			else:
				self.DnsState += 1
				if not self.dnsConsole.appContainers:
					statecallback(self.DnsState)

	def deactivateInterface(self, ifaces, callback=None):
		self.config_ready = False
		self.msgPlugins()
		commands = []

		def buildCommands(iface):
			commands.append(("/sbin/ifdown", "/sbin/ifdown", "-f", iface))
			commands.append(("/sbin/ip", "/sbin/ip", "addr", "flush", "dev", iface, "scope", "global"))
			#wpa_supplicant sometimes doesn't quit properly on SIGTERM
			if os.path.exists('/var/run/wpa_supplicant/' + iface):
				commands.append("wpa_cli -i" + iface + " terminate")

		if isinstance(ifaces, (list, tuple)):
			for iface in ifaces:
				if iface != 'eth0' or not self.onRemoteRootFS():
					buildCommands(iface)
		else:
			if ifaces == 'eth0' and self.onRemoteRootFS():
				if callback is not None:
					callback(True)
				return
			buildCommands(ifaces)
		self.deactivateInterfaceConsole.eBatch(commands, self.deactivateInterfaceFinished, (ifaces, callback), debug=True)

	def deactivateInterfaceFinished(self, extra_args):
		(ifaces, callback) = extra_args
		if not self.deactivateInterfaceConsole.appContainers:
			if callback is not None:
				callback(True)

	def activateInterface(self, iface, callback=None):
		if self.config_ready:
			self.config_ready = False
			self.msgPlugins()
		if iface == 'eth0' and self.onRemoteRootFS():
			if callback is not None:
				callback(True)
			return
		commands = []
		commands.append(("/sbin/ifup", "/sbin/ifup", iface))
		self.activateInterfaceConsole.eBatch(commands, self.activateInterfaceFinished, callback, debug=True)

	def activateInterfaceFinished(self, extra_args):
		callback = extra_args
		if not self.activateInterfaceConsole.appContainers:
			if callback is not None:
				callback(True)

	def sysfsPath(self, iface):
		return '/sys/class/net/' + iface

	def isWirelessInterface(self, iface):
		if iface in self.wlan_interfaces:
			return True

		if os.path.isdir(self.sysfsPath(iface) + '/wireless'):
			return True

		# r871x_usb_drv on kernel 2.6.12 is not identifiable over /sys/class/net/'ifacename'/wireless so look also inside /proc/net/wireless
		device = re.compile('[a-z]{2,}[0-9]*:')
		ifnames = []
		fp = open('/proc/net/wireless', 'r')
		for line in fp:
			try:
				ifnames.append(device.search(line).group()[:-1])
			except AttributeError:
				pass
		if iface in ifnames:
			return True

		return False

	def getWlanModuleDir(self, iface=None):
		devicedir = self.sysfsPath(iface) + '/device'
		if not os.path.isdir(devicedir):
			return None
		moduledir = devicedir + '/driver/module'
		if os.path.isdir(moduledir):
			return moduledir

		# identification is not possible over default moduledir
		for x in os.listdir(devicedir):
			# rt3070 on kernel 2.6.18 registers wireless devices as usb_device (e.g. 1-1.3:1.0) and identification is only possible over /sys/class/net/'ifacename'/device/1-xxx
			if x.startswith("1-"):
				moduledir = devicedir + '/' + x + '/driver/module'
				if os.path.isdir(moduledir):
					return moduledir
		# rt73, zd1211b, r871x_usb_drv on kernel 2.6.12 can be identified over /sys/class/net/'ifacename'/device/driver, so look also here
		moduledir = devicedir + '/driver'
		if os.path.isdir(moduledir):
			return moduledir

		return None

	def detectWlanModule(self, iface=None):
		if not self.isWirelessInterface(iface):
			return None

		devicedir = self.sysfsPath(iface) + '/device'
		if os.path.isdir(devicedir + '/ieee80211'):
			return 'nl80211'

		moduledir = self.getWlanModuleDir(iface)
		if moduledir:
			module = os.path.basename(os.path.realpath(moduledir))
			if module in ('ath_pci', 'ath5k'):
				return 'madwifi'
			if module in ('rt73', 'rt73'):
				return 'ralink'
			if module == 'zd1211b':
				return 'zydas'
			if module == 'brcm-systemport':
				return 'brcm-wl'
		return 'wext'

	def calc_netmask(self, nmask):
		from struct import pack
		from socket import inet_ntoa
		mask = 1L << 31
		xnet = (1L << 32) - 1
		cidr_range = range(0, 32)
		cidr = long(nmask)
		if cidr not in cidr_range:
			print 'cidr invalid: %d' % cidr
			return None
		else:
			nm = ((1L << cidr) - 1) << (32 - cidr)
			netmask = str(inet_ntoa(pack('>L', nm)))
			return netmask

	def msgPlugins(self):
		if self.config_ready is not None:
			for p in plugins.getPlugins(PluginDescriptor.WHERE_NETWORKCONFIG_READ):
				p(reason=self.config_ready)

	def hotplug(self, event):
		interface = event['INTERFACE']
		if self.isBlacklisted(interface):
			return
		action = event['ACTION']
		if action == "add":
			print "[Network] Add new interface:", interface
			self.getAddrInet(interface, None)
		elif action == "remove":
			print "[Network] Removed interface:", interface
			try:
				del self.ifaces[interface]
			except KeyError:
				pass


iNetwork = Network()


def InitNetwork():
	pass
