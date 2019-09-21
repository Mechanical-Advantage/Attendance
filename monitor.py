import pyshark
import time
import threading
import signal
import sys
import os

#config
log_path = "../Attendance_test/Attendance_data/logs/monitor.log"
interfaces = {
"INTERN": "wlp6s0",
"BELKIN": "wlx00173f847fbf",
"PROXIM": "wlx0020a6f69098"
}
no_log = ["c4:17:fe:af:5d:a5", "00:17:3f:84:7f:bf", "00:20:a6:f6:90:98"] #INTERN, BELKIN, PROXIM

mon_interfaces = {}
def start_monitor(code, interface):
	result = os.popen("sudo airmon-ng start " + interface).read()
	mon_interface = result.split("enabled on ")
	if len(mon_interface) > 1:
		mon_interface = mon_interface[1].split(")")[0]
		mon_interfaces[code] = mon_interface
		print("Started monitor " + code)
		return(True)
	else:
		print("Failed to start monitor " + code)
		return(False)
		
def stop_monitors():
	for code, interface in mon_interfaces.items():
		os.system("sudo airmon-ng stop " + interface + " > /dev/null")
		print("Stopped monitor " + code)

def shutdown(sig, frame):
	print("\nStarting clean shutdown. Please wait for completition.")
	stop_monitors()
	log.close()
	sys.exit(0)
	
signal.signal(signal.SIGINT, shutdown)

def monitor(code, interface):
	if start_monitor(code, interface):
		def process(packet):
			try:
				text = str(round(time.time())) + " : " + code + " : " + packet.wlan.sa_resolved
				should_log = packet.wlan.sa_resolved not in no_log
			except:
				x = 0
			else:
				if should_log:
					print(text)
					log.write(text + "\n")
		capture = pyshark.LiveCapture(interface=mon_interfaces[code])
		capture.apply_on_packets(process)

monitors = []
log = open(log_path, "a")
for code, interface in interfaces.items():
	monitors.append(threading.Thread(target=monitor, args=(code,interface), daemon=True))
	monitors[len(monitors)-1].start()

signal.pause()
