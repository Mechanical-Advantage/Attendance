#!/bin/bash
ENABLE=true
REPO_PATH='/home/attendance/Attendance'

if [ "$ENABLE" = true ]; then
    cd "$REPO_PATH"
    output=`git pull --ff-only`
    if [ "$output" != "Already up to date." ]; then
        sudo reboot
    fi
fi