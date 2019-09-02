import time
import datetime
import cherrypy
import slack
import sqlite3 as sql
import math
import subprocess
import inflect
import os
from random import shuffle

#Config
port = 8000
host = '0.0.0.0'
database = "attendance.db"
root_main = "/home/attendance/Attendance/"
root_data = "/home/attendance/Attendance_data/"

#Setup
database = root_data + database
languageManager = inflect.engine()

def currentTime():
    return(int(round(time.time())))

def formatDuration(duration, showSeconds):
    tempDuration = duration
    hours = math.floor(tempDuration/3600)
    tempDuration -= hours*3600
    minutes = math.floor(tempDuration/60)
    seconds = tempDuration - minutes*60
    durationFormatted = ""
    if hours > 0:
        durationFormatted = str(hours) + "h "
    if minutes > 0:
        durationFormatted = durationFormatted + str(minutes) + "m "
    if showSeconds:
        durationFormatted = durationFormatted + str(seconds) + "s "
    return(durationFormatted[:-1])

def orderNames(rawNames, byFirst=False):
    names = []
    for i in range(0, len(rawNames)):
        name = rawNames[i][0]
        nameList = name.split(" ")
        if len(nameList) < 2:
            nameList.append("")
        names.append({"first": nameList[0], "last": nameList[1]})
    if byFirst:
        namesSorted = sorted(names, key=lambda x: (x["first"], x["last"]))
    else:
        namesSorted = sorted(names, key=lambda x: (x["last"], x["first"]))
    namesOutput = []
    for i in range(0, len(namesSorted)):
        if namesSorted[i]["last"] == "":
            namesOutput.append(namesSorted[i]["first"])
        else:
            namesOutput.append(namesSorted[i]["first"] + " " + namesSorted[i]["last"])
    return(namesOutput)

def javascriptDate(date, noTime=False):
    newDate = time.localtime(date)
    year = time.strftime("%Y", newDate)
    month = str(int(time.strftime("%m", newDate)) - 1)
    if noTime:
        day_hour_minute = time.strftime("%d", newDate)
    else:
        day_hour_minute = time.strftime("%d, %H, %M", newDate)
    return("new Date(" + year + ", " + month + ", " + day_hour_minute + ")")

def title(display):
    uppers = {}
    for f in range(0, len(display)):
        if display[f].isupper():
            uppers[f] = display[f]
    display = list(display.title())
    for f, letter in uppers.items():
        display[f] = letter
    display = "".join(display)
    return(display)

def formatList(inputList, separator):
    output = ""
    for i in range(0, len(inputList)):
        output = output + inputList[i]
        if i != len(inputList) - 1:
            if len(inputList) == 2:
                output = output + " "
            else:
                output = output + ", "
        if i == len(inputList) - 2:
            output = output + separator + " "
    return(output)

