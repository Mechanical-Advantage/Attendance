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
		
def stop_monitor(code):
	global interfaces
	output = output = run_command(["sudo", "iw", "dev", interfaces[code]["monitor"], "del"])
	if output == "":
		print("Stopped monitor " + code)
	else:
		print("Failed to stop monitor " + code + " on '" + interfaces[code]["monitor"])

def stop_all():
	for code in interfaces.keys():
		stop_monitor(code)

restart_signal = False
def monitor(code):
	global interfaces
	global write_queue
	global restart_signal
	global thread_count
	last_packet = time.time()
	thread_count += 1

	def process(packet):
		nonlocal last_packet
		last_packet = time.time()
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
			capture.apply_on_packets(process, timeout=config.mon_restart_checkperiod)
		except:
			pass
		if restart_signal: # stop b/c script restarting
			thread_count -= 1
			return
		if time.time() - last_packet > config.mon_restart_timeout: # problem w/ interface, restart script
			print("Interface", code, "not working, triggering restart")
			restart_signal = True
			thread_count -= 1
			return
		
#Run db write thread
write_queue = []
def writer():
	global thread_count
	global write_queue
	thread_count += 1
	conn = sql.connect(config.data + "/logs.db")
	cur = conn.cursor()

	#Get id lookup table
	id_lookup_result = cur.execute("SELECT * FROM lookup").fetchall()
	id_lookup_cache = {}
	for id, value in id_lookup_result:
		id_lookup_cache[value] = id
	print("Loaded id lookup table, ready to write")

	#Write data periodically
	while not restart_signal:
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

	#Script restarting
	conn.close()
	print("Database connection closed")
	thread_count -= 1

writer = threading.Thread(target=writer, daemon=True)
writer.start()

#Overall control
def shutdown(sig, frame):
	print("\nStarting clean shutdown. Please wait for completition.")
	stop_all()
	sys.exit(0)

def restart():
	stop_all()
	time.sleep(1)
	os.execl(sys.executable, sys.executable, * sys.argv)

signal.signal(signal.SIGINT, shutdown)

#Start monitors
monitors = []
thread_count = 0
run_command(["sudo", "killall", "tshark"]) # kill b/c can cause problems on restart
for code in interfaces.keys():
	time.sleep(2)
	if start_monitor(code):
		monitors.append(threading.Thread(target=monitor, args=(code,), daemon=True))
		monitors[len(monitors)-1].start()

#Wait for restart signal
while True:
	time.sleep(1)
	if restart_signal:
		print("Waiting for all threads to exit...")
		while thread_count > 0:
			time.sleep(1)
		print("All threads exited, beginning restart")
		time.sleep(1)
		restart()