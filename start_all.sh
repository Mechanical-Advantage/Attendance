#!/bin/bash
sudo iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 8000
sudo iptables -t nat -I OUTPUT -p tcp -d 127.0.0.1 --dport 80 -j REDIRECT --to-port 8000
exo-open --launch TerminalEmulator 'sudo python3 /home/attendance/Attendance/monitor.py'
exo-open --launch TerminalEmulator 'python3 /home/attendance/Attendance/log_read.py'
exo-open --launch TerminalEmulator 'python3 /home/attendance/Attendance/web_server.py'
firefox -url 'http://127.0.0.1/manual' &