class mainServer(object):
    @cherrypy.expose
    def index(self):
        conn = sql.connect(database)
        cur = conn.cursor()
        output = """
<html><head><title>6328 Attendance</title><link rel="stylesheet" type="text/css" href="/static/css/admin.css"><style>
iframe {
  border: none;
  width: 100%;
  height: 500px;
}
</style>
<script src="/static/js/lastUpdate.js"></script>
</head><body>

<form method="get" action="/getRecords">
<input type="date" name="startDate" value="$startValue"> to <input type="date" name="endDate" value="$endValue"> for person <select name="filter"><option value="*">Everyone</option>$selectionHtml</select>
<button type="submit">Get Records</button>
</form>

<a href="/advanced">Advanced Get Records</a><br><br>
<a href="/manual">Manual Sign In/Out</a><br><br>
<a href="/peoplelist">Manage People</a>

<br><p id="lastUpdate" style="font-style: italic;"></p>

<h3>People Here Now</h3>
<iframe id="liveView" src="/live/homepage" name="liveView"></iframe>

<script>
window.setInterval("reloadLastUpdate();", 1000);
reloadLastUpdate();
window.setInterval("reloadLive();", 60000);
function reloadLive() {
 document.getElementById("liveView").src="/live/homepage";
}
</script>
</body></html>
        """

        #Generate name selector
        cur.execute("SELECT name FROM people")
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
    def advanced(self):
        conn = sql.connect(database)
        cur = conn.cursor()
        output = """
<html><head><title>6328 Attendance</title><link rel="stylesheet" type="text/css" href="/static/css/admin.css">
<script>

function refresh() {
const names = $namelist;

var text = "";
var nameCount = names.length;
for (var i = 0; i < nameCount; i++) {

var checkName = "check" + i.toString();
if (document.getElementById(checkName).checked == true){
text = text + names[i] + ",";
}
}

text = text.slice(0, -1);
document.getElementById("output").value = text;
}


function setChecks(value) {
const names = $namelist;
var nameCount = names.length;
for (var i = 0; i < nameCount; i++) {

var checkName = "check" + i.toString();
document.getElementById(checkName).checked = value;
}
refresh();
}

</script>
</head><body>
<a href="/">< Return</a><br><br>
<form id="mainForm" method="get" action="/getRecords">
Start date: <input type="date" name="startDate" value="$startValue"><br>
End date: <input type="date" name="endDate" value="$endValue">
</form>
<button onclick="setChecks(true);">Check All</button><button onclick="setChecks(false);">Uncheck All</button><br><br>

$checkHtml

<input form="mainForm" type="hidden" name="filter" id="output">
<input form="mainForm" type="hidden" name="fromAdvanced" value="1">
<button form="mainForm" type="submit">Get Records</button>

</body></html>
        """
        #Get list of categories
        cur.execute("SELECT * FROM possibleCategories")
        names = cur.fetchall()
        cleanNames = []
        for i in range(0, len(names)):
            cleanNames.append(names[i][0])
            names[i] = languageManager.plural(names[i][0])

        #Get list of people
        cur.execute("SELECT name FROM people")
        peoplelist = orderNames(cur.fetchall())
        names.extend(peoplelist)
        cleanNames.extend(peoplelist)

        #Add names to javascript
        output = output.replace("$namelist", str(cleanNames).replace("'", '"'))

        #Add names to html
        checkHtml = ""
        for i in range(0, len(names)):
            display = title(names[i])
            checkHtml = checkHtml + '<label class="check"><input type="checkbox" class="check" onclick="refresh()" id="check' + str(i) + '"> ' + display + '</label><br>'
        output = output.replace("$checkHtml", checkHtml)

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
    def live(self, version="homepage"):
        conn = sql.connect(database)
        cur = conn.cursor()

        output = """
<html><head>
<link rel="stylesheet" type="text/css" href="/static/css/admin.css">
<style>
$versioncss
</style>
</head><body>
<div class="center"><table class="names">$tableHtml</table><div>
</body></html>
        """
        if version == "signin":
            output = output.replace("$versioncss", """
div.center {
position: absolute;
left: 50%;
transform: translate(-50%, 0);
}

@font-face {
	font-family: "Robotech GP";
	src: url("/static/fonts/robotechgp.ttf");
}

td {
font-family: "Robotech GP";
font-size: 20px;
}
            """)
        else:
            output = output.replace("$versioncss", """
div.center {
position: absolute;
top: 0px;
left: 0px;
}
            """)

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
            tempTableHtml = tempTableHtml + "<td class=\"names\">" + row + "</td>"
        tempTableHtml = tempTableHtml + "</tr>"
        output = output.replace("$tableHtml", tempTableHtml)

        conn.close()
        return(output)

    @cherrypy.expose
    def lastUpdate(self):
        conn = sql.connect(database)
        cur = conn.cursor()
        cur.execute("SELECT * FROM lastUpdate")
        time = str(cur.fetchall()[0][0])
        conn.close()
        return(time)

    @cherrypy.expose
    def getRecords(self, startDate="", endDate="", filter="*", fromAdvanced="0"):
        conn = sql.connect(database)
        cur = conn.cursor()
        output = """
<html><head><title>6328 Attendance</title><link rel="stylesheet" type="text/css" href="/static/css/admin.css">

<script type="text/javascript" src="https://www.gstatic.com/charts/loader.js"></script>
<script type="text/javascript">google.charts.load('current', {'packages':["corechart", "timeline", "calendar"]});</script>
$pieScript
$catPieScript
$histogramScript
$calendarScript
$timelineScript

<script type="text/javascript">

function showAll() {
var element = document.getElementById("extraRowStyle");
element.parentNode.removeChild(element)

var element = document.getElementById("showAllLink");
element.parentNode.removeChild(element)
}
</script>
<style id="extraRowStyle">
tr.extraRow {
display: none;
}
</style>

</head><body>

<a href="$returnLink">< Return</a><br><br>
$contents

$pieDiv
$catPieDiv
$histogramDiv
$calendarDiv
$timelineDiv

</body></html>
        """

        pieScript = """
<script type="text/javascript">
  google.charts.setOnLoadCallback(drawChart);
  function drawChart() {
    var data = google.visualization.arrayToDataTable($pieData);

    var options = {
      title: 'Work Time Distribution (by person)',
      pieHole: 0.3,
      chartArea: {left:20,top:40,width:'100%',height:'95%'},
    };

    var chart = new google.visualization.PieChart(document.getElementById('piechart'));
    chart.draw(data, options);
  }
</script>
        """

        pieDiv = """<br><div id="piechart" style="height: 500px; width: 100%;"></div>"""

        catPieScript = """
<script type="text/javascript">
  google.charts.setOnLoadCallback(drawChart);
  function drawChart() {
    var data = google.visualization.arrayToDataTable($catPieData);

    var options = {
      title: 'Work Time Distribution (by category)',
      pieHole: 0.3,
      chartArea: {left:20,top:40,width:'100%',height:'95%'},
    };

    var chart = new google.visualization.PieChart(document.getElementById('catpiechart'));
    chart.draw(data, options);
  }
</script>
        """

        catPieDiv = """<br><div id="catpiechart" style="height: 500px; width: 100%;"></div>"""

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

        calendarScript = """
<script type="text/javascript">
  google.charts.setOnLoadCallback(drawChart);
  function drawChart() {
    var data = new google.visualization.DataTable();
    data.addColumn({ type: 'date', id: 'Date' });
    data.addColumn({ type: 'number', id: 'Hours' });
    data.addRows($calendarData);

    var options = {
      title: "Hours By Day"
    };

    var chart = new google.visualization.Calendar(document.getElementById('calendar'));
    chart.draw(data, options);
  }
</script>
        """

        calendarDiv = """<br><div id="calendar" style="height: 500px; width: 100%;"></div>"""

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
          timeline: { showRowLabels: false },
          hAxis: { format: 'h:mmaa' }
        };

        chart.draw(dataTable, options);

  }
