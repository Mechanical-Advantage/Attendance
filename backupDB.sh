#!/bin/bash
cd '/home/jaw99/Attendance'
git add attendance.db
echo
message="Updating backup database on "`date '+%m-%d-%Y at %I:%M:%S %p'`
git commit -m "$message"
while [ true ]; do
git push origin master
if [ $? -eq 0 ]; then
exit 0
fi
done
