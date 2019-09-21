import sqlite3 as sql
import os

#Config
db_path = "logs.db"
probemon_path = "Attendance_data/logs/probemon/"
monitor_path = "Attendance_data/logs/monitor/"
exclude = ["c4:17:fe:af:5d:a5", "00:17:3f:84:7f:bf", "00:20:a6:f6:90:98"]

conn = sql.connect(db_path)
cur = conn.cursor()
cur.execute("DELETE FROM logs")
cur.execute("DELETE FROM lookup")
cur.execute("UPDATE sqlite_sequence SET seq=0 WHERE name='lookup'")

ids = {}
max_id = -1
def process(path, separator, mac_position):
    global max_id
    filelist = os.listdir(path)
    for i in range(len(filelist))[::-1]:
        if filelist[i][:1] == ".":
            filelist.pop(i)

    for filename in filelist:
        print(filename)
        log = open(path + filename, "r")
        try:
            data = log.read().split("\n")
        except:
            x = 0
        else:
            for line in data:
                values = line.split(separator)
                try:
                    timestamp = values[0]
                    mac = values[mac_position]
                except:
                    x = 0
                else:
                    if mac not in exclude:
                        if mac in ids.keys():
                            id = ids[mac]
                        else:
                            max_id += 1
                            ids[mac] = max_id
                            id = max_id
                            cur.execute("INSERT INTO lookup(id,value) VALUES (?,?)", (id,mac))
                        cur.execute("INSERT INTO logs(timestamp,action,id) VALUES (?,0,?)", (timestamp,id))
        conn.commit()

process(probemon_path, "\t", 1)
process(monitor_path, " : ", 2)

conn.commit()
conn.close()