</script>
        """

        timelineDiv = """<br><div id="timeline" style="height: 100%;"></div>"""

        def getError(error, output):
            conn.close()
            tempOutput = output
            tempOutput = tempOutput.replace("$timelineScript", "")
            tempOutput = tempOutput.replace("$timelineDiv", "")
            tempOutput = tempOutput.replace("$pieScript", "")
            tempOutput = tempOutput.replace("$pieDiv", "")
            tempOutput = tempOutput.replace("$catPieScript", "")
            tempOutput = tempOutput.replace("$catPieDiv", "")
            tempOutput = tempOutput.replace("$calendarScript", "")
            tempOutput = tempOutput.replace("$calendarDiv", "")
            tempOutput = tempOutput.replace("$histogramScript", "")
            tempOutput = tempOutput.replace("$histogramDiv", "")
            tempOutput = tempOutput.replace("$contents", error)
            tempOutput = tempOutput.replace("$returnLink", "/")
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

        #Create list of names
        if filter == "*":
            cur.execute("SELECT * FROM people")
            names = orderNames(cur.fetchall())
        else:
            names = []

            #Get categories
            cur.execute("SELECT * FROM possibleCategories")
            categories = cur.fetchall()
            for i in range(0, len(categories)):
                categories[i] = categories[i][0]

            #Iterate through input (if category, add names from category. if name, add to list)
            inputList = filter.split(",")
            for i in range(0, len(inputList)):
                if inputList[i] in categories:
                    cur.execute("SELECT name FROM categories WHERE category=?", (inputList[i],))
                    namesInCat = cur.fetchall()
                    for f in range(0, len(namesInCat)):
                        if namesInCat[f][0] not in names:
                            names.append(namesInCat[f][0])
                else:
                    if inputList[i] not in names:
                        names.append(inputList[i])

        #Get matching records from history
        cur.execute("SELECT * FROM history WHERE timeIn>? AND timeIn<?", (startDate,endDate))
        rowsTemp = cur.fetchall()
        rows = []
        for i in range(0, len(rowsTemp)):
            if rowsTemp[i][0] in names:
                rows.append(rowsTemp[i])
        rows = sorted(rows, key=lambda x: (x[0], x[1]))

        #Determine if single or multiple days and add appropriate graphs

        #Pie chart -> multple people, any # of days
        #Histogram -> any # of poeple, any # of days, more than one entry
        #Calendar -> any # of people, multiple days
        #Timeline -> multiple people, single day
        if len(names) > 1:
            gen_pieChart = True
            output = output.replace("$pieScript", pieScript)
            output = output.replace("$pieDiv", pieDiv)
            output = output.replace("$catPieScript", catPieScript)
            output = output.replace("$catPieDiv", catPieDiv)
        else:
            gen_pieChart = False
            output = output.replace("$pieScript", "")
            output = output.replace("$pieDiv", "")
            output = output.replace("$catPieScript", "")
            output = output.replace("$catPieDiv", "")

        if len(rows) > 1:
            gen_histogram = True
            output = output.replace("$histogramScript", histogramScript)
            output = output.replace("$histogramDiv", histogramDiv)
        else:
            gen_histogram = False
            output = output.replace("$histogramScript", "")
            output = output.replace("$histogramDiv", "")

        if endDate - startDate <= (60*60*25):
            singleDay = True
            output = output.replace("$calendarScript", "")
            output = output.replace("$calendarDiv", "")
        else:
            singleDay = False
            output = output.replace("$calendarScript", calendarScript)
            output = output.replace("$calendarDiv", calendarDiv)

        if endDate - startDate <= (60*60*25*4):
            if len(names) > 1:
                gen_timeline = True
                output = output.replace("$timelineScript", timelineScript)
                output = output.replace("$timelineDiv", timelineDiv)
            else:
                gen_timeline = False
                output = output.replace("$timelineScript", "")
                output = output.replace("$timelineDiv", "")
        else:
            gen_timeline = False
            output = output.replace("$timelineScript", "")
            output = output.replace("$timelineDiv", "")

        #Generate table contents
        dateFormat = "%a %m/%d - %I:%M %p"
        tempContents = "<table><tr><th>Name</th><th>Time In</th><th>Time Out</th><th>Duration</th>"
        totalDuration = 0

        internalPieData = {}
        histogramData = [['Name', 'Hours']]
        rowid = 0
        extraRowCount = 0
        for row in rows:
            rowid += 1
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
            durationFormatted = formatDuration(rawDuration, showSeconds=False)

            #Get class
            if rowid > 25:
                rowclass = ' class="extraRow"'
                extraRowCount += 1
            else:
                rowclass = ""

            tempContents = tempContents + '<tr' + rowclass + '><td><a class="hidden" href="/person/' + row[0] + '">' + row[0] + "</a></td><td>" + timeInFormatted + "</td><td>" + timeOutFormatted + "</td><td>" + durationFormatted + "</td></tr>"

        tempContents = tempContents + "</table>"
        if extraRowCount > 0:
            if extraRowCount == 1:
                rowname = "Row"
            else:
                rowname = "Rows"
            tempContents = tempContents + '<div id="showAllLink"><br><a href="javascript:showAll()">Show ' + str(extraRowCount) + ' More ' + rowname + '</a></div>'

        #Generate title
        titleDateFormat = "%a %m/%d"
        if singleDay:
            tempTitle = "<h3>" + time.strftime(titleDateFormat, time.localtime(startDate)) + " (" + formatDuration(totalDuration, showSeconds=False) + " total time)</h3>"
        else:
            tempTitle = "<h3>" + time.strftime(titleDateFormat, time.localtime(startDate)) + " to " + time.strftime(titleDateFormat, time.localtime(endDate - 1)) + " (" + formatDuration(totalDuration, showSeconds=False) + " total time)</h3>"

        #Generate pie chart
        if gen_pieChart:
            pieData = [['Name', 'Hours']]
            for person, seconds in internalPieData.items():
                pieData.append([person, (seconds/60/60)])
            output = output.replace("$pieData", str(pieData))

            #Generate category pie chart
            categoryPieData = {}
            for person, seconds in internalPieData.items():
                cur.execute("SELECT category FROM categories WHERE name=? ORDER BY category", (person,))
                categories = cur.fetchall()
                for i in range(0, len(categories)):
                    categories[i] = title(languageManager.plural(categories[i][0]))
                if len(categories) == 0:
                    categoriesString = "Unclassified"
                else:
                    categoriesString = formatList(categories, "and")

                if categoriesString in categoryPieData:
                    categoryPieData[categoriesString] += seconds
                else:
                    categoryPieData[categoriesString] = seconds

            pieData = [['Category', 'Hours']]
            for category, seconds in categoryPieData.items():
                pieData.append([category, (seconds/60/60)])
            output = output.replace("$catPieData", str(pieData))

        #Generate histogram
        if gen_histogram:
            for i in range(1, len(histogramData)):
                histogramData[i][1] = histogramData[i][1]/60/60
            output = output.replace("$histogramData", str(histogramData))

        #Generate calendar (create totals)
        if singleDay == False:
            tempCalendarData = {}
            for row in rows:
                if row[2] < 0:
                    rawDuration = round(time.time()) - row[1]
                else:
                    rawDuration = row[2] - row[1]

                date = javascriptDate(row[1], noTime=True)
                if date in tempCalendarData:
                    tempCalendarData[date] += rawDuration
                else:
                    tempCalendarData[date] = rawDuration

            #Generate calendar (format data)
            calendarData = "["
            for date, seconds in tempCalendarData.items():
                calendarData = calendarData + "[" + date + ", " + str(round(seconds/60/60)) + "]"
                calendarData = calendarData + ","
            calendarData = calendarData[:-1] + "]"
            output = output.replace("$calendarData", calendarData)

        #Generate timeline
        if gen_timeline:
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

        #Add return link
        if fromAdvanced == "1":
            output = output.replace("$returnLink", "/advanced")
        else:
            output = output.replace("$returnLink", "/")

        conn.close()
        return(output.replace("$contents", tempTitle + tempContents))

    @cherrypy.expose
    def manual(self):
        output = """
