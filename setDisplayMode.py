import sqlite3 as sql

rawInput = input("Display pure slideshow? (y-n) ")
if rawInput == "y":
    toWrite = 1
else:
    toWrite = 0
conn = sql.connect("attendance.db")
conn.cursor().execute("UPDATE slideshowSettings SET pureSlideshow=?", (toWrite,))
conn.commit()
