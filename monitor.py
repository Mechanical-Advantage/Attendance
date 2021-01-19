import config
import pyshark
import sqlite3 as sql
import time
import random
import threading
import signal
import subprocess
import sys
import os

interfaces = config.mon_interfaces

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

# Start a single monitor interface
def start_monitor(code):
	global interfaces

	# Try to create interface on specified monitor interface
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
	
	# Try to create interfaces until successful
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

	# Activate interface
	output = run_command(["sudo", "ip", "link", "set", "dev", interfaces[code]["monitor"], "up"])
	if output != "":
		print("Failed to start monitor " + code + " - could not activate interface '" + interfaces[code]["monitor"] + "'")
		return(False)

	print("Started monitor " + code + " on '" + interfaces[code]["monitor"] + "'")
	return(True)
		
# Shutdown a single monitor interface
def stop_monitor(code, interface):
	output = output = run_command(["sudo", "iw", "dev", interface, "del"])
	if output == "":
		print("Stopped monitor " + code)
	else:
		print("Failed to stop monitor " + code + " on '" + interface + "'")

# Shutdown all monitor interfaces
def stop_all():
	for code, value in interfaces.items():
		stop_monitor(code, value["monitor"])

# Monitor devices on a single interface
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
				write_queue.append([record_time, 0, record_value])
		
	capture = pyshark.LiveCapture(interface=interfaces[code]["monitor"])
	while True:
		try:
			capture.apply_on_packets(process)
		except:
			pass

# Monitor devices over the network
def network_monitor():
	global write_queue

    # Get list of possible ips
	ips = []
	for i in range(int(config.mon_ip_range[0].split(".")[-1]) + 1, int(config.mon_ip_range[1].split(".")[-1])):
		ips.append(".".join(config.mon_ip_range[0].split(".")[:-1] + [str(i)]))

	last_pings = {}
	while True:
		current_time = round(time.time())

		# Determine ips to ping
		ping_list = []
		for ip in ips:
			if ip in last_pings.keys():
				if current_time - last_pings[ip] < config.mon_success_wait:
					continue
			ping_list.append(ip)

		# Ping ips
		fping = subprocess.Popen(
			["fping", "-C", "1", "-r", "0", "-t", str(config.mon_ping_timeout), "-q"] + ping_list, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
		fping.wait()
		stdout, stderr = fping.communicate()
		fping_lines = stderr.decode("utf-8").split("\n")[:-1]

		# Lookup arp table
		arp = subprocess.Popen(
			["arp", "-a"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
		arp.wait()
		stdout, stderr = arp.communicate()
		arp_table = {}
		for line in stdout.decode("utf-8").split("\n")[:-1]:
			ip = line.split("(")[1].split(")")[0]
			mac = line.split(" at ")[1].split(" ")[0]
			if len(mac) == 17:
				arp_table[ip] = mac

		# Find successful detections
		for line in fping_lines:
			line_split = line.split(" : ")
			ip = line_split[0].rstrip()
			success = line_split[1] != "-"
			if success:
				if ip in arp_table.keys():
					mac = arp_table[ip]
					last_pings[ip] = current_time
					if mac not in config.mon_nolog:
						print(str(current_time) + " : NETWRK : " + mac)
						write_queue.append([current_time, 3, mac])
		
# Run db write thread
write_queue = []
def writer():
	global write_queue
	conn = sql.connect(config.data + "/logs.db")
	cur = conn.cursor()

	# Get id lookup table
	id_lookup_result = cur.execute("SELECT * FROM lookup").fetchall()
	id_lookup_cache = {}
	for id, value in id_lookup_result:
		id_lookup_cache[value] = id
	print("Loaded id lookup table, ready to write")

	# Write data periodically
	while True:
		time.sleep(config.mon_write_wait)
		write_queue_internal = write_queue
		write_queue = []
		print(str(round(time.time())) + " : WRITER : Writing " + str(len(write_queue_internal)) + " records")
		for record in write_queue_internal:
			if record[2] not in id_lookup_cache:
				cur.execute("INSERT INTO lookup(value) VALUES (?)", (record[1],))
				lookup_id = cur.execute("SELECT seq FROM sqlite_sequence WHERE name='lookup'").fetchall()[0][0] + 1
				id_lookup_cache[record[2]] = lookup_id
			else:
				lookup_id = id_lookup_cache[record[2]]
			cur.execute("INSERT INTO logs(timestamp,action,id) VALUES (?,?,?)", (record[0],record[1],lookup_id))
		conn.commit()
		print(str(round(time.time())) + " : WRITER : Finished writing " + str(len(write_queue_internal)) + " records")

# Shutdown signal
def shutdown(sig, frame):
	print("\nStarting clean shutdown. Please wait for completition.")
	stop_all()
	sys.exit(0)

signal.signal(signal.SIGINT, shutdown)

# Kill tshark
run_command(["sudo", "killall", "tshark"], output=False)

# Start other threads
writer = threading.Thread(target=writer, daemon=True)
writer.start()
if config.mon_network_enable:
	network_monitor = threading.Thread(target=network_monitor, daemon=True)
	network_monitor.start()

# Start monitors
monitors = []
for code in interfaces.keys():
	time.sleep(2)
	if start_monitor(code):
		monitors.append(threading.Thread(target=monitor, args=(code,), daemon=True))
		monitors[len(monitors)-1].start()

signal.pause()