<html><head><title>6328 Sign In/Out</title><link rel="stylesheet" type="text/css" href="/static/css/manual.css">
<script>
window.setInterval("updateDisplayType();", 5000);
window.setInterval("reloadIFrame();", 60000);
function reloadIFrame() {
 document.getElementById("liveView").src="/live/signin";
}
</script>

</head><body>

<div class="slideshow slideshow1" style="opacity: 0.7;"></div>
<div class="slideshow slideshow2" style="opacity: 0;"></div>

<div class="aboveSlideshow">
<div class="title">People Here Now:</div>
<div style="position: absolute; top: 60px; left: 50%; transform: translate(-50%, 0); width: 100%;"><iframe id="liveView" src="/live/signin" style="border: none; width: 100%; height: 300px;"></iframe></div>
<div class="alert"><a href="/manual_select/info" class="show">Should I sign in?</a></div>
<div class="signin">Sign In</div>
<div class="signout">Sign Out</div>

<a href="manual_select/signin"><div class="leftlink"></div></a>
<a href="manual_select/signout"><div class="rightlink"></div></a>
</div>

<div class="linkblocker"></div>

<script src="/static/js/slideshow.js"></script>
<script type="text/javascript">
window.setInterval("updateSlideshow();", 500);
function updateSlideshow() {
advance($imagelist);
}
updateSlideshow()
</script>
</body></html>
        """

        imagelist = os.listdir(root_main + "static/backgrounds")
        shuffle(imagelist)
        imagelist = str(imagelist).replace("'", '"')
        output = output.replace("$imagelist", imagelist)

        return(output)

    @cherrypy.expose
    def manual_select(self, func="signin", letter=0):
        conn = sql.connect(database)
        cur = conn.cursor()
        output = """
<html><head><title>6328 Sign In/Out</title><link rel="stylesheet" type="text/css" href="/static/css/manual.css"></head><body>

<div class="title">$prompt</div>
<div style="position: absolute; left: 50%; transform: translate(-50%, 0); top: 50px; font-size: 30px; font-style: italic;"><a href="/manual">< Return</a></div>
<div class="center"><table>$tableHtml</table>
<div style="text-align: center; font-size: 30px; margin-top: 10px;">If your name isn't listed, you don't need to $action</div>
</div>

</body></html>
        """
        #Fill in action
        if func == "signout":
            output = output.replace("$action", "sign out")
        else:
            output = output.replace("$action", "sign in")

        #Get list of all names
        cur.execute("SELECT DISTINCT name FROM people ORDER BY name")
        namesUnfiltered = orderNames(cur.fetchall())

        #Get people here
        cur.execute("SELECT name FROM live")
        namesHere = cur.fetchall()
        for i in range(0, len(namesHere)):
            namesHere[i] = namesHere[i][0]

        #Generate list of names to display
        names = []
        for i in range(0, len(namesUnfiltered)):
            if func == "signin":
                display = True
            elif func == "signout":
                display = namesUnfiltered[i] in namesHere
            else:
                display = True
            if display:
                names.append(namesUnfiltered[i])

        if letter == 0:
            output = output.replace("$prompt", "Please select your first initial:")

            #Get list of letters
            letters = []
            for name in names:
                if name[0] not in letters:
                    letters.append(name[0])
            letters = sorted(letters)

            #Generate table html (select letter)
            tempTableHtml = "<tr>"
            for i in range(0, len(letters)):
                if i % 8 == 0:
                    if i != 0:
                        tempTableHtml = tempTableHtml + "</tr><tr>"
                tempTableHtml = tempTableHtml + "<td class=\"letters\"><a href=\"/manual_select/" + func + "/" + letters[i] + "\">" + letters[i] + "</a></td>"
            tempTableHtml = tempTableHtml + "</tr>"

        else:
            output = output.replace("$prompt", "Please select your name:")

            #Generate table html (select person)
            tempTableHtml = "<tr>"
            i = -1
            for name in names:
                if name[0] == letter:
                    i += 1
                    if i % 4 == 0:
                        if i != 0:
                            tempTableHtml = tempTableHtml + "</tr><tr>"
                    tempTableHtml = tempTableHtml + "<td class=\"names\"><a href=\"/manual_internal?name=" + name + "&func=" + func + "\">" + name + "</a></td>"
            tempTableHtml = tempTableHtml + "</tr>"
        output = output.replace("$tableHtml", tempTableHtml)

        conn.close()
        return(output)

    @cherrypy.expose
    def manual_internal(self, name="John Doe", func="info"):
        conn = sql.connect(database)
        cur = conn.cursor()
        output = """
<html><head><title>6328 Sign In/Out</title><link rel="stylesheet" type="text/css" href="/static/css/manual.css"></head><body>
$contents
</body></html>
        """

        if func == "info":
            output = output.replace("$contents", """

