# CONFIGURATION FOR ALL PYTHON SCRIPTS
# Note that configuration for "nightly_refresh.sh" and "start_all.sh" are part of their respective files

# General
repo = "/home/attendance/Attendance"
data = "/home/attendance/Attendance_data"

# Monitor
mon_write_wait = 10 # secs, how long to wait between db writes when monitoring
mon_restart_timeout = 180 # secs, time from last packet at which monitoring interface restarted
mon_restart_checkperiod = 15 # secs, frequency at which to check for restart timeout
mon_nolog = ["00:17:3f:84:7f:bf", "00:20:a6:f6:90:98"] # which macs to skip logging (router, wifi adapters, etc.)
mon_interfaces = {
	"INTERN": {
		"standard": "wlp2s0"
	},
	# "BELKIN": {
	# 	"standard": "wlx00173f847fbf"
	# }
	"PROXIM": {
		"standard": "wlx0020a6f69098"
	}
}

# Analysis
recordkeeper_times = {
    "live_threshold": 30, # minutes, amount of time since last detection before removed from live
    "auto_extension": 10, # minutes, amount of time automatic visits are extended past last detection
    "reset_threshold": 75, # minutes, amount of time since last detection before new visit created
    "manual_grace": 15, # minutes, amount of time after manual signout where automatic signins are blocked
    "manual_timeout": 8 # hours, amount of time after last detection when signed out if manual sign in
}

# Web server
web_host = "0.0.0.0"
web_forced_advised = None # not used for hosting
web_port = 8000
web_socket_port = 8001
enable_slack = False