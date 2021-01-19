import config
import sqlite3 as sql
import threading
import time
from datetime import datetime

time_config = config.recordkeeper_times


def print_visits(visits):
    print(len(visits), "visits")
    for visit in visits:
        print()
        print(visit["name"])
        if visit["timein"] == -1 or visit["timein"] == -2:
            print("Out of range")
        else:
            print(datetime.fromtimestamp(
                visit["timein"]).strftime("%-I:%M %p %a %b %-d"))
        if visit["timeout"] == -1 or visit["timeout"] == -2:
            print("Out of range")
        else:
            print(datetime.fromtimestamp(
                visit["timeout"]).strftime("%-I:%M %p %a %b %-d"))


def get_range(start_time, end_time, filter=[], debug=False, cached=False):
    # Initialization
    log_conn = sql.connect(config.data + "/logs.db")
    log_cur = log_conn.cursor()
    main_conn = sql.connect(config.data + "/attendance.db")
    main_cur = main_conn.cursor()

    # If using cache, get data
    if cached:
        where_query = ""
        if len(filter) != 0:
            where_query = " AND ("
            for name in filter:
                where_query += "name='" + name + "' OR "
            where_query = where_query[:-4] + ")"
        records = main_cur.execute("SELECT * FROM history_cache WHERE ((time_in > ? AND time_in < ?) OR (time_out > ? AND time_out < ?))" +
                                   where_query + " ORDER BY time_in ASC", (start_time, end_time, start_time, end_time)).fetchall()
        log_conn.close()
        main_conn.close()
        return([{"name": x[0], "timein": x[1], "timeout": x[2]} for x in records])

    # Determine start and end times
    results = []
    max_reset = max(time_config["auto_reset"], time_config["manual_reset"])
    scan_start = start_time - (max_reset * 60)
    max_future = max((time_config["auto_reset"] - time_config["auto_extension"]),
                     (time_config["manual_reset"] - time_config["manual_extension"]))
    scan_end = end_time + (max_future * 60)

    def get_id(value):
        id = log_cur.execute(
            "SELECT id FROM lookup WHERE value=?", (value,)).fetchall()
        if len(id) == 0:
            return(-1)
        else:
            return(id[0][0])

    def generate_where_query():
        scan_periods = [{
            "start": scan_start,
            "end": scan_end,
            "ids": []
        }]

        # Get manual sign-in names and generate filter for device retrieval
        name_lookup_filter = ""
        for name in filter:
            id = get_id(name)
            if not id == -1:
                scan_periods[0]["ids"].append(id)
            name_lookup_filter += "name='" + name + "' OR "
        name_lookup_filter = name_lookup_filter[:-4]

        # Get device macs and generate scan periods
        devices = main_cur.execute(
            "SELECT mac, active_start, active_end FROM devices WHERE " + name_lookup_filter).fetchall()
        for device in devices:
            id = get_id(device[0])
            if not id == -1:
                scan_period = {"ids": [id]}

                # Get start time
                if device[1] == None:
                    scan_period["start"] = scan_start
                elif device[1] <= scan_start:
                    scan_period["start"] = scan_start
                elif device[1] <= scan_end:
                    scan_period["start"] = device[1]
                else:
                    continue

                # Get end time
                if device[2] == None:
                    scan_period["end"] = scan_end
                elif device[2] >= scan_end:
                    scan_period["end"] = scan_end
                elif device[2] >= scan_start:
                    scan_period["end"] = device[2]
                else:
                    continue

                # Save scan period
                if scan_period["start"] == scan_start and scan_period["end"] == scan_end:
                    scan_periods[0]["ids"].append(id)
                else:
                    scan_periods.append(scan_period)

        # Check if there are valid scan periods
        if len(scan_periods[0]["ids"]) == 0:
            scan_periods.pop(0)
        if len(scan_periods) == 0:
            return "WHERE 1=0"

        # Generate final where query
        output_periods = []
        for scan_period in scan_periods:
            ids = " OR ".join(["id=" + str(x) for x in scan_period["ids"]])
            output_periods.append("(timestamp >= " + str(scan_period["start"]) + " AND timestamp <= " + str(
                scan_period["end"]) + " AND (" + ids + "))")
        return "WHERE (" + " OR ".join(output_periods) + ")"

    # Get people list if filter empty
    if len(filter) == 0:
        filter = main_cur.execute("SELECT * FROM people").fetchall()
        filter = [x[0] for x in filter]

    # Start timer
    timer_start = time.time()

    # Get id lookup table
    id_lookup_result = log_cur.execute("SELECT * FROM lookup").fetchall()
    id_lookup = {}
    for id, value in id_lookup_result:
        id_lookup[id] = value

    # Get device lookup table
    device_lookup_result = main_cur.execute(
        "SELECT mac,name,active_start,active_end FROM devices").fetchall()
    device_lookup = {}
    for mac, name, active_start, active_end in device_lookup_result:
        if mac not in device_lookup.keys():
            device_lookup[mac] = []
        device_lookup[mac].append({
            "name": name,
            "start": active_start,
            "end": active_end
        })

    # Record time for reading lookup tables
    if debug:
        timer_end = time.time()
        print("Loaded lookup tables in", timer_end - timer_start, "seconds")

    # Get records
    records = log_cur.execute(
        "SELECT * FROM logs " + generate_where_query()).fetchall()

    # Record time to read records
    if debug:
        timer_end = time.time()
        print("Retrieved records in", timer_end - timer_start, "seconds")

    # Sort records
    records.sort(key=lambda x: x[0])

    # Record time to sort records
    if debug:
        timer_end = time.time()
        print("Sorted records in", timer_end - timer_start, "seconds")

    # Process a single record for a given person
    def process_record(record, name):
        # Find last detection
        last_found = False
        last_i = 0
        for i in range(len(results))[::-1]:
            if results[i]["name"] == name:
                last_found = True
                last_i = i
                break

        # If mac and manual signout, check if within grace period
        if record[1] == 0 or record[1] == 3:
            if last_found:
                if results[last_i]["manual_signout"]:
                    if record[0] - results[last_i]["timeout"] <= time_config["manual_grace"] * 60:
                        return

        # Determine if should be joined to previous visit
        extend = False
        if last_found:
            if results[last_i]["manual_signin"]:
                cutoff = time_config["manual_reset"] * 60
            else:
                cutoff = time_config["auto_reset"] * 60
            if record[0] - results[last_i]["timeout"] <= cutoff:
                extend = True

        # Modify existing visit
        if extend:
            if results[last_i]["timeout"] < record[0]:
                results[last_i]["timeout"] = record[0]
            results[last_i]["manual_signout"] = record[1] == 2
            if record[1] == 1:
                results[last_i]["manual_signin"] = True

        # Create new visit
        else:
            if record[1] == 2:
                return
            results.append({"name": name, "timein": record[0], "timeout": record[0],
                            "manual_signin": record[1] == 1, "manual_signout": False})

    # Iterate through records, find name and process
    for record in records:
        # Get name
        if record[1] == 0 or record[1] == 3:  # Device detection

            # Get list of potential names
            try:
                names = device_lookup[id_lookup[record[2]]]
            except:
                continue

            if len(names) == 1:  # Single name (never changed ownership)
                process_record(record, names[0]["name"])
            else:  # Multiple names (changed ownership, find any valid names)
                for name in names:
                    if name["start"] != None:
                        if record[0] < name["start"]:
                            continue
                    if name["end"] != None:
                        if record[0] > name["end"]:
                            continue
                    process_record(record, name["name"])

        else:  # Manual sign in/out
            name = id_lookup[record[2]]
            process_record(record, name)

    # Process final results
    for i in range(len(results))[::-1]:
        # Adjust end time
        if not results[i]["manual_signout"]:
            if results[i]["manual_signin"]:
                results[i]["timeout"] += time_config["manual_extension"] * 60
            else:
                results[i]["timeout"] += time_config["auto_extension"] * 60

        # Remove times not in range
        if results[i]["timein"] < start_time:
            results[i]["timein"] = -1
        if results[i]["timeout"] < start_time:
            results[i]["timeout"] = -1
        if results[i]["timein"] > end_time:
            results[i]["timein"] = -2
        if results[i]["timeout"] > end_time:
            results[i]["timeout"] = -2

        # Remove records not in range
        if (results[i]["timein"] == -1 and results[i]["timeout"] == -1) or (results[i]["timein"] == -2 and results[i]["timeout"] == -2):
            results.pop(i)

    # End timer
    if debug:
        timer_end = time.time()
        print("Finished in", timer_end - timer_start, "seconds")

    # Finish
    log_conn.close()
    main_conn.close()
    return(results)


