# CONFIGURATION FOR ALL PYTHON SCRIPTS
# Note that configuration for "nightly_refresh.sh" and "start_all.sh" are part of their respective files

# General
repo = "/home/attendance/Attendance"
data = "/home/attendance/Attendance_data"
admin_title = "6328 Attendance"
signin_title = "6328 Sign In/Out"

# Monitor
mon_write_wait = 10 # secs, how long to wait between db writes when monitoring
mon_nolog = ["00:17:3f:84:7f:bf", "78:92:9c:fd:17:d1"] # which macs to skip logging (router, wifi adapters, etc.)
mon_interfaces = {
	"INTERN": {
		"standard": "wlp2s0"
	},
	"BELKIN": {
		"standard": "wlx00173f847fbf"
	},
	"PROXIM": {
		"standard": "wlx0020a6f69098"
	}
}

# Analysis
recordkeeper_times = { # in minutes
	"auto_extension": 10, # amount of time automatic visits are extended past last detection
	"auto_live": 30, # amount of time since last detection before removed from live
	"auto_reset": 240, # amount of time since last detection before new visit created
	"manual_grace": 15, # amount of time after manual signout where automatic signins are blocked
	"manual_extension": 180, # amount of time manual visits are extended past sign in
	"manual_live": 480, # amount of time since sign in before removed from live (except for manual sign-outs)
	"manual_reset": 480 # amount of time since sign in where new visit created
}

# Web server
web_host = "0.0.0.0"
web_forced_advised = None # not used for hosting
web_port = 8000
web_socket_port = 8001
enable_slack = True