<div style="text-align: center; font-size: 30px; font-style: italic;"><a href="/manual">< Return</a></div><br>
<div class="message">$message
<br><br>Have $deviceDescription device you bring to robotics? <a href="/manual_addDevice_stage1?name=$name" class="show">Click here</a>
</div>
            """)
            cur.execute("SELECT mac,description,reliable FROM devices WHERE name=?", (name,))
            data = cur.fetchall()
            descriptions = []
            manual_hasDevice = len(data) > 0
            manual_validDescription = False
            manual_reliableDevice = False
            for i in range(0, len(data)):
                if data[i][0] == None:
                    manual_nullMac = True
                if data[i][2] == 1:
                    manual_reliableDevice = True
                if data[i][1] != None:
                    manual_validDescription = True
                    if data[i][2] == 1:
                        descriptions.append(data[i][1])
            auto = (manual_hasDevice and manual_validDescription and manual_reliableDevice)

            if auto == False:
                output = output.replace("$message", "You, $name, should sign in manually. Be sure to sign out when you leave.")
                output = output.replace("$deviceDescription", "a")

            else:
                output = output.replace("$message", "You, $name, do not normally need to sign in.<br><br>However, if do not have your $devices, please sign in manually.")
                output = output.replace("$deviceDescription", "another")
                output = output.replace("$devices", formatList(descriptions, "or"))

            output = output.replace("$name", name)
        else:
            #Get time
            now = currentTime()

            #Update database
            if func == "signin":
                cur.execute("SELECT * FROM live WHERE name=?", (name,))
                if len(cur.fetchall()) != 0:
                    cur.execute("UPDATE live SET lastSeen=? WHERE name=?", (now,name))
                    cur.execute("UPDATE history SET timeOut=-2 WHERE name=? AND timeOut=-1", (name,))
                else:
                    cur.execute("INSERT INTO live(name,lastSeen) VALUES (?,?)", (name,now))
                    cur.execute("INSERT INTO history(name,timeIn,timeOut) VALUES (?,?,-2)", (name,now))
                    slack.post(name + " arrived at " + time.strftime("%-I:%M %p on %a %-m/%-d"))
            elif func == "signout":
                cur.execute("DELETE FROM live WHERE name=?", (name,))
                cur.execute("UPDATE history SET timeOut=? WHERE timeOut<0 AND name=?", (now,name))
                cur.execute("INSERT INTO signedOut(name,timestamp) VALUES (?,?)", (name,now))
                slack.post(name + " left at " + time.strftime("%-I:%M %p on %a %-m/%-d"))

            output = output.replace("$contents", """
<div class="title">All set!</div>
<meta http-equiv="refresh" content="3; url=/manual" />
            """)

        conn.commit()
        conn.close()
        return(output)

    @cherrypy.expose
    def manual_addDevice_stage1(self, name="John Doe"):
        output = """
<html><head><title>6328 Sign In/Out</title><link rel="stylesheet" type="text/css" href="/static/css/manual.css">
<script type="application/javascript">
function chgAction(mainForm){
if( document.mainForm.deviceType.selectedIndex==13 )
    {document.mainForm.action = "/manual_addDevice_stage2";}
else
{document.mainForm.action = "/manual_addDevice_stage3";}
}

</script>
</head><body>
<div style="text-align: center; font-size: 30px; font-style: italic;"><a href="/manual_internal?func=info&name=$name">< Return</a></div><br>
<div class="message_small">
In order to automatically track attendace, we can detect when devices enter this building. If you have a device you are willing to let us track, please continue.
<form name="mainForm" id="mainForm" method="post" action="/manual_addDevice_stage3">

<br>What sort of device is it? <select id="deviceType" name="deviceType" onChange="javascript:chgAction()">
<option>iPhone</option>
<option>Android Phone</option>
<option>Windows 10 Laptop</option>
<option>Windows 8 Laptop</option>
<option>Windows 7 Laptop</option>
<option>MacBook</option>
<option>Chromebook</option>
<option>iPad</option>
<option>Android Tablet</option>
<option>Apple Watch</option>
<option>Android Wear</option>
<option>Samsung Gear</option>
<option>iPod Touch</option>
<option>Other</option>
</select>
<input type="hidden" name="name" value="$name">
<button type="submit">Continue</button>

</form>
</div>
</body></html>
        """
        output = output.replace("$name", name)
        return(output)

    @cherrypy.expose
    def manual_addDevice_stage2(self, name="John Doe", deviceType="iPhone"):
        output = """
<html><head><title>6328 Sign In/Out</title><link rel="stylesheet" type="text/css" href="/static/css/manual.css"></head><body>
<div style="text-align: center; font-size: 30px; font-style: italic;"><a href="/manual_internal?func=info&name=$name">< Return</a></div><br>
<div class="message_small">

<form method="post" action="/manual_addDevice_stage3">
How would you classify this device? (phone, tablet, laptop, watch, etc.) <input type="text" name="description">
<input type="hidden" name="name" value="$name">
<input type="hidden" name="deviceType" value="$deviceType">
<button type="submit">Continue</button>

</form>
</div>
</body></html>
        """
        output = output.replace("$name", name)
        output = output.replace("$deviceType", deviceType)
        return(output)

    @cherrypy.expose
    def manual_addDevice_stage3(self, name="John Doe", deviceType="iPhone", description="", forceManual="0"):
        output = """
<html><head><title>6328 Sign In/Out</title><link rel="stylesheet" type="text/css" href="/static/css/manual.css">
<script>
window.setInterval("reloadIFrame();", 1000);
function reloadIFrame() {
 document.getElementById("waitDisplay").src="/manual_waitForMac";
}
</script>
</head><body>
<div style="text-align: center; font-size: 30px; font-style: italic;"><a href="/manual_internal?func=info&name=$name">< Return</a></div><br>
<div class="message_small">

$content

</form>
</div>
</body></html>
        """

        outputManual = """
<form method="post" action="/manual_addDevice_stage4">

<input type="hidden" name="name" value="$name">
<input type="hidden" name="description" value="$description">
In order to track your $description, we need to get its MAC address. Please follow the steps below:
<ol>$instructions</ol>
What is your $description's MAC address? <input type="text" name="mac">

<button type="submit">Add Device</button>
        """

        outputAuto = """
Next, please go to a web browser on your $description and type in the address:<br><br>

<div style="font-family: monospace;">http://attendance.local/add</div>

<br>You must be connected to the HS-Access or HS-Access_5GHz network.
<br><br><a href="/manual_addDevice_stage3?name=$name&deviceType=$deviceType&description=$description&forceManual=1" class="show">I can't do that</a>

