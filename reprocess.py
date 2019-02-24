import log_read
import time
import sqlite3 as sql
import math

conn = sql.connect("attendance.db")
cur = conn.cursor()

#Get start and end times
startTime = int(input("What is the start time? "))
cur.execute("SELECT timestamp FROM log ORDER BY timestamp LIMIT 1")
if startTime < cur.fetchall()[0][0]:
    print("Your specified start date is before data started being logged. Proceeding will result in data loss.")
    answer = input("Continue? (y-n) ")
    if answer != "y":
        exit()

answer = input("Reprocess data from " + time.ctime(startTime) + "? (y-n) ")
if answer != "y":
    exit()

cur.execute("SELECT timestamp FROM log ORDER BY timestamp DESC LIMIT 1")
endTime = cur.fetchall()[0][0]

#Find number of minutes
minutes = math.ceil((endTime-startTime)/60)

#Reset database
cur.execute("DELETE FROM history WHERE timeIn<?", (startTime,))
cur.execute("DELETE FROM live")
cur.execute("DELETE FROM signedOut")

#Process data
for currentMinutes in range(0, minutes + 1):
    minuteStart = startTime + (currentMinutes*60)
    minuteEnd = startTime + ((currentMinutes+1)*60)
    print("[" + time.ctime(minuteEnd) + "]", end="\r")
    cur.execute("SELECT function,detail FROM log WHERE timestamp>? AND timestamp<?", (minuteStart,minuteEnd))
    log_read.refresh(connection=conn, currentTime=minuteEnd, data=cur.fetchall())
conn.commit()
conn.close()
