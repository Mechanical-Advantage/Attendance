import pyshark
import sqlite3 as sql
import time
import random
import threading
import signal
import subprocess
import sys
import subprocess
import os

#Config
log_db = "/home/attendance/Attendance_data/logs.db"
write_wait = 10 # secs, length of time between writes
interfaces = {
	"INTERN": {
		"standard": "wlp2s0"
	},
	# "BELKIN": {
	# 	"standard": "wlx00173f847fbf"
	# },
	"PROXIM": {
		"standard": "wlx0020a6f69098"
	}
}
no_log = ["00:17:3f:84:7f:bf", "00:20:a6:f6:90:98"] #BELKIN, PROXIM

def run_command(args):
	process = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	result = process.stdout.decode("utf-8")
	result += process.stderr.decode("utf-8")
	return(result)

def get_interfaces():
	result = run_command(["iwconfig"])
	result = [x for x in result.split("\n") if x[:1] != " " and x[:1] != "\t" and len(x) > 0]
	result = [x.split(" ")[0] for x in result]
	return(result)

def start_monitor(code):
	global interfaces

	#Try to create interface on specified monitor interface
	def create_interface(standard, monitor):
		result = ""
		old_interfaces = get_interfaces()
		output = run_command(["sudo", "iw", "dev", standard, "interface", "add", monitor, "type", "monitor"])
		if output != "":
			return("")

		time.sleep(0.5)
		new_interfaces = get_interfaces()
		for new in new_interfaces:
			if new not in old_interfaces:
				result = new
				break
		return(result)
	
	#Try to create interfaces until successful
	mon_number = 0
	while mon_number < 99:
		result = create_interface(interfaces[code]["standard"], "mon" + str(mon_number))
		if result[:3] == "mon":
			interfaces[code]["monitor"] = result
			break
		else:
			mon_number += 1
			run_command(["sudo", "iw", "dev", result, "del"])
	if mon_number > 99:
		print("Failed to start monitor " + code + " - could not create virutal interface")
		return(False)

	#Activate interface
	output = run_command(["sudo", "ip", "link", "set", "dev", interfaces[code]["monitor"], "up"])
	if output != "":
		print("Failed to start monitor " + code + " - could not activate interface '" + interfaces[code]["monitor"] + "'")
		return(False)

	print("Started monitor " + code + " on '" + interfaces[code]["monitor"] + "'")
	return(True)
		
def stop_monitors():
	global interfaces
	for code in interfaces.keys():
		output = output = run_command(["sudo", "iw", "dev", interfaces[code]["monitor"], "del"])
		if output == "":
			print("Stopped monitor " + code)
		else:
			print("Failed to stop monitor " + code + " on '" + interfaces[code]["monitor"])

def shutdown(sig, frame):
	print("\nStarting clean shutdown. Please wait for completition.")
	stop_monitors()
	sys.exit(0)
	
signal.signal(signal.SIGINT, shutdown)

def monitor(code):
	global interfaces
	global write_queue

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
		
	capture = pyshark.LiveCapture(interface=interfaces[code]["monitor"])
	capture.apply_on_packets(process)
		
#Run db write thread
write_queue = []
def writer():
	global write_queue
	conn = sql.connect(log_db)
	cur = conn.cursor()

	#Get id lookup table
	id_lookup_result = cur.execute("SELECT * FROM lookup").fetchall()
	id_lookup_cache = {}
	for id, value in id_lookup_result:
		id_lookup_cache[value] = id
	print("Loaded id lookup table, ready to write")

	while True:
		time.sleep(write_wait)
		write_queue_internal = write_queue
		write_queue = []
		print(str(round(time.time())) + " : WRITER : Writing " + str(len(write_queue_internal)) + " records")
		for record in write_queue_internal:
			if record[1] not in id_lookup_cache:
				cur.execute("INSERT INTO lookup(value) VALUES (?)", (record[1],))
				lookup_id = cur.execute("SELECT seq FROM sqlite_sequence WHERE name='lookup'").fetchall()[0][0] + 1
				id_lookup_cache[record[1]] = lookup_id
			else:
				lookup_id = id_lookup_cache[record[1]]
			cur.execute("INSERT INTO logs(timestamp,action,id) VALUES (?,0,?)", (record[0],lookup_id))
		conn.commit()
		print(str(round(time.time())) + " : WRITER : Finished writing " + str(len(write_queue_internal)) + " records")
writer = threading.Thread(target=writer, daemon=True)
writer.start()	

#Start monitors
monitors = []
for code in interfaces.keys():
	if start_monitor(code):
		monitors.append(threading.Thread(target=monitor, args=(code,), daemon=True))
		monitors[len(monitors)-1].start()

signal.pause()
