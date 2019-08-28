#packet.wlan.sa_resolved

import pyshark
import time
import sys

capture = pyshark.LiveCapture(interface=sys.argv[1])
print("Starting to monitor...")
for packet in capture.sniff_continuously():
	try:
		print(str(round(time.time())) + " : " + packet.wlan.sa_resolved)
	except:
		print(str(round(time.time())) + " : " + "Exception!")
