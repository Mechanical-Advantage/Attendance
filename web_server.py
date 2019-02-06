import time
import datetime
import cherrypy
import sqlite3 as sql
import math
import plotly as py
import plotly.graph_objs as go
import numpy as np
import psutil
from ics import Calendar, Event

#Config
port = 8000
host = '192.168.1.101'
database = "attendance.db"
signoutTheshold = 15 #in minutes
root = "/home/jaw99/AttendanceTracker/"

def currentTime():
    return(int(round(time.time())))

def orderNames(rawNames):
    names = []
    for i in range(0, len(rawNames)):
        name = rawNames[i][0]
        nameList = name.split(" ")
        if len(nameList) < 2:
            nameList.append("")
        names.append({"first": nameList[0], "last": nameList[1]})
    namesSorted = sorted(names, key=lambda x: (x["last"], x["first"]))
    namesOutput = []
    for i in range(0, len(namesSorted)):
        namesOutput.append(namesSorted[i]["first"] + " " + namesSorted[i]["last"])
    return(namesOutput)

def findWeekday(weekday, next):
    scanTime = currentTime()
    while time.strftime("%A", time.localtime(scanTime)) != weekday:
        if next:
            scanTime += 60*60*24
        else:
            scanTime -= 60*60*24

    return(time.strftime("%Y-%m-%d", time.localtime(scanTime)))

def javascriptDate(date):
    newDate = time.localtime(date)
    year = time.strftime("%Y", newDate)
    month = str(int(time.strftime("%m", newDate)) - 1)
    day_hour_minute = time.strftime("%d, %H, %M", newDate)
    return("new Date(" + year + ", " + month + ", " + day_hour_minute + ")")

def generateIcs(data):
    c = Calendar()
    for row in data:
        e = Event()
        e.name = row[0]
        e.begin = str(row[1])
        if row[2] < 0:
            e.end = currentTime()
        else:
            e.end = str(row[2])
        c.events.add(e)
    with open('web_resources/calendar.ics', 'w') as my_file:
        my_file.writelines(c)

