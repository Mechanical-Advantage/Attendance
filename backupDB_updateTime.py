import sqlite3 as sql
import time

conn = sql.connect("attendance.db")
cur = conn.cursor()
cur.execute("UPDATE lastBackup SET timestamp=?", (int(round(time.time())),))
conn.commit()
conn.close()
