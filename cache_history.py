import recordkeeper
import sqlite3 as sql
import time
import math

start_time = round(time.time())
records = recordkeeper.get_range(0, start_time)

conn = sql.connect("/home/attendance/Attendance_data/attendance.db")
cur = conn.cursor()
cur.execute("DELETE FROM history_cache")
for record in records:
    time_in = record["timein"]
    time_out = record["timeout"]
    if time_in == -1:
        time_in = 0
    if time_out == -1:
        time_out = 0
    if time_in == -2:
        time_in = start_time
    if time_out == -2:
        time_out = start_time
    cur.execute("INSERT INTO history_cache(name,time_in,time_out) VALUES (?,?,?)", (record["name"],time_in,time_out))
conn.commit()
conn.close()