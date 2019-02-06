#!/usr/bin/python

import time
import sqlite3 as sql

#Config
threshold = 40 #in minutes
signoutTheshold = 15 #how long after manually signing out should a person be able to be signed in? (in minutes)
looptime = 1 #in minutes

def refresh():
    #Get time
    currentTime = int(round(time.time()))

    #Connect to database
    conn = sql.connect("attendance.db")
    cur = conn.cursor()

    #Update last update datetime
    cur.execute("SELECT * FROM lastUpdate")
    lastUpdateData = cur.fetchall()
    lastUpdate = lastUpdateData[0][0]
    cur.execute("UPDATE lastUpdate SET timestamp=?", (currentTime,))

    #Remove items from signout table based on threshold and get list of names
    cur.execute("DELETE FROM signedOut WHERE timestamp<?", (currentTime-(signoutTheshold*60),))
    conn.commit()
    cur.execute("SELECT name FROM signedOut")
    signedOutLocked = cur.fetchall()
    for i in range(0, len(signedOutLocked)):
        signedOutLocked[i] = signedOutLocked[i][0]

    #Read mac addresses into work table
    cur.execute("DELETE FROM work")
    count = 0
    with open("/home/jaw99/python/probemon/probemon.log") as f:
        while True:
            try:
                lineval = f.readline()
            except:
                print("WARNING - found unknown characters in log")
            else:
                if not lineval:
                    break
                data = lineval.split('\t')
                if int(data[0]) > lastUpdate:
                    count += 1
                    cur.execute("INSERT INTO work(mac) VALUES (?)", (data[1],))
    conn.commit()

    #Get known records & save to live
    cur.execute("SELECT DISTINCT people.name FROM people INNER JOIN work ON people.mac=work.mac")
    namesFound = cur.fetchall()
    for row in namesFound:
        name = row[0]
        print("Found " + name)
        if name in signedOutLocked:
            print("Skipped checking in " + name)
        else:
            cur.execute("SELECT * FROM live WHERE name=?", (name,))
            if len(cur.fetchall()) != 0:
                cur.execute("UPDATE live SET lastSeen=? WHERE name=?", (currentTime,name))
            else:
                print("Checked in " + name)
                cur.execute("INSERT INTO live(name,lastSeen) VALUES (?,?)", (name,currentTime))
                cur.execute("INSERT INTO history(name,timeIn,timeOut) VALUES (?,?,-1)", (name,currentTime))
    conn.commit()

    #Find records above threshold
    cur.execute("SELECT * FROM live WHERE lastSeen<?", (currentTime-threshold*60,))
    checkOutList = cur.fetchall()
    for row in checkOutList:
        name = row[0]
        print("Checked out " + name)
        cur.execute("DELETE FROM live WHERE name=?", (name,))
        cur.execute("UPDATE history SET timeOut=? WHERE timeOut=-1 AND name=?", (round(currentTime-((threshold/2)*60)),name))
    conn.commit()
    conn.close()

while True:
    time.sleep(looptime*60)
    refresh()
    print("Refreshed at " + time.ctime())