<br><br><iframe id="waitDisplay" src="/manual_waitForMac" style="border: none; width: 100%; height: 200px;"></iframe>
        """

        #Get device description
        if deviceType == "Other":
            description = description
        else:
            descriptionLookup = {
                "iPhone": "phone",
                "Android Phone": "phone",
                "Windows 10 Laptop": "laptop",
                "Windows 8 Laptop": "laptop",
                "Windows 7 Laptop": "laptop",
                "MacBook": "laptop",
                "Chromebook": "laptop",
                "iPad": "tablet",
                "Android Tablet": "tablet",
                "Apple Watch": "watch",
                "Samsung Gear": "watch",
                "Android Wear": "watch",
                "iPod Touch": "iPod Touch"
            }
            description = descriptionLookup[deviceType]

        #Fill in content based on auto or manual entry
        if description == "watch" or forceManual == "1": #Manual entry
            output = output.replace("$content", outputManual)
            #Fill in instructions
            instructionsLookup = {
                "iPhone": ["Go to the settings app", "Tap 'General'", "Tap 'About'", "Your iPhone's MAC address is listed as 'Wi-Fi Address'"],
                "Android Phone": ["Go to the settings app", "Tap 'About phone'", "Tap 'Status'", "Your phone's MAC address is listed as 'Wi-Fi MAC Address'", "If these steps don't work, Google how to find the MAC address on your specific device."],
                "Windows 10 Laptop": ["Open the start menu", "In the search box, type 'cmd' and press enter", "Type in 'ipconfig /all' and press Enter. Your network configurations will display", "Scroll down to your network adapter and look for the values next to 'Physical Address'", "This is your MAC address"],
                "Windows 8 Laptop": ["Open the start menu", "In the search box, type 'cmd' and press enter", "Type in 'ipconfig /all' and press Enter. Your network configurations will display", "Scroll down to your network adapter and look for the values next to 'Physical Address'", "This is your MAC address"],
                "Windows 7 Laptop": ["Open the start menu", "In the search box, type 'cmd' and press enter", "Type in 'getmac' and press Enter", "Scroll down to your network adapter and look for the values next to 'Physical Address'", "This is your MAC address"],
                "MacBook": ["Open System Preferences", "Select Network", "In the left-hand pane, select 'Wifi'", "Click 'Advanced' in the lower right corner", "At the bottom of the window, your device's MAC address is listed as 'Wi-Fi address'"],
                "Chromebook": ["Click the status area, where your account picture appears", "Click the section that says Connected to (and the name of the network)", "At the top of the box that appears, pick your network", "In the window that opens, your MAC address is the 'Hardware address'"],
                "iPad": ["Go to the setting app", "Tap 'General'", "Tap 'About'", "Your iPad's MAC address is listed as 'Wi-Fi Address'"],
                "Android Tablet": ["Go to the settings app", "Tap 'About tablet'", "Tap 'Status'", "Your tablet's MAC address is listed as 'Wi-Fi MAC Address'", "If these steps don't work, Google how to find the MAC address on your specific device."],
                "Apple Watch": ["Go to the Watch app on your iPhone", "Tap 'General'", "Tap 'About'", "Your watch's MAC address is listed as 'Wi-Fi Address'"],
                "Android Wear": ["Go to Settings", "Choose 'System'", "Click 'About'", "Select 'Model'", "Your watch's MAC address will be displayed"],
                "Samsung Gear": ["Go to Settings", "Press 'Gear info'", "Select 'About device'", "Your watch's MAC address will be displayed"],
                "iPod Touch": ["Go to the settings app", "Tap 'General'", "Tap 'About'", "Your device's MAC address is listed as 'Wi-Fi Address'"],
                "Other": ["Google how to get your device's MAC address", "Do that"]
            }
            instructions = instructionsLookup[deviceType]
            instructionsText = ""
            for i in range(0, len(instructions)):
                instructionsText = instructionsText + "<li>" + instructions[i] + "</li>"
            output = output.replace("$instructions", instructionsText)

        else: #Auto entry
            output = output.replace("$content", outputAuto)
            conn = sql.connect(database)
            cur = conn.cursor()
            cur.execute("DELETE FROM addDevice")
            cur.execute("INSERT INTO addDevice(name,description) VALUES (?,?)", (name,description))
            conn.commit()
            conn.close()

        output = output.replace("$name", name)
        output = output.replace("$deviceType", deviceType)
        output = output.replace("$description", description)
        return(output)

    @cherrypy.expose
    def manual_addDevice_stage4(self, name="John Doe", mac="", description="unknown"):
        conn = sql.connect(database)
        cur = conn.cursor()
        output = """
<html><head><link rel="stylesheet" type="text/css" href="/static/css/manual.css">
<meta http-equiv="refresh" content="5; url=/manual_internal?func=info&name=$name" />
</head><body>
<div class="message">
$message
</div>
</body></html>
            """

        newMac = mac.lower()
        newMac = newMac.replace("-", ":")

        cur.execute("DELETE FROM addDevice")
        try:
            cur.execute("INSERT INTO devices(name,mac,description,reliable) VALUES (?,?,?,1)", (name,newMac,description))
        except:
            output = output.replace("$message", "This device is already registered in the system.<br><br>This may mean that we have decided this device is unreliable.")
        else:
            output = output.replace("$message", "Your device has been added!")

        conn.commit()
        conn.close()

        return(output.replace("$name", name))

    @cherrypy.expose
    def manual_waitForMac(self):
        conn = sql.connect(database)
        cur = conn.cursor()

        output = """
<html><head><link rel="stylesheet" type="text/css" href="/static/css/manual.css"><base target="_parent"></head><body>
<div class="message">
$content
</div>
</body></html>
        """

        outputWaiting = """
Waiting...
        """

        outputFinished = """
Your device is almost ready to be tracked.
<form method="post" action="/manual_addDevice_stage4">
<input type="hidden" name="name" value="$name">
<input type="hidden" name="mac" value="$mac">
<input type="hidden" name="description" value="$description">
<br><button type="submit">Finish</button>
</form>
        """

        cur.execute("SELECT * FROM addDevice")
        data = cur.fetchall()
        if len(data) == 0:
            output = output.replace("$content", outputWaiting)
        else:
            if data[0][2] == None:
                output = output.replace("$content", outputWaiting)
            else:
                output = output.replace("$content", outputFinished)
                output = output.replace("$name", data[0][0])
                output = output.replace("$description", data[0][1])
                output = output.replace("$mac", data[0][2])
        return(output)

    @cherrypy.expose
    def add(self):
        conn = sql.connect(database)
        cur = conn.cursor()
        output = """
