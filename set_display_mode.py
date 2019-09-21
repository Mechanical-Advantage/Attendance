import sqlite3 as sql
import sys

if len(sys.argv) > 1:
    toWrite = sys.argv[1]
else:
    rawInput = input("Display pure slideshow? (y-n) ")
    if rawInput == "y":
        toWrite = 1
    else:
        toWrite = 0
    
conn = sql.connect("/home/attendance/Attendance_data/attendance.db")
conn.cursor().execute("UPDATE general SET value=? WHERE key='pure_slideshow'", (toWrite,))
conn.commit()
