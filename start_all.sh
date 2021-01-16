#!/bin/bash
#Config
REPO_PATH='/home/attendance/Attendance'
ENABLE_NGROK=true
WEB_PORT='8000'

sudo iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port "$WEB_PORT"
sudo iptables -t nat -I OUTPUT -p tcp -d 127.0.0.1 --dport 80 -j REDIRECT --to-port "$WEB_PORT"
exo-open --launch TerminalEmulator "sudo python3.8 $REPO_PATH/monitor.py"
exo-open --launch TerminalEmulator "python3.8 $REPO_PATH/web_server.py"
firefox -url 'http://127.0.0.1/manual' &
if [ "$ENABLE" = true ]; then
    sleep 30
    exo-open --launch TerminalEmulator "ngrok tcp 22"
fi
