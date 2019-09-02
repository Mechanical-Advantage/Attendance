#!/usr/bin/python

import time
import sqlite3 as sql
print("Authenticating w/ Google...                 ", end="\r")
import google_interface
looptime = 60 #in seconds
logpath = "/home/attendance/Attendance_data/logs/log_read_log.log"
database = "/home/attendance/Attendance_data/attendance.db"

def log(message):
    fullMessage = "[" + time.strftime("%a %m-%d-%Y at %I:%M:%S %p") + "] " + message
    print(fullMessage)
    log = open(logpath, "a")
    log.write(fullMessage + "\n")
    log.close()

def refresh(connection, currentTime, data):
    #Config
    threshold = 40 #in minutes
    signoutTheshold = 15 #how long after manually signing out should a person be able to be signed in? (in minutes)

    #Connect to database
    cur = connection.cursor()

    #Remove items from signout table based on threshold and get list of names
    cur.execute("DELETE FROM signedOut WHERE timestamp<?", (currentTime-(signoutTheshold*60),))

    #Read mac addresses into work table
    cur.execute("DELETE FROM work")
    for i in range(0, len(data)):
        if data[i][0] == "mac":
            cur.execute("INSERT INTO work(mac) VALUES (?)", (data[i][1],))
        elif data[i][0] == "signin":
            cur.execute("INSERT INTO live(name,lastSeen) VALUES (?,?)", (data[1][1],currentTime))
            cur.execute("INSERT INTO history(name,timeIn,timeOut) VALUES (?,?,-2)", (data[1][1],currentTime))
        elif data[1][0] == "signout":
            cur.execute("DELETE FROM live WHERE name=?", (data[1][1],))
            cur.execute("UPDATE history SET timeOut=? WHERE timeOut<0 AND name=?", (currentTime,data[1][1]))
            cur.execute("INSERT INTO signedOut(name,timestamp) VALUES (?,?)", (data[1][1],currentTime))

    #Get list of people signed out
    cur.execute("SELECT name FROM signedOut")
    signedOutLocked = cur.fetchall()
    for i in range(0, len(signedOutLocked)):
        signedOutLocked[i] = signedOutLocked[i][0]

    #Get known records & save to live
    cur.execute("SELECT DISTINCT devices.name FROM devices INNER JOIN work ON devices.mac=work.mac")
    namesFound = cur.fetchall()
    for row in namesFound:
        name = row[0]
        log("Found " + name)
        if name in signedOutLocked:
            log("Skipped checking in " + name + " (signed out recently)")
        else:
            cur.execute("SELECT * FROM live WHERE name=?", (name,))
            if len(cur.fetchall()) != 0:
                cur.execute("UPDATE live SET lastSeen=? WHERE name=?", (currentTime,name))
            else:
                log("Checked in " + name)
                cur.execute("INSERT INTO live(name,lastSeen) VALUES (?,?)", (name,currentTime))
                cur.execute("INSERT INTO history(name,timeIn,timeOut) VALUES (?,?,-1)", (name,currentTime))

    #Find records above threshold
    cur.execute("SELECT * FROM live WHERE lastSeen<?", (currentTime-threshold*60,))
    checkOutList = cur.fetchall()
    for row in checkOutList:
        name = row[0]
        cur.execute("SELECT timeOut FROM history WHERE name=? AND timeOut < 0", (name,))
        status = cur.fetchall()[0][0]
        if status == -2 and (currentTime-row[1]) < 12*60*60:
            log("Skipped checking out " + name + " (signed in manually)")
        else:
            if (currentTime-row[1]) >= 12*60*60:
                log("Checked out " + name + " (not seen for 12 hours)")
            else:
                log("Checked out " + name)
            cur.execute("DELETE FROM live WHERE name=?", (name,))
            cur.execute("UPDATE history SET timeOut=? WHERE timeOut<0 AND name=?", (round(currentTime-((threshold/2)*60)),name))

if __name__ == "__main__":
    while True:
        print("Refreshing...                 ", end="\r")
        try:
            conn = sql.connect(database)
            cur = conn.cursor()
            processData = []
            currentTime = int(round(time.time()))

            #Update last update datetime
            cur.execute("SELECT * FROM lastUpdate")
            lastUpdateData = cur.fetchall()
            lastUpdate = lastUpdateData[0][0]
            cur.execute("UPDATE lastUpdate SET timestamp=?", (currentTime,))

            #Read log file
            i = 0
            with open("/home/attendance/Attendance_data/logs/monitor.log") as f:
                while True:
                    i += 1
                    try:
                        lineval = f.readline()
                    except:
                        x = 0 #Need to have code here to create valid 'except'
                    else:
                        if not lineval:
                            break
                        data = lineval.split(" : ")
                        try:
                            int(data[0])
                        except:
                            x = 0 #Need to have code here, to create valid 'except'
                        else:
                            if int(data[0]) > lastUpdate:
                                processData.append(["mac", data[2][:-1]])
            refresh(connection=conn, currentTime=currentTime, data=processData)
            conn.commit()
            print("Updating spreadsheet...                 ", end="\r")
            google_interface.updateSpreadsheet()
        except:
            log("WARNING - failed to refresh")
        conn.close()

        for i in range(0, looptime):
            print("Time until refresh: " + str(looptime-i) + "s       ", end="\r")
            time.sleep(1)
