import pyshark
import sqlite3 as sql
import time
import threading
import signal
import sys
import os

#Config
log_db = "./logs.db"
write_wait = 10 # secs, length of time between writes
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
	sys.exit(0)
	
signal.signal(signal.SIGINT, shutdown)

def monitor(code, interface):
	global write_queue
	if start_monitor(code, interface):
		def process(packet):
			try:
				record_time = round(time.time())
				record_value = packet.wlan.sa_resolved
				should_log = packet.wlan.sa_resolved not in no_log
			except:
				x = 0
			else:
				if should_log:
					print(str(record_time) + " : " + code + " : " + record_value)
					write_queue.append([record_time, record_value])
					
		capture = pyshark.LiveCapture(interface=mon_interfaces[code])
		capture.apply_on_packets(process)
		
#Run db write thread
write_queue = []
def writer():
	global write_queue
	conn = sql.connect(log_db)
	cur = conn.cursor()
	while True:
		time.sleep(write_wait)
		write_queue_internal = write_queue
		write_queue = []
		print(str(round(time.time())) + " : WRITER : Writing " + str(len(write_queue_internal)) + " records")
		for record in write_queue_internal:
			lookup_id = cur.execute("SELECT id FROM lookup WHERE value=?", (record[1],)).fetchall()
			if len(lookup_id) == 0:
				cur.execute("INSERT INTO lookup(value) VALUES (?)", (record[1],))
				lookup_id = cur.execute("SELECT id FROM lookup WHERE value=?", (record[1],)).fetchall()[0][0]
			else:
				lookup_id = lookup_id[0][0]
			cur.execute("INSERT INTO logs(timestamp,action,id) VALUES (?,0,?)", (record[0],lookup_id))
		conn.commit()
		print(str(round(time.time())) + " : WRITER : Finished writing " + str(len(write_queue_internal)) + " records")
writer = threading.Thread(target=writer, daemon=True)
writer.start()	

#Start monitors
monitors = []
for code, interface in interfaces.items():
	monitors.append(threading.Thread(target=monitor, args=(code,interface), daemon=True))
	monitors[len(monitors)-1].start()

signal.pause()