class mainServer(object):
    @cherrypy.expose
    def index(self):
        conn = sql.connect(database)
        cur = conn.cursor()
        output = """
<html><head><title>6328 Attendance</title><style>
iframe {
  border: none;
  width: 100%;
  height: 500px;
}
</style></head><body>

<form method="get" action="/getRecords">
<input type="date" name="startDate" value="$startValue"> to <input type="date" name="endDate" value="$endValue"> for person <select name="person"><option value="*">Everyone</option>$selectionHtml</select>
<button type="submit">Get Records</button>
</form>

<a href="/manual">Manual Sign In/Out</a>

<h3>People Here Now</h3>
 <iframe src="/live" name="liveView"></iframe>

</body></html>
        """

        #Generate name selector
        cur.execute("SELECT DISTINCT name FROM people")
        names = orderNames(cur.fetchall())
        tempSelectionHtml = ""
        for i in range(0, len(names)):
            tempSelectionHtml = tempSelectionHtml + "<option value=\"" + names[i] + "\">" + names[i] + "</option>"
        output = output.replace("$selectionHtml", tempSelectionHtml)

        #Fill in dates from sessions
        if "lastStartDate" in cherrypy.session:
            startValue = cherrypy.session["lastStartDate"]
        else:
            startValue = time.strftime("%Y-%m-%d")
        output = output.replace("$startValue", startValue)
        if "lastEndDate" in cherrypy.session:
            endValue = cherrypy.session["lastEndDate"]
        else:
            endValue = time.strftime("%Y-%m-%d")
        output = output.replace("$endValue", endValue)

        conn.close()
        return(output)

    @cherrypy.expose
    def live(self):
        conn = sql.connect(database)
        cur = conn.cursor()

        output = """
<html><head>
<link rel="stylesheet" type="text/css" href="/mainStyle.css">
<meta http-equiv="refresh" content="60; url=/live" />
</head><body>
<table>$tableHtml</table>
</body></html>
        """

        #Get list of live names
        cur.execute("SELECT name FROM live")
        rows = orderNames(cur.fetchall())

        #Generate table html
        tempTableHtml = "<tr>"
        i = -1
        for row in rows:
            i += 1
            if i % 5 == 0:
                if i != 0:
                    tempTableHtml = tempTableHtml + "</tr><tr>"
            tempTableHtml = tempTableHtml + "<td>" + row + "</td>"
        tempTableHtml = tempTableHtml + "</tr>"
        output = output.replace("$tableHtml", tempTableHtml)

        conn.close()
        return(output)

    @cherrypy.expose
    def getRecords(self, startDate="", endDate="", person="*"):
        conn = sql.connect(database)
        cur = conn.cursor()
        output = """
<html><head><title>6328 Attendance</title><link rel="stylesheet" type="text/css" href="/mainStyle.css">

<script type="text/javascript" src="https://www.gstatic.com/charts/loader.js"></script>
<script type="text/javascript">google.charts.load('current', {'packages':["corechart", "timeline"]});</script>
$timelineScript
$pieScript
$histogramScript

</head><body>

<a href="/">< Return</a><br><br>
$contents

$pieDiv
$histogramDiv
$timelineDiv

</body></html>
        """

        timelineScript = """
<script type="text/javascript">
  google.charts.setOnLoadCallback(drawChart);
  function drawChart() {
    var container = document.getElementById('timeline');
        var chart = new google.visualization.Timeline(container);
        var dataTable = new google.visualization.DataTable();

        dataTable.addColumn({ type: 'string', id: 'Name' });
        dataTable.addColumn({ type: 'string', id: 'Name' });
        dataTable.addColumn({ type: 'date', id: 'Start' });
        dataTable.addColumn({ type: 'date', id: 'End' });
        dataTable.addRows([$timelineData]);

        var options = {
          timeline: { showRowLabels: false }
        };

        chart.draw(dataTable, options);

  }
</script>
        """

        timelineDiv = """<br><div id="timeline" style="height: 100%";></div>"""

        pieScript = """
<script type="text/javascript">
  google.charts.setOnLoadCallback(drawChart);
  function drawChart() {
    var data = google.visualization.arrayToDataTable($pieData);

    var options = {
      title: 'Work Time Distribution',
      pieHole: 0.3,
      chartArea: {left:20,top:40,width:'100%',height:'95%'},
    };

    var chart = new google.visualization.PieChart(document.getElementById('piechart'));
    chart.draw(data, options);
  }
</script>
        """

        pieDiv = """<br><div id="piechart" style="height: 500px; width: 100%;"></div>"""

        histogramScript = """
<script type="text/javascript">
  google.charts.setOnLoadCallback(drawChart);
  function drawChart() {
    var data = google.visualization.arrayToDataTable($histogramData);

    var options = {
      title: 'Lengths of visits',
      legend: { position: 'none' },
      histogram: { bucketSize: 0.5 },
      chartArea: {top:40,width:'90%',height:'80%'},
    };

    var chart = new google.visualization.Histogram(document.getElementById('histogram'));
    chart.draw(data, options);
  }
</script>
        """

        histogramDiv = """<br><div id="histogram" style="height: 500px; width: 100%;"></div>"""

        def getError(error, output):
            conn.close()
            tempOutput = output
            tempOutput = tempOutput.replace("$timelineScript", "")
            tempOutput = tempOutput.replace("$timelineDiv", "")
            tempOutput = tempOutput.replace("$pieScript", "")
            tempOutput = tempOutput.replace("$pieDiv", "")
            tempOutput = tempOutput.replace("$histogramScript", "")
            tempOutput = tempOutput.replace("$histogramDiv", "")
            tempOutput = tempOutput.replace("$contents", error)
            return(tempOutput)

        #Update session data
        cherrypy.session["lastStartDate"] = startDate
        cherrypy.session["lastEndDate"] = endDate

        #Create unix timestamp from input
        try:
            startDate = time.mktime(datetime.datetime.strptime(startDate, "%Y-%m-%d").timetuple()) - (5*60*60)
            endDate = time.mktime(datetime.datetime.strptime(endDate, "%Y-%m-%d").timetuple()) + (19*60*60)
        except:
            return(getError("Please enter a valid start and end date.", output))

        startDate = startDate + time.timezone
        endDate = endDate + time.timezone

        #Check that range is valid
        if endDate<startDate:
            conn.close()
            return(getError("End date is before start date.", output))

        #Get matching records from history
        if person == "*":
            cur.execute("SELECT * FROM history WHERE timeIn>? AND timeIn<? ORDER BY name", (startDate,endDate))
        else:
            cur.execute("SELECT * FROM history WHERE timeIn>? AND timeIn<? AND name=?", (startDate,endDate,person))
        rows = cur.fetchall()

        #Determine if single or multiple days and add appropriate graphs

        #Pie chart -> show if multiple people (any # of days)
        #Histogram -> show if more than one entry (any # of days, single or multiple people)
        #Timeline -> show if single day and multiple people
        if endDate - startDate < (60*60*25):
            singleDay = True
            if person == "*":
                output = output.replace("$timelineScript", timelineScript)
                output = output.replace("$timelineDiv", timelineDiv)
            else:
                output = output.replace("$timelineScript", "")
                output = output.replace("$timelineDiv", "")
        else:
            singleDay = False
            output = output.replace("$timelineScript", "")
            output = output.replace("$timelineDiv", "")
        if person == "*":
            output = output.replace("$pieScript", pieScript)
            output = output.replace("$pieDiv", pieDiv)
        else:
            output = output.replace("$pieScript", "")
            output = output.replace("$pieDiv", "")
        if len(rows) > 1:
            output = output.replace("$histogramScript", histogramScript)
            output = output.replace("$histogramDiv", histogramDiv)
        else:
            output = output.replace("$histogramScript", "")
            output = output.replace("$histogramDiv", "")

        #Generate .ics
        #generateIcs(rows)

        #Generate table contents
        dateFormat = "%a %m/%d - %I:%M %p"
        tempContents = "<table><tr><th>Name</th><th>Time In</th><th>Time Out</th><th>Duration</th>"
        totalDuration = 0
        def formatDuration(duration):
            tempDuration = duration
            hours = math.floor(tempDuration/3600)
            tempDuration -= hours*3600
            minutes = math.floor(tempDuration/60)
            durationFormatted = ""
            if hours > 0:
                durationFormatted = str(hours) + "h "
            durationFormatted = durationFormatted + str(minutes) + "m"
            return(durationFormatted)

        internalPieData = {}
        histogramData = [['Name', 'Hours']]
        for row in rows:
            if row[2] < 0:
                timeOutFormatted = "Still here"
                rawDuration = round(time.time()) - row[1]
            else:
                timeOutFormatted = time.strftime(dateFormat, time.localtime(row[2]))
                rawDuration = row[2] - row[1]
            timeInFormatted = time.strftime(dateFormat, time.localtime(row[1]))

            #Add to total for pie chart
            if row[0] not in internalPieData:
                internalPieData[row[0]] = 0
            internalPieData[row[0]] += rawDuration

            #Record for histogram
            histogramData.append([row[0], rawDuration])

            #Format Duration
            totalDuration += rawDuration
            durationFormatted = formatDuration(rawDuration)
            tempContents = tempContents + "<tr><td>" + row[0] + "</td><td>" + timeInFormatted + "</td><td>" + timeOutFormatted + "</td><td>" + durationFormatted + "</td></tr>"

        tempContents = tempContents + "</table>"

        #Generate title
        titleDateFormat = "%a %m/%d"
        if singleDay:
            tempTitle = "<h3>" + time.strftime(titleDateFormat, time.localtime(startDate)) + " (" + formatDuration(totalDuration) + " total time)</h3>"
        else:
            tempTitle = "<h3>" + time.strftime(titleDateFormat, time.localtime(startDate)) + " to " + time.strftime(titleDateFormat, time.localtime(endDate - 1)) + " (" + formatDuration(totalDuration) + " total time)</h3>"

        #Generate timeline
        if singleDay:
            timelineData = ""
            i = -1
            for row in rows:
                i += 1
                if row[2] < 0:
                    endDate = round(currentTime())
                else:
                    endDate = row[2]
                timelineData = timelineData + "['" + row[0] + "', '" + row[0] + "', " + javascriptDate(row[1]) + ", " + javascriptDate(endDate) + "]"
                if i != len(rows):
                    timelineData = timelineData + ","
            output = output.replace("$timelineData", timelineData)

        #Generate pie chart
        pieData = [['Name', 'Hours']]
        for person, seconds in internalPieData.items():
            pieData.append([person, (seconds/60/60)])
        output = output.replace("$pieData", str(pieData))

        #Generate histogram
        for i in range(1, len(histogramData)):
            histogramData[i][1] = histogramData[i][1]/60/60
        output = output.replace("$histogramData", str(histogramData))

        conn.close()
        return(output.replace("$contents", tempTitle + tempContents))

    @cherrypy.expose
    def manual(self):
        return("""
<html><head><title>6328 Sign In/Out</title><link rel="stylesheet" type="text/css" href="/signin.css"></head><body>
<div class="alert">If you sign in manually, you must sign out manually</div>
<div class="signin">Sign In</div>
<div class="signout">Sign Out</div>

<a href="manual_select?func=signin"><div class="leftlink"></div></a>
<a href="manual_select?func=signout"><div class="rightlink"></div></a>
</body></html>
        """)

    @cherrypy.expose
    def manual_select(self, func="signin"):
        conn = sql.connect(database)
        cur = conn.cursor()
        output = """
<html><head><title>6328 Sign In/Out</title><link rel="stylesheet" type="text/css" href="/signin.css"></head><body>

<div class="title">Please select your name:</div>
<div class="center"><table>$tableHtml</table></div>

</body></html>
        """

        #Get list of names
        cur.execute("SELECT DISTINCT name FROM people ORDER BY name")
        names = orderNames(cur.fetchall())

        #Get people Here
        cur.execute("SELECT name FROM live")
        people = cur.fetchall()
        for i in range(0, len(people)):
            people[i] = people[i][0]

        #Generate table html
        tempTableHtml = "<tr>"
        i = -1
        for row in names:
            if func == "signin":
                display = row not in people
            else:
                display = row in people
            if display:
                i += 1
                if i % 4 == 0:
                    if i != 0:
                        tempTableHtml = tempTableHtml + "</tr><tr>"
                tempTableHtml = tempTableHtml + "<td><a href=\"/manual_internal?name=" + row + "&func=" + func + "\">" + row + "</a></td>"
        tempTableHtml = tempTableHtml + "</tr>"
        output = output.replace("$tableHtml", tempTableHtml)

        conn.close()
        return(output)

    @cherrypy.expose
    def manual_internal(self, name="", func="signin"):
        conn = sql.connect(database)
        cur = conn.cursor()

        #Get time
        time = currentTime()

        #Update database
        if func == "signin":
            cur.execute("INSERT INTO live(name,lastSeen) VALUES (?,?)", (name,time))
            cur.execute("INSERT INTO history(name,timeIn,timeOut) VALUES (?,?,-2)", (name,time))
        elif func == "signout":
            cur.execute("DELETE FROM live WHERE name=?", (name,))
            cur.execute("UPDATE history SET timeOut=? WHERE timeOut<0 AND name=?", (time,name))
            cur.execute("INSERT INTO signedOut(name,timestamp) VALUES (?,?)", (name,time))

        conn.commit()
        conn.close()
        return("""
<html><head><title>6328 Sign In/Out</title><link rel="stylesheet" type="text/css" href="/signin.css"></head><body>

<div class="title">All set!</div>
<meta http-equiv="refresh" content="3; url=/manual" />

</body></html>
        """)

cherrypy.config.update({'server.socket_port': port, 'server.socket_host': host})
cherrypy.quickstart(mainServer(), "/", {"/": {"log.access_file": "", "log.error_file": "", "tools.sessions.on": True, "tools.sessions.timeout": 30}, "/mainStyle.css": {"tools.staticfile.on": True, "tools.staticfile.filename": root + "web_resources/mainStyle.css"}, "/favicon.ico": {"tools.staticfile.on": True, "tools.staticfile.filename": root + "web_resources/favicon.ico"}, "/signin.css": {"tools.staticfile.on": True, "tools.staticfile.filename": root + "web_resources/signin.css"}, "/robotechgp.ttf": {"tools.staticfile.on": True, "tools.staticfile.filename": root + "web_resources/robotechgp.ttf"}, "/Attendance Calendar.ics": {"tools.staticfile.on": True, "tools.staticfile.filename": root + "web_resources/calendar.ics"}})
