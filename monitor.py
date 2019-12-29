import config
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

interfaces = config.mon_interfaces
thread_count = 0

def run_command(args, output=True):
	if output:
		process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		stdout, stderr = process.communicate()
		result = stdout.decode("utf-8")
		result += stderr.decode("utf-8")
		return(result)
	else:
		process = subprocess.call(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
		return

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
			run_command(["sudo", "iw", "dev", result, "del"], output=False)
	if mon_number >= 99:
		print("Failed to start monitor " + code + " - could not create virutal interface")
		return(False)

	#Activate interface
	output = run_command(["sudo", "ip", "link", "set", "dev", interfaces[code]["monitor"], "up"])
	if output != "":
		print("Failed to start monitor " + code + " - could not activate interface '" + interfaces[code]["monitor"] + "'")
		return(False)

	print("Started monitor " + code + " on '" + interfaces[code]["monitor"] + "'")
	return(True)
		
def stop_monitor(code, interface):
	output = output = run_command(["sudo", "iw", "dev", interface, "del"])
	if output == "":
		print("Stopped monitor " + code)
	else:
		print("Failed to stop monitor " + code + " on '" + interface + "'")

def stop_all():
	for code, value in interfaces.items():
		stop_monitor(code, value["monitor"])

def monitor(code):
	global interfaces
	global write_queue

	def process(packet):
		try:
			record_time = round(time.time())
			record_value = packet.wlan.sa_resolved
			should_log = packet.wlan.sa_resolved not in config.mon_nolog
		except:
			x = 0
		else:
			if should_log:
				print(str(record_time) + " : " + code + " : " + record_value)
				write_queue.append([record_time, record_value])
		
	capture = pyshark.LiveCapture(interface=interfaces[code]["monitor"])
	while True:
		try:
			capture.apply_on_packets(process)
		except:
			pass
		
#Run db write thread
write_queue = []
def writer():
	global write_queue
	conn = sql.connect(config.data + "/logs.db")
	cur = conn.cursor()

	#Get id lookup table
	id_lookup_result = cur.execute("SELECT * FROM lookup").fetchall()
	id_lookup_cache = {}
	for id, value in id_lookup_result:
		id_lookup_cache[value] = id
	print("Loaded id lookup table, ready to write")

	#Write data periodically
	while True:
		time.sleep(config.mon_write_wait)
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

#Shutdown signal
def shutdown(sig, frame):
	print("\nStarting clean shutdown. Please wait for completition.")
	stop_all()
	sys.exit(0)

signal.signal(signal.SIGINT, shutdown)

#Kill tshark
run_command(["sudo", "killall", "tshark"], output=False)

#Start monitors
monitors = []
for code in interfaces.keys():
	time.sleep(2)
	if start_monitor(code):
		monitors.append(threading.Thread(target=monitor, args=(code,), daemon=True))
		monitors[len(monitors)-1].start()

signal.pause()