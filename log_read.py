#!/usr/bin/python

import time
import sqlite3 as sql

looptime = 60 #in seconds

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
        print("[" + time.ctime(currentTime) + "] Found " + name)
        if name in signedOutLocked:
            print("[" + time.ctime(currentTime) + "] Skipped checking in " + name)
        else:
            cur.execute("SELECT * FROM live WHERE name=?", (name,))
            if len(cur.fetchall()) != 0:
                cur.execute("UPDATE live SET lastSeen=? WHERE name=?", (currentTime,name))
            else:
                print("[" + time.ctime(currentTime) + "] Checked in " + name)
                cur.execute("INSERT INTO live(name,lastSeen) VALUES (?,?)", (name,currentTime))
                cur.execute("INSERT INTO history(name,timeIn,timeOut) VALUES (?,?,-1)", (name,currentTime))

    #Find records above threshold
    cur.execute("SELECT * FROM live WHERE lastSeen<?", (currentTime-threshold*60,))
    checkOutList = cur.fetchall()
    for row in checkOutList:
        name = row[0]
        print("[" + time.ctime(currentTime) + "] Checked out " + name)
        cur.execute("DELETE FROM live WHERE name=?", (name,))
        cur.execute("UPDATE history SET timeOut=? WHERE timeOut=-1 AND name=?", (round(currentTime-((threshold/2)*60)),name))

if __name__ == "__main__":
    while True:
        print("Refreshing...                 ", end="\r")
        conn = sql.connect("attendance.db")
        cur = conn.cursor()
        processData = []
        currentTime = int(round(time.time()))

        #Update last update datetime
        cur.execute("SELECT * FROM lastUpdate")
        lastUpdateData = cur.fetchall()
        lastUpdate = lastUpdateData[0][0]
        cur.execute("UPDATE lastUpdate SET timestamp=?", (currentTime,))

        #Read log file
        with open("/home/jaw99/python/probemon/probemon.log") as f:
            while True:
                try:
                    lineval = f.readline()
                except:
                    x = 0 #Need to have code here to create valid 'except'
                else:
                    if not lineval:
                        break
                    data = lineval.split('\t')
                    try:
                        int(data[0])
                    except:
                        x = 0 #Need to have code here, to create valid 'except'
                    else:
                        if int(data[0]) > lastUpdate:
                            cur.execute("SELECT detail FROM log ORDER BY timestamp DESC LIMIT 1")
                            lastItem = cur.fetchall()
                            save = False
                            if len(lastItem) == 0:
                                save = True
                            if save == False:
                                if lastItem[0][0] != data[1]:
                                    save = True
                            if save:
                                cur.execute("INSERT INTO log(timestamp,function,detail) VALUES (?,?,?)", (int(data[0]), "mac", data[1]))
                            processData.append(["mac", data[1]])

        try:
            refresh(connection=conn, currentTime=currentTime, data=processData)
        except:
            print("[" + time.ctime() + "] WARNING - failed to refresh")
        conn.commit()
        conn.close()

        for i in range(0, looptime):
            print("Time until refresh: " + str(looptime-i) + "s       ", end="\r")
            time.sleep(1)
