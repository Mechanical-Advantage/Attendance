import sqlite3 as sql
import time
import json
from datetime import datetime

#Config
log_db = "logs.db"
main_db = "/Users/jonah/Documents/Attendance_test/Attendance_data/attendance.db"
time_config = {
    "live_threshold": 40, #minutes, amount of time since last detection before removed from live
    "auto_extension": 15, #minutes, amount of time automatic visits are extended past last detection
    "reset_threshold": 75, #minutes, amount of time since last detection before new visit created
    "manual_grace": 15, #minutes, amount of time after manual signout where automatic signins are blocked
    "manual_timeout": 8 #hours, amount of time after last detection when signed out if manual sign in
}

def print_visits(visits):
    print(len(visits), "visits")
    for visit in visits:
        print()
        print(visit["name"])
        if visit["timein"] == -1 or visit["timein"] == -2:
            print("Out of range")
        else:
            print(datetime.fromtimestamp(visit["timein"]).strftime("%-I:%M %p %a %b %-d"))
        if visit["timeout"] == -1 or visit["timeout"] == -2:
            print("Out of range")
        else:
            print(datetime.fromtimestamp(visit["timeout"]).strftime("%-I:%M %p %a %b %-d"))

def get_range(start_time, end_time, filter=[], debug=False):
    #Initialization
    log_conn = sql.connect(log_db)
    log_cur = log_conn.cursor()
    main_conn = sql.connect(main_db)
    main_cur = main_conn.cursor()
    
    results = []
    scan_start = start_time - (time_config["manual_timeout"] * 3600)
    scan_end = end_time + (time_config["reset_threshold"] * 60)
    
    def get_id(value):
        id = log_cur.execute("SELECT id FROM lookup WHERE value=?", (value,)).fetchall()
        if len(id) == 0:
            return(-1)
        else:
            return(id[0][0])

    def generate_where_query():
        output = "WHERE timestamp>=" + str(scan_start) + " AND timestamp<=" + str(scan_end)
        name_filter = ""
        name_lookup_filter = ""
        for name in filter:
            id = get_id(name)
            if not id == -1:
                name_filter += "id=" + str(id) + " OR "
            name_lookup_filter += "name='" + name + "' OR "
        name_filter = name_filter[:-4]
        name_lookup_filter = name_lookup_filter[:-4]
        
        devices = main_cur.execute("SELECT mac FROM devices WHERE " + name_lookup_filter).fetchall()
        devices = [x[0] for x in devices]
        device_filter = ""
        for mac in devices:
            id = get_id(mac)
            if not id == -1:
                device_filter += "id=" + str(id) + " OR "
        device_filter = device_filter[:-4]

        if name_filter != "" or device_filter != "":
            output += " AND ("
        output += name_filter
        if name_filter != "" and device_filter != "":
            output += " OR "
        output += device_filter
        if name_filter != "" or device_filter != "":
            output += ")"
        return(output)

    #Get people list if filter empty
    if len(filter) == 0:
        filter = main_cur.execute("SELECT * FROM people").fetchall()
        filter = [x[0] for x in filter]

    #Start timer
    timer_start = time.time()

    #Get id lookup table
    id_lookup_result = log_cur.execute("SELECT * FROM lookup").fetchall()
    id_lookup = {}
    for id, value in id_lookup_result:
        id_lookup[id] = value

    #Get device lookup table
    device_lookup_result = main_cur.execute("SELECT mac,name FROM devices").fetchall()
    device_lookup = {}
    for mac, name in device_lookup_result:
        device_lookup[mac] = name

    #Record time for reading lookup tables
    if debug:
        timer_end = time.time()
        print("Loaded lookup tables in", timer_end - timer_start, "seconds")

    #Get records
    records = log_cur.execute("SELECT * FROM logs " + generate_where_query() + " ORDER BY timestamp ASC").fetchall()

    #Record time to read records
    if debug:
        timer_end = time.time()
        print("Retrieved records in", timer_end - timer_start, "seconds")

    for record in records:
        #Get name
        if record[1] == 0:
            try:
                name = device_lookup[id_lookup[record[2]]]
            except:
                continue
        else:
            name = id_lookup[record[2]]

        #Find last detection
        last_found = False
        last_i = 0
        for i in range(len(results))[::-1]:
            if results[i]["name"] == name:
                last_found = True
                last_i = i
                break
                    
        #If mac and manual signout, check if within grace period
        if record[1] == 0:
            if last_found:
                if results[last_i]["manual_signout"]:
                    if record[0] - results[last_i]["timeout"] <= time_config["manual_grace"] * 60:
                        continue

        #Determine if should be joined to previous visit
        extend = False
        if last_found:
            if results[last_i]["manual_signin"]:
                cutoff = time_config["manual_timeout"] * 3600
            else:
                cutoff = time_config["reset_threshold"] * 60
            if record[0] - results[last_i]["timeout"] <= cutoff:
                extend = True

        #Modify existing visit
        if extend:
            if results[last_i]["timeout"] < record[0]:
                results[last_i]["timeout"] = record[0]
            results[last_i]["manual_signout"] = record[1] == "signout"
            if record[1] == 1:
                results[last_i]["manual_signin"] = true
                    
        #Create new visit
        else:
            if record[1] == 2:
                continue
            results.append({"name": name, "timein": record[0], "timeout": record[0], "manual_signin": record[1] == "signin", "manual_signout": False})

    #Process results
    for i in range(len(results))[::-1]:
        #Adjust end time
        if not results[i]["manual_signout"]:
            if results[i]["manual_signin"]:
                results[i]["timeout"] += time_config["manual_timeout"] * 3600
            else:
                results[i]["timeout"] += time_config["auto_extension"] * 60

        #Remove times not in range
        if results[i]["timein"] < start_time:
            results[i]["timein"] = -1
        if results[i]["timeout"] < start_time:
            results[i]["timeout"] = -1
        if results[i]["timein"] > end_time:
            results[i]["timein"] = -2
        if results[i]["timeout"] > end_time:
            results[i]["timeout"] = -2
        
        #Remove records not in range
        if (results[i]["timein"] == -1 and results[i]["timeout"] == -1) or (results[i]["timein"] == -2 and results[i]["timeout"] == -2):
            results.pop(i)

    #End timer
    if debug:
        timer_end = time.time()
        print("Finished in", timer_end - timer_start, "seconds")
    
    #Finish
    log_conn.close()
    main_conn.close()
    return(results)

def get_live(now):
    visits = get_range(now - ((time_config["live_threshold"] - time_config["auto_extension"]) * 60), now)
    results = []
    for visit in visits:
        if not visit["name"] in results and ((not visit["manual_signout"]) or visit["timeout"] == -2):
            results.append(visit["name"])
    results.sort()
    return(results)

#Testing
if __name__ == "__main__":
    #print_visits(get_range(1562731200, 1562817600))
    #print_visits(get_range(1567569600, 1567656000))
    print_visits(get_range(0, 2000000000, debug=True))
    #print(get_live(1568936984))