def get_live(now):
    max_past = max((time_config["auto_live"] - time_config["auto_extension"]),
                   (time_config["manual_live"] - time_config["manual_extension"]))

    # Extra 3 minutes give Slack poster time to detect manual timeouts
    visits = get_range(now - (max_past * 60) - 180, now)
    results = []
    for visit in visits:
        if not visit["name"] in results:
            # manual sign-outs immediately removed from live
            if visit["timeout"] != -2 and visit["manual_signout"]:
                visit["here"] = False
            else:
                if visit["manual_signin"]:
                    cutoff = time_config["manual_live"] - \
                        time_config["manual_extension"]
                else:
                    cutoff = time_config["auto_live"] - \
                        time_config["auto_extension"]
                if visit["timeout"] == -2:
                    compare_time = time.time()
                else:
                    compare_time = visit["timeout"]
                visit["here"] = now - compare_time <= cutoff * 60
            results.append(visit)

    results = sorted(results, key=lambda x: x["name"])

    return(results)


live = []
live_ready = False


def get_livecache():
    return(live)


def get_liveready():
    return(live_ready)


def start_live_server():
    def live_server():
        global live
        global live_ready
        while True:
            live = get_live(time.time())
            live_ready = True
            time.sleep(5)

    server = threading.Thread(target=live_server, daemon=True)
    server.start()


# Testing
if __name__ == "__main__":
    # print_visits(get_range(1562731200, 1562817600, filter=[
    #              "Jonah Bonner"], debug=True, cached=False))
    #print_visits(get_range(1567569600, 1567656000))
    visits = get_range(0, 2000000000, filter=["Jonah Bonner"], debug=True)
    # print(len(visits))
    # print(get_live(1568936984))