<html><head><title>6328 Sign In/Out</title><link rel="stylesheet" type="text/css" href="/static/css/manual.css"></head><body>
<div class="message">$message</div>
</body></html>
        """
        def getMac():
            arpOutput = subprocess.run(["arp", cherrypy.request.remote.ip], stdout=subprocess.PIPE).stdout.decode('utf-8')
            arpOutput = arpOutput.split("\n")
            if len(arpOutput) < 2:
                return("failure")
            arpOutput = arpOutput[1][33:50]
            if len(arpOutput) == 0:
                return("failure")
            return(arpOutput)

        mac = getMac()
        cur.execute("SELECT count(*) FROM addDevice")
        if cur.fetchall()[0][0] != 1 or mac == "failure":
            output = output.replace("$message", "Something has gone wrong!<br><br>Please click I can't do that")
        else:
            cur.execute("UPDATE addDevice SET mac=?", (mac,))
            output = output.replace("$message", "Excellent! Please continue on the attendance screen.")

        conn.commit()
        conn.close()
        return(output)

    @cherrypy.expose
    def peoplelist(self, sortFirst='0'):
        conn = sql.connect(database)
        cur = conn.cursor()
        output = """
<html><head><title>People - 6328 Attendance</title><link rel="stylesheet" type="text/css" href="/static/css/admin.css"></head><body>
<a href="/">< Return</a><br><br>

<form method="post" action="/peoplelist_add">
<input name="name" type="text"><button type="submit">Add person</button>
</form>

<h3>$peoplecount People:</h3>
Sort by <a href="/peoplelist?sortFirst=1">first name</a> <a href="/peoplelist">last name</a><br><br>
<div style="line-height: 2em;">$peoplelistHtml</div>

