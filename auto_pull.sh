#!/bin/bash
ENABLE=true
REPO_PATH='/home/attendance/Attendance'
DATA_PATH='/home/attendance/Attendance_data'

log () {
    echo [`date`] "$1" >> "$DATA_PATH/logs/refreshlog.log"
}

if [ "$ENABLE" = true ]; then
    log 'Checking for updates from GitHub'
    cd "$REPO_PATH"
    output=`git pull --ff-only`
    if [ "$output" == "Already up to date." ]; then
        log 'No updates to repository'
    else
        log 'Found updates, rebooting'
        sudo reboot
    fi
else
    log 'Auto pull disabled, skipping'
fi