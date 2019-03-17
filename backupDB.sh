#!/bin/bash
cd '/home/jaw99/Attendance'
python3 backupDB_updateTime.py
git add attendance.db
git add logs
message="Updating backup database on "`date '+%m-%d-%Y at %I:%M:%S %p'`
git commit -m "$message"
echo
while [ true ]; do
git push origin master
if [ $? -eq 0 ]; then
exit 0
fi
done