</body></html>
        """

        #Get list of names
        cur.execute("SELECT name FROM people")
        names = orderNames(cur.fetchall(), byFirst=(sortFirst == '1'))

        #Set people count
        output = output.replace("$peoplecount", str(len(names)))

        #Create html
        peoplelistHtml = ""
        for i in range(0, len(names)):
            #Get devices
            cur.execute("SELECT description FROM devices WHERE name=? ORDER BY description", (names[i],))
            devices = cur.fetchall()
            if len(devices) == 0:
                devicesText = "no devices"
            else:
                devicesText = ""
                for f in range(0, len(devices)):
                    if devices[f][0] == None:
                        description = "unknown"
                    else:
                        description = devices[f][0]
                    devicesText = devicesText + description + ", "
                devicesText = devicesText[:-2]

            #Get categories
            cur.execute("SELECT category FROM categories WHERE name=? ORDER BY category", (names[i],))
            categories = cur.fetchall()
            if len(categories) == 0:
                categoriesText = "no categories"
            else:
                categoriesText = ""
                for f in range(0, len(categories)):
                    categoriesText = categoriesText + categories[f][0] + ", "
                categoriesText = categoriesText[:-2]
            peoplelistHtml = peoplelistHtml + "<a style=\"color: black; font-weight: bold; text-decoration: none;\" href=\"/person/" + names[i] + "\">"+ names[i] + "</a> <i>(" + devicesText + "), (" + categoriesText + ")</i><br>"
        output = output.replace("$peoplelistHtml", peoplelistHtml)

        conn.close()
        return(output)

    @cherrypy.expose
    def peoplelist_add(self, name="John Doe"):
        conn = sql.connect(database)
        cur = conn.cursor()
        cur.execute("SELECT name FROM people WHERE name=?", (name,))
        if len(cur.fetchall()) == 0:
            cur.execute("INSERT INTO people(name) VALUES (?)", (name,))

        conn.commit()
        conn.close()
        return("""<meta http-equiv="refresh" content="0; url=/person/""" + name + """" />""")

    @cherrypy.expose
    def person(self, name="John Doe"):
        conn = sql.connect(database)
        cur = conn.cursor()
        output = """
<html><head><title>$name - 6328 Attendance</title><link rel="stylesheet" type="text/css" href="/static/css/admin.css"></head><body>
<a href="/peoplelist">< Return</a><br><br>

<h2>$name</h2>
<h3>General</h3>
<form method="post" action="/person_rename">
<input name="oldName" type="hidden" value="$name">
<input name="newName" type="text"><button type="submit">Rename</button>
</form>

<form method="post" action="/person_remove">
<input name="name" type="hidden" value="$name"><button type="submit">Remove Person</button>
</form>

<h3>Categories</h3>
<form method="post" action="/person_addCategory">
<input type="hidden" value="$name" name="name">
<select name="category">$selectionHtml</select>
<button type="submit">Add Category</button>
</form>
<div style="line-height: 1.5em;">$categoriesHtml</div>

<h3>Devices</h3>
<a href="/manual_addDevice_stage1?name=$name" target="_blank">Add Device</a><br><br>
<div style="line-height: 1.5em;">$devicesHtml</div>

</body></html>
        """
        output = output.replace("$name", name)

        #Generate category selection
        cur.execute("SELECT name FROM possibleCategories")
        possibleCategories = cur.fetchall()
        for i in range(0, len(possibleCategories)):
            possibleCategories[i] = possibleCategories[i][0]
        tempSelectionHtml = ""
        for i in range(0, len(possibleCategories)):
            tempSelectionHtml = tempSelectionHtml + "<option value=\"" + possibleCategories[i] + "\">" + possibleCategories[i] + "</option>"
        output = output.replace("$selectionHtml", tempSelectionHtml)

        #Get devices
        cur.execute("SELECT id,description,reliable FROM devices WHERE name=?", (name,))
        devices = cur.fetchall()

        #Generate devices html
        devicesHtml = ""
        for i in range(0, len(devices)):
            if devices[i][2] == 1:
                toggleText = "Mark as unreliable"
            else:
                toggleText = "Mark as reliable"
            if devices[i][1] == None:
                description = "unknown"
            else:
                description = devices[i][1]
            devicesHtml = devicesHtml + "<i>" + description + "</i>"
            devicesHtml = devicesHtml + " - <a href=\"/person_toggleReliable/" + str(devices[i][0]) + "\">" + toggleText + "</a>"
            devicesHtml = devicesHtml + " - <a href=\"/person_removeDevice/" + str(devices[i][0]) + "\">Remove device</a><br>"
        output = output.replace("$devicesHtml", devicesHtml)

        #Get categories
        cur.execute("SELECT category FROM categories WHERE name=?", (name,))
        categories = cur.fetchall()
        for i in range(0, len(categories)):
            categories[i] = categories[i][0]

        #Generate categories html
        categoriesHtml = ""
        for i in range(0, len(categories)):
            categoriesHtml = categoriesHtml + "<i>" + categories[i] + "</i>"
            categoriesHtml = categoriesHtml + " - <a href=\"/person_removeCategory?name=" + name + "&category=" + categories[i] + "\">Remove category</a><br>"
        output = output.replace("$categoriesHtml", categoriesHtml)

        conn.close()
        return(output)

    @cherrypy.expose
    def person_rename(self, oldName="John Doe", newName="John Doe"):
        conn = sql.connect(database)
        cur = conn.cursor()

        cur.execute("UPDATE people SET name=? WHERE name=?", (newName,oldName))
        cur.execute("UPDATE devices SET name=? WHERE name=?", (newName,oldName))
        cur.execute("UPDATE live SET name=? WHERE name=?", (newName,oldName))
        cur.execute("UPDATE history SET name=? WHERE name=?", (newName,oldName))
        cur.execute("UPDATE signedOut SET name=? WHERE name=?", (newName,oldName))
        cur.execute("UPDATE categories SET name=? WHERE name=?", (newName,oldName))
        cur.execute("UPDATE addDevice SET name=? WHERE name=?", (newName,oldName))

        output = """<meta http-equiv="refresh" content="0; url=/person/$name" />"""
        output = output.replace("$name", newName)

        conn.commit()
        conn.close()
        return(output)

    @cherrypy.expose
    def person_remove(self, name="John Doe"):
        conn = sql.connect(database)
        cur = conn.cursor()

        cur.execute("DELETE FROM people WHERE name=?", (name,))
        cur.execute("DELETE FROM devices WHERE name=?", (name,))

        conn.commit()
        conn.close()
        return("""<meta http-equiv="refresh" content="0; url=/peoplelist" />""")

    @cherrypy.expose
    def person_addCategory(self, name="John Doe", category=""):
        conn = sql.connect(database)
        cur = conn.cursor()

        cur.execute("INSERT INTO categories(name,category) VALUES (?,?)", (name,category))

        output = """<meta http-equiv="refresh" content="0; url=/person/$name" />"""
        output = output.replace("$name", name)

        conn.commit()
        conn.close()
        return(output)

    @cherrypy.expose
    def person_removeCategory(self, name="John Doe", category=""):
        conn = sql.connect(database)
        cur = conn.cursor()

        cur.execute("DELETE FROM categories WHERE name=? AND category=?", (name,category))

        output = """<meta http-equiv="refresh" content="0; url=/person/$name" />"""
        output = output.replace("$name", name)

        conn.commit()
        conn.close()
        return(output)

    @cherrypy.expose
    def person_toggleReliable(self, id=-1):
        conn = sql.connect(database)
        cur = conn.cursor()

        cur.execute("SELECT reliable FROM devices WHERE id=?", (id,))
        data = cur.fetchall()
        if len(data) > 0:
            if data[0][0] == 0:
                newValue = 1
            else:
                newValue = 0
            cur.execute("UPDATE devices SET reliable=? WHERE id=?", (newValue,id))

        output = """<meta http-equiv="refresh" content="0; url=/person/$name" />"""

        #Find name
        cur.execute("SELECT name FROM devices WHERE id=?", (id,))
        output = output.replace("$name", cur.fetchall()[0][0])

        conn.commit()
        conn.close()
        return(output)

    @cherrypy.expose
    def person_removeDevice(self, id=-1):
        conn = sql.connect(database)
        cur = conn.cursor()

        #Find name
        cur.execute("SELECT name FROM devices WHERE id=?", (id,))
        name = cur.fetchall()[0][0]

        cur.execute("DELETE FROM devices WHERE id=?", (id,))

        output = """<meta http-equiv="refresh" content="0; url=/person/$name" />"""
        output = output.replace("$name", name)

        conn.commit()
        conn.close()
        return(output)

    @cherrypy.expose
    def manual_displayType(self):
        conn = sql.connect(database)
        cur = conn.cursor()

        cur.execute("SELECT * FROM slideshowSettings")
        output = str(cur.fetchall()[0][0])

        conn.close()
        return(output)

def error_page(status, message, traceback, version):
    output = """
<html><head><title>Error - 6328 Attendance</title></head><body>
<h1>This is embarrassing...</h1>
<h3>Looks like something isn't working right. Please try again later.<br><br><a href="javascript:window.history.back();">Click here to go back</a></h3>
<div style="font-family: monospace;">
$status<br>
$message<br>
$traceback
</div>
</body></html>
"""
    output = output.replace("$traceback", traceback.replace("\n", "<br>"))
    output = output.replace("$status", status)
    output = output.replace("$message", message)
    return(output)

if __name__ == "__main__":
    #Check for root permissions
    if os.geteuid() != 0 and port == 80:
        print("Please run again using 'sudo' to host on port 80.")
        exit()

    cherrypy.config.update({'server.socket_port': port, 'server.socket_host': host, 'error_page.500': error_page, 'error_page.404': error_page})
    cherrypy.quickstart(mainServer(), "/", {"/": {"log.access_file": root_data + "logs/serverlog.log", "log.error_file": "", "tools.sessions.on": True, "tools.sessions.timeout": 30}, "/static": {"tools.staticdir.on": True, "tools.staticdir.dir": root_main + "static"}, "/favicon.ico": {"tools.staticfile.on": True, "tools.staticfile.filename": root_main + "static/favicon.ico"}})
