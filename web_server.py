import config
import cherrypy
import recordkeeper
from simple_websocket_server import WebSocketServer, WebSocket
import inflect
import sqlite3 as sql
import requests
import threading
from random import shuffle
import math
import time
import datetime
import subprocess
import os

# Setup
database = config.data + "/attendance.db"
log_database = config.data + "/logs.db"
language_manager = inflect.engine()
record_requests = []
request_threads = []
if config.enable_slack:
	slack_url = open(config.data + "/slack_url.txt", "r").read()

# Get ip address
if config.web_forced_advised != None:
    advised_ip = config.web_forced_advised
else:
    ifconfig_result = subprocess.run(["ifconfig"], stdout=subprocess.PIPE).stdout.decode('utf-8')
    ifconfig_result = [x.split("inet ")[1].split(" ")[0] for x in ifconfig_result.split("\n") if "inet " in x]
    ifconfig_result = [x for x in ifconfig_result if x != "127.0.0.1"]
    if len(ifconfig_result) < 1:
        ifconfig_result.append("127.0.0.1")
    advised_ip = ifconfig_result[0]

	
def slack_post(message):
	requests.post(slack_url, json={"text": message})

def record_request_thread(request_id):
    request = record_requests[request_id]
    try:
        data = recordkeeper.get_range(request["start_date"], request["end_date"], filter=request["filter"])
    except:
        x = 0
    else:
        record_requests[request_id]["output"] = data
    record_requests[request_id]["complete"] = True
    send_complete(request_id)

def current_time():
    return(int(round(time.time())))

def format_duration(duration, show_seconds):
    temp_duration = duration
    hours = math.floor(temp_duration/3600)
    temp_duration -= hours*3600
    minutes = math.floor(temp_duration/60)
    seconds = temp_duration - minutes*60
    duration_formatted = ""
    if hours > 0:
        duration_formatted = str(hours) + "h "
    if minutes > 0:
        duration_formatted = duration_formatted + str(minutes) + "m "
    if show_seconds:
        duration_formatted = duration_formatted + str(seconds) + "s "
    return(duration_formatted[:-1])


def order_names(raw_names, by_first=False):
    names = []
    for i in range(0, len(raw_names)):
        name = raw_names[i][0]
        name_list = name.split(" ")
        if len(name_list) < 2:
            name_list.append("")
        names.append({"first": name_list[0], "last": name_list[1]})
    if by_first:
        names_sorted = sorted(names, key=lambda x: (x["first"], x["last"]))
    else:
        names_sorted = sorted(names, key=lambda x: (x["last"], x["first"]))
    names_output = []
    for i in range(0, len(names_sorted)):
        if names_sorted[i]["last"] == "":
            names_output.append(names_sorted[i]["first"])
        else:
            names_output.append(
                names_sorted[i]["first"] + " " + names_sorted[i]["last"])
    return(names_output)


def javascript_date(date, no_time=False):
    new_date = time.localtime(date)
    year = time.strftime("%Y", new_date)
    month = str(int(time.strftime("%m", new_date)) - 1)
    if no_time:
        day_hour_minute = time.strftime("%d", new_date)
    else:
        day_hour_minute = time.strftime("%d, %H, %M", new_date)
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


def format_list(input_list, separator):
    output = ""
    for i in range(0, len(input_list)):
        output = output + input_list[i]
        if i != len(input_list) - 1:
            if len(input_list) == 2:
                output = output + " "
            else:
                output = output + ", "
        if i == len(input_list) - 2:
            output = output + separator + " "
    return(output)


class main_server(object):
    @cherrypy.expose
    def index(self):
        conn = sql.connect(database)
        cur = conn.cursor()
        output = """
<html><head><title>$title</title><link rel="stylesheet" type="text/css" href="/static/css/admin.css"><style>
iframe {
  border: none;
  width: 100%;
  height: 500px;
}
</style>
</head><body>

<form method="get" action="/load_records">
<input type="date" name="start_date" value="$start_value"> to <input type="date" name="end_date" value="$end_value"> for person <select name="filter"><option value="*">Everyone</option>$selectionHtml</select>
<input type="hidden" name="source" value="cache"></input>
<button type="submit">Get Records</button>
</form>

<form method="get" action="/load_records">
<input type="hidden" name="start_date" value="$today_value">
<input type="hidden" name="end_date" value="$today_value">
<input type="hidden" name="source" value="live"></input>
<button type="submit">Get Today's Records</button>
</form>

<a href="/advanced">Advanced Get Records</a><br><br>
<a href="/manual">Manual Sign In/Out</a><br><br>
<a href="/peoplelist">Manage People</a>

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

        # Generate name selector
        names = order_names(cur.execute("SELECT * FROM people").fetchall())
        temp_selection_html = ""
        for i in range(0, len(names)):
            temp_selection_html = temp_selection_html + "<option value=\"" + \
                names[i] + "\">" + names[i] + "</option>"
        output = output.replace("$selectionHtml", temp_selection_html)

        # Fill in dates from sessions
        if "lastStartDate" in cherrypy.session:
            start_value = cherrypy.session["lastStartDate"]
        else:
            start_value = time.strftime("%Y-%m-%d")
        output = output.replace("$start_value", start_value)
        if "lastEndDate" in cherrypy.session:
            end_value = cherrypy.session["lastEndDate"]
        else:
            end_value = time.strftime("%Y-%m-%d")
        output = output.replace("$end_value", end_value)
        output = output.replace("$today_value", time.strftime("%Y-%m-%d"))

        conn.close()
        return(output.replace("$title", config.admin_title))

    @cherrypy.expose
    def advanced(self):
        conn = sql.connect(database)
        cur = conn.cursor()
        output = """
<html><head><title>$title</title><link rel="stylesheet" type="text/css" href="/static/css/admin.css">
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
<form id="mainForm" method="get" action="/load_records">
Start date: <input type="date" name="start_date" value="$start_value"><br>
End date: <input type="date" name="end_date" value="$end_value"><br>
Source: <select name="source">
<option value="cache">Nightly Cache (faster, especially for large queries)</option>
<option value="live">Live Analysis (slower, includes data from current day)</option>
</select>
</form>
<button onclick="setChecks(true);">Check All</button><button onclick="setChecks(false);">Uncheck All</button><br><br>

$check_html

<input form="mainForm" type="hidden" name="filter" id="output">
<button form="mainForm" type="submit">Get Records</button>

</body></html>
        """
        # Get list of categories
        cur.execute("SELECT * FROM possible_categories")
        names = cur.fetchall()
        clean_names = []
        for i in range(0, len(names)):
            clean_names.append(names[i][0])
            names[i] = language_manager.plural(names[i][0])

        # Get list of people
        cur.execute("SELECT name FROM people")
        peoplelist = order_names(cur.fetchall())
        names.extend(peoplelist)
        clean_names.extend(peoplelist)

        # Add names to javascript
        output = output.replace("$namelist", str(
            clean_names).replace("'", '"'))

        # Add names to html
        check_html = ""
        for i in range(0, len(names)):
            display = title(names[i])
            check_html = check_html + '<label class="check"><input type="checkbox" class="check" onclick="refresh()" id="check' + \
                str(i) + '"> ' + display + '</label><br>'
        output = output.replace("$check_html", check_html)

        # Fill in dates from sessions
        if "lastStartDate" in cherrypy.session:
            start_value = cherrypy.session["lastStartDate"]
        else:
            start_value = time.strftime("%Y-%m-%d")
        output = output.replace("$start_value", start_value)
        if "lastEndDate" in cherrypy.session:
            end_value = cherrypy.session["lastEndDate"]
        else:
            end_value = time.strftime("%Y-%m-%d")
        output = output.replace("$end_value", end_value)

        conn.close()
        return(output.replace("$title", config.admin_title))

    @cherrypy.expose
    def live(self, version="homepage"):
        conn = sql.connect(database)
        cur = conn.cursor()

        output = """
<html><head>
<link rel="stylesheet" type="text/css" href="/static/css/admin.css">
<link rel="stylesheet" type="text/css" href="/static/css/font.css">
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

td {
font-family: "Title";
font-size: 20px;
}

td.yellow {
background-color: yellow;
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

        # Get list of live names
        live = recordkeeper.get_livecache()
        rows = order_names([(x["name"],) for x in live])
        if len(rows) == 0:
            rows.append("No one")

        # Generate table html
        temp_table_html = "<tr>"
        i = -1
        for row in rows:
            i += 1
            if i % 5 == 0:
                if i != 0:
                    temp_table_html = temp_table_html + "</tr><tr>"

            #Check if manual sign in
            if row == "No one":
                yellow_text = ""
            else:
                x = 0
                while live[x]["name"] != row:
                    x += 1
                if live[x]["manual_signin"]:
                    yellow_text = " yellow"
                else:
                    yellow_text = ""
            temp_table_html = temp_table_html + "<td class=\"names" + yellow_text + "\">" + row + "</td>"
        temp_table_html = temp_table_html + "</tr>"
        output = output.replace("$tableHtml", temp_table_html)

        conn.close()
        return(output)
    
    @cherrypy.expose
    def load_records(self, start_date="", end_date="", filter="*", source="cache"):
        conn = sql.connect(database)
        cur = conn.cursor()
        output = """
<html><head><title>$title</title><link rel="stylesheet" type="text/css" href="/static/css/admin.css">
<style>

.center {
position: absolute;
top: 50%;
left: 50%;
transform: translate(-50%, -50%);
}

div.load-text {
text-align: center;
font-size: 25px;
margin-bottom: 10px;
max-width: 150px;
font-weight: bold;
}

div.funny-text {
font-weight: normal;
font-size: 20px;
margin-top: 10px;
}
</style>
<script>
const requestId = $requestid
</script>
</head>
<body>

<div class="center">
<div class="load-text">
Please wait
<div class="funny-text" id="funnyText"></div>
</div>
<canvas id="loadingCanvas" width=150, height=60></canvas>
<img id="loadingImage" src="/static/img/loading.png" hidden></img>
</div>

<script src="/static/js/loading.js"></script>

</body>
</html>
            """
        error_output = """
<html><head><title>$title</title><link rel="stylesheet" type="text/css" href="/static/css/admin.css"></head>
<body>
<a href="/">< Return</a><br><br>
$error
</body>
</html>
            """
        redirect_output = """
<html><head><link rel="stylesheet" type="text/css" href="/static/css/manual.css">
<meta http-equiv="refresh" content="0; url=/show_records?request_id=$requestid" />
</head><body></body></html>
        """
        
        def get_error(error):
            conn.close()
            return(error_output.replace("$error", error).replace("$title", config.admin_title))
        
        # Update session data
        cherrypy.session["lastStartDate"] = start_date
        cherrypy.session["lastEndDate"] = end_date
        
        # Create unix timestamp from input
        try:
            start_date = time.mktime(datetime.datetime.strptime(start_date, "%Y-%m-%d").timetuple()) - (5*60*60)
            end_date = time.mktime(datetime.datetime.strptime(end_date, "%Y-%m-%d").timetuple()) + (19*60*60)
        except:
            return(get_error("Please enter a valid start and end date."))
        start_date = start_date + time.timezone
        end_date = end_date + time.timezone
        
        # Check that range is valid
        if end_date < start_date:
            conn.close()
            return(get_error("End date is before start date."))

        # Create list of names
        if filter == "*":
            cur.execute("SELECT * FROM people")
            names = order_names(cur.fetchall())
        else:
            names = []
            
            # Get categories
            cur.execute("SELECT * FROM possible_categories")
            categories = cur.fetchall()
            for i in range(0, len(categories)):
                categories[i] = categories[i][0]
        
            # Iterate through input (if category, add names from category. if name, add to list)
            input_list = filter.split(",")
            for i in range(0, len(input_list)):
                if input_list[i] in categories:
                    cur.execute("SELECT name FROM categories WHERE category=?", (input_list[i],))
                    names_in_cat = cur.fetchall()
                    for f in range(0, len(names_in_cat)):
                        if names_in_cat[f][0] not in names:
                            names.append(names_in_cat[f][0])
                else:
                    if input_list[i] not in names:
                        names.append(input_list[i])
        
        #Create request data
        request = {"start_date": start_date, "end_date": end_date, "filter": names, "output": [], "complete": False}
        record_requests.append(request)
        request_id = len(record_requests) - 1
        
        #Start thread or get data
        if source == "live":
            request_threads.append(threading.Thread(target=record_request_thread, args=(request_id,), daemon=True))
            request_threads[len(request_threads) - 1].start()
            output = output.replace("$requestid", str(request_id))
        else:
            record_requests[request_id]["output"] = recordkeeper.get_range(record_requests[request_id]["start_date"], record_requests[request_id]["end_date"], filter=record_requests[request_id]["filter"], cached=True)
            record_requests[request_id]["complete"] = True
            output = redirect_output.replace("$requestid", str(request_id))
        return(output.replace("$title", config.admin_title))

    @cherrypy.expose
    def show_records(self, request_id):
        conn = sql.connect(database)
        cur = conn.cursor()
        
        output = """
<html><head><title>$title</title><link rel="stylesheet" type="text/css" href="/static/css/admin.css">

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
<a href="/">< Return</a><br><br>

$contents

$pieDiv
$catPieDiv
$histogramDiv
$calendarDiv
$timelineDiv

</body></html>
            """
        
        pie_script = """
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
        
        pie_div = """<br><div id="piechart" style="height: 500px; width: 100%;"></div>"""
        
        cat_pie_script = """
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
        
        cat_pie_div = """<br><div id="catpiechart" style="height: 500px; width: 100%;"></div>"""
        
        histogram_script = """
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
        
        histogram_div = """<br><div id="histogram" style="height: 500px; width: 100%;"></div>"""
        
        calendar_script = """
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
        
        calendar_div = """<br><div id="calendar" style="height: 500px; width: 100%;"></div>"""
        
        timeline_script = """
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
        
        timeline_div = """<br><div id="timeline" style="height: 100%;"></div>"""

        # Get data from request
        request_id = int(request_id)
        if request_id not in range(len(record_requests)):
            return("""<meta http-equiv="refresh" content="0;URL='/'" />""")
        rows = sorted(record_requests[request_id]["output"], key=lambda x: (x["name"], x["timein"]))
        start_date = record_requests[request_id]["start_date"]
        end_date = record_requests[request_id]["end_date"]

        # Determine if single or multiple days and add appropriate graphs

        # Pie chart -> multple people, any # of days
        # Histogram -> any # of poeple, any # of days, more than one entry
        # Calendar -> any # of people, multiple days
        # Timeline -> multiple people, 1-4 days
        if len(record_requests[request_id]["filter"]) > 1:
            gen_piechart = True
            output = output.replace("$pieScript", pie_script)
            output = output.replace("$pieDiv", pie_div)
            output = output.replace("$catPieScript", cat_pie_script)
            output = output.replace("$catPieDiv", cat_pie_div)
        else:
            gen_piechart = False
            output = output.replace("$pieScript", "")
            output = output.replace("$pieDiv", "")
            output = output.replace("$catPieScript", "")
            output = output.replace("$catPieDiv", "")

        if len(rows) > 1:
            gen_histogram = True
            output = output.replace("$histogramScript", histogram_script)
            output = output.replace("$histogramDiv", histogram_div)
        else:
            gen_histogram = False
            output = output.replace("$histogramScript", "")
            output = output.replace("$histogramDiv", "")

        if end_date - start_date <= (60*60*25):
            single_day = True
            output = output.replace("$calendarScript", "")
            output = output.replace("$calendarDiv", "")
        else:
            single_day = False
            output = output.replace("$calendarScript", calendar_script)
            output = output.replace("$calendarDiv", calendar_div)

        if end_date - start_date <= (60*60*25*4):
            if len(record_requests[request_id]["filter"]) > 1:
                gen_timeline = True
                output = output.replace("$timelineScript", timeline_script)
                output = output.replace("$timelineDiv", timeline_div)
            else:
                gen_timeline = False
                output = output.replace("$timelineScript", "")
                output = output.replace("$timelineDiv", "")
        else:
            gen_timeline = False
            output = output.replace("$timelineScript", "")
            output = output.replace("$timelineDiv", "")

        # Generate table contents
        date_format = "%a %m/%d - %I:%M %p"
        temp_contents = "<table><tr><th>Name</th><th>Time In</th><th>Time Out</th><th>Duration</th>"
        total_duration = 0

        internal_pie_data = {}
        histogram_data = [['Name', 'Hours']]
        rowid = 0
        extra_row_count = 0
        for row in rows:
            rowid += 1
            if row["timein"] < 0:
                timein_formatted = "Out of range"
                duration_start = start_date
            else:
                timein_formatted = time.strftime(date_format, time.localtime(row["timein"]))
                duration_start = row["timein"]
            
            if row["timeout"] < 0:
                timeout_formatted = "Out of range"
                duration_end = end_date
            else:
                timeout_formatted = time.strftime(date_format, time.localtime(row["timeout"]))
                duration_end = row["timeout"]
            raw_duration = duration_end - duration_start

            # Add to total for pie chart
            if row["name"] not in internal_pie_data:
                internal_pie_data[row["name"]] = 0
            internal_pie_data[row["name"]] += raw_duration

            # Record for histogram
            histogram_data.append([row["name"], raw_duration])

            # Format Duration
            total_duration += raw_duration
            duration_formatted = format_duration(raw_duration, show_seconds=False)

            # Get class
            if rowid > 25:
                rowclass = ' class="extraRow"'
                extra_row_count += 1
            else:
                rowclass = ""

            temp_contents = temp_contents + '<tr' + rowclass + '><td><a class="hidden" href="/person/' + \
                row["name"] + '">' + row["name"] + "</a></td><td>" + timein_formatted + "</td><td>" + \
                timeout_formatted + "</td><td>" + duration_formatted + "</td></tr>"

        temp_contents = temp_contents + "</table>"
        if extra_row_count > 0:
            if extra_row_count == 1:
                rowname = "Row"
            else:
                rowname = "Rows"
            temp_contents = temp_contents + '<div id="showAllLink"><br><a href="javascript:showAll()">Show ' + \
                str(extra_row_count) + ' More ' + rowname + '</a></div>'

        # Generate title
        title_date_format = "%a %m/%d"
        if single_day:
            temp_title = "<h3>" + time.strftime(title_date_format, time.localtime(
                start_date)) + " (" + format_duration(total_duration, show_seconds=False) + " total time)</h3>"
        else:
            temp_title = "<h3>" + time.strftime(title_date_format, time.localtime(start_date)) + " to " + time.strftime(
                title_date_format, time.localtime(end_date - 1)) + " (" + format_duration(total_duration, show_seconds=False) + " total time)</h3>"

        # Generate pie chart
        if gen_piechart:
            pie_data = [['Name', 'Hours']]
            for person, seconds in internal_pie_data.items():
                pie_data.append([person, (seconds/60/60)])
            output = output.replace("$pieData", str(pie_data))

            # Generate category pie chart
            category_pie_data = {}
            for person, seconds in internal_pie_data.items():
                cur.execute(
                    "SELECT category FROM categories WHERE name=? ORDER BY category", (person,))
                categories = cur.fetchall()
                for i in range(0, len(categories)):
                    categories[i] = title(
                        language_manager.plural(categories[i][0]))
                if len(categories) == 0:
                    categories_string = "Unclassified"
                else:
                    categories_string = format_list(categories, "and")

                if categories_string in category_pie_data:
                    category_pie_data[categories_string] += seconds
                else:
                    category_pie_data[categories_string] = seconds

            pie_data = [['Category', 'Hours']]
            for category, seconds in category_pie_data.items():
                pie_data.append([category, (seconds/60/60)])
            output = output.replace("$catPieData", str(pie_data))

        # Generate histogram
        if gen_histogram:
            for i in range(1, len(histogram_data)):
                histogram_data[i][1] = histogram_data[i][1]/60/60
            output = output.replace("$histogramData", str(histogram_data))

        # Generate calendar (create totals)
        if single_day == False:
            temp_calendar_data = {}
            for row in rows:
                if row["timein"] < 0:
                    duration_start = start_date
                else:
                    duration_start = row["timein"]
            
                if row["timeout"] < 0:
                    duration_end = end_date
                else:
                    duration_end = row["timeout"]
                raw_duration = duration_end - duration_start

                date = javascript_date(row["timein"], no_time=True)
                if date in temp_calendar_data:
                    temp_calendar_data[date] += raw_duration
                else:
                    temp_calendar_data[date] = raw_duration

            # Generate calendar (format data)
            calendar_data = "["
            for date, seconds in temp_calendar_data.items():
                calendar_data = calendar_data + \
                    "[" + date + ", " + str(round(seconds/60/60)) + "]"
                calendar_data = calendar_data + ","
            calendar_data = calendar_data[:-1] + "]"
            output = output.replace("$calendarData", calendar_data)

        # Generate timeline
        if gen_timeline:
            timeline_data = ""
            i = -1
            for row in rows:
                i += 1
                if row["timein"] < 0:
                    duration_start = start_date
                else:
                    duration_start = row["timein"]
                
                if row["timeout"] < 0:
                    duration_end = end_date
                else:
                    duration_end = row["timeout"]
                
                timeline_data = timeline_data + \
                    "['" + row["name"] + "', '" + row["name"] + "', " + \
                    javascript_date(duration_start) + ", " + \
                    javascript_date(duration_end) + "]"
                if i != len(rows):
                    timeline_data = timeline_data + ","
            output = output.replace("$timelineData", timeline_data)

        conn.close()
        return(output.replace("$contents", temp_title + temp_contents).replace("$title", config.admin_title))

    @cherrypy.expose
    def manual(self):
        output = """
<html><head><title>$title_signin</title><link rel="stylesheet" type="text/css" href="/static/css/manual.css"><link rel="stylesheet" type="text/css" href="/static/css/font.css">
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
<div class="yellow_alert"">(Must sign out manually)</div>
<div class="yellow_box"></div>
<div style="position: absolute; top: 85px; left: 50%; transform: translate(-50%, 0); width: 100%;"><iframe id="liveView" src="/live/signin" style="border: none; width: 100%; height: 300px;"></iframe></div>
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

        imagelist = os.listdir(config.repo + "/static/backgrounds")
        shuffle(imagelist)
        imagelist = str(imagelist).replace("'", '"')
        output = output.replace("$imagelist", imagelist)

        return(output.replace("$title_signin", config.signin_title))

    @cherrypy.expose
    def manual_select(self, func="signin", letter=0):
        conn = sql.connect(database)
        cur = conn.cursor()
        output = """
<html><head><title>$title_signin</title><link rel="stylesheet" type="text/css" href="/static/css/manual.css"><link rel="stylesheet" type="text/css" href="/static/css/font.css"></head><body>

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

        # Get list of all names
        cur.execute("SELECT DISTINCT name FROM people ORDER BY name")
        names = order_names(cur.fetchall())

        if letter == 0:
            output = output.replace(
                "$prompt", "Please select your first initial:")

            # Get list of letters
            letters = []
            for name in names:
                if name[0] not in letters:
                    letters.append(name[0])
            letters = sorted(letters)

            # Generate table html (select letter)
            temp_table_html = "<tr>"
            for i in range(0, len(letters)):
                if i % 8 == 0:
                    if i != 0:
                        temp_table_html = temp_table_html + "</tr><tr>"
                temp_table_html = temp_table_html + "<td class=\"letters\"><a href=\"/manual_select/" + \
                    func + "/" + letters[i] + "\">" + letters[i] + "</a></td>"
            temp_table_html = temp_table_html + "</tr>"

        else:
            output = output.replace("$prompt", "Please select your name:")

            # Generate table html (select person)
            temp_table_html = "<tr>"
            i = -1
            for name in names:
                if name[0] == letter:
                    i += 1
                    if i % 4 == 0:
                        if i != 0:
                            temp_table_html = temp_table_html + "</tr><tr>"
                    temp_table_html = temp_table_html + "<td class=\"names\"><a href=\"/manual_internal?name=" + \
                        name + "&func=" + func + "\">" + name + "</a></td>"
            temp_table_html = temp_table_html + "</tr>"
        output = output.replace("$tableHtml", temp_table_html)

        conn.close()
        return(output.replace("$title_signin", config.signin_title))

    @cherrypy.expose
    def manual_internal(self, name="John Doe", func="info"):
        conn = sql.connect(database)
        cur = conn.cursor()
        output = """
<html><head><title>$title_signin</title><link rel="stylesheet" type="text/css" href="/static/css/manual.css"><link rel="stylesheet" type="text/css" href="/static/css/font.css"></head><body>
$contents
</body></html>
        """

        if func == "info":
            output = output.replace("$contents", """

<div style="text-align: center; font-size: 30px; font-style: italic;"><a href="/manual">< Return</a></div><br>
<div class="message">$message
<br><br>Have $deviceDescription device you bring to robotics? <a href="/manual_add_device_stage_1?name=$name" class="show">Click here</a>
</div>
            """)
            cur.execute(
                "SELECT mac,description,reliable FROM devices WHERE name=?", (name,))
            data = cur.fetchall()
            descriptions = []
            manual_has_device = len(data) > 0
            manual_valid_description = False
            manual_reliable_device = False
            for i in range(0, len(data)):
                if data[i][2] == 1:
                    manual_reliable_device = True
                if data[i][1] != None:
                    manual_valid_description = True
                    if data[i][2] == 1:
                        descriptions.append(data[i][1])
            auto = (
                manual_has_device and manual_valid_description and manual_reliable_device)

            if auto == False:
                output = output.replace(
                    "$message", "You, $name, should sign in manually. Be sure to sign out when you leave.")
                output = output.replace("$deviceDescription", "a")

            else:
                output = output.replace(
                    "$message", "You, $name, do not normally need to sign in.<br><br>However, if do not have your $devices, please sign in manually.")
                output = output.replace("$deviceDescription", "another")
                output = output.replace(
                    "$devices", format_list(descriptions, "or"))

            output = output.replace("$name", name)
        else:
            # Get time
            now = current_time()

            # Update database
            if func == "signin":
                action = 1
            else:
                action = 2
            
            log_conn = sql.connect(log_database)
            log_cur = log_conn.cursor()
            id = log_cur.execute("SELECT id FROM lookup WHERE value=?", (name,)).fetchall()
            if len(id) < 1:
                max_id = log_cur.execute("SELECT max(id) FROM lookup").fetchall()[0][0]
                id = max_id + 1
                log_cur.execute("INSERT INTO lookup(id,value) VALUES (?,?)", (id,name))
            else:
                id = id[0][0]
            log_cur.execute("INSERT INTO logs(timestamp,action,id) VALUES (?,?,?)", (now,action,id))
            log_conn.commit()
            log_conn.close()

            output = output.replace("$contents", """
<div class="title">All set!<br><br>Your name will $action in a few minutes.</div>
<meta http-equiv="refresh" content="3; url=/manual" />
            """)
            if func == "signin":
                output = output.replace("$action", "appear")
            else:
                output = output.replace("$action", "disappear")

        conn.commit()
        conn.close()
        return(output.replace("$title_signin", config.signin_title))

    @cherrypy.expose
    def manual_add_device_stage_1(self, name="John Doe"):
        output = """
<html><head><title>$title_signin</title><link rel="stylesheet" type="text/css" href="/static/css/manual.css"><link rel="stylesheet" type="text/css" href="/static/css/font.css">
<script type="application/javascript">
function chgAction(mainForm){
if( document.mainForm.device_type.selectedIndex==13 )
    {document.mainForm.action = "/manual_add_device_stage_2";}
else
{document.mainForm.action = "/manual_add_device_stage_3";}
}

</script>
</head><body>
<div style="text-align: center; font-size: 30px; font-style: italic;"><a href="/manual_internal?func=info&name=$name">< Return</a></div><br>
<div class="message_small">
In order to automatically track attendace, we can detect when devices enter this building. If you have a device you are willing to let us track, please continue.
<form name="mainForm" id="mainForm" method="post" action="/manual_add_device_stage_3">

<br>What sort of device is it? <select id="device_type" name="device_type" onChange="javascript:chgAction()">
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
        return(output.replace("$title_signin", config.signin_title))

    @cherrypy.expose
    def manual_add_device_stage_2(self, name="John Doe", device_type="iPhone"):
        output = """
<html><head><title>$title_signin</title><link rel="stylesheet" type="text/css" href="/static/css/manual.css"><link rel="stylesheet" type="text/css" href="/static/css/font.css"></head><body>
<div style="text-align: center; font-size: 30px; font-style: italic;"><a href="/manual_internal?func=info&name=$name">< Return</a></div><br>
<div class="message_small">

<form method="post" action="/manual_add_device_stage_3">
How would you classify this device? (phone, tablet, laptop, watch, etc.) <input type="text" name="description">
<input type="hidden" name="name" value="$name">
<input type="hidden" name="device_type" value="$device_type">
<button type="submit">Continue</button>

</form>
</div>
</body></html>
        """
        output = output.replace("$name", name)
        output = output.replace("$device_type", device_type)
        return(output.replace("$title_signin", config.signin_title))

    @cherrypy.expose
    def manual_add_device_stage_3(self, name="John Doe", device_type="iPhone", description="", force_manual="0"):
        output = """
<html><head><title>$title_signin</title><link rel="stylesheet" type="text/css" href="/static/css/manual.css"><link rel="stylesheet" type="text/css" href="/static/css/font.css">
<script>
window.setInterval("reloadIFrame();", 1000);
function reloadIFrame() {
 document.getElementById("waitDisplay").src="/manual_wait_for_mac";
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

        output_manual = """
<form method="post" action="/manual_add_device_stage_4">

<input type="hidden" name="name" value="$name">
<input type="hidden" name="description" value="$description">
In order to track your $description, we need to get its MAC address. Please follow the steps below:
<ol>$instructions</ol>
What is your $description's MAC address? <input type="text" name="mac">

<button type="submit">Add Device</button>
        """

        output_auto = """
Next, please go to a web browser on your $description and type in the address:<br><br>

<div style="font-family: monospace;">http://$hostname/add</div>

<br>You must be connected to the HS-Access or HS-Access_5GHz network.
<br><br><a href="/manual_add_device_stage_3?name=$name&device_type=$device_type&description=$description&force_manual=1" class="show">I can't do that</a>

<br><br><iframe id="waitDisplay" src="/manual_wait_for_mac" style="border: none; width: 100%; height: 200px;"></iframe>
        """

        # Get device description
        if device_type == "Other":
            description = description
        else:
            description_lookup = {
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
            description = description_lookup[device_type]

        # Fill in content based on auto or manual entry
        if description == "watch" or force_manual == "1":  # Manual entry
            output = output.replace("$content", output_manual)
            #Fill in instructions
            instructions_lookup = {
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
                "Other": ["Google how to get your device's Wi-Fi MAC address", "Do that"]
            }
            instructions = instructions_lookup[device_type]
            instructions_text = ""
            for i in range(0, len(instructions)):
                instructions_text = instructions_text + \
                    "<li>" + instructions[i] + "</li>"
            output = output.replace("$instructions", instructions_text)

        else:  # Auto entry
            output = output.replace("$content", output_auto)
            conn = sql.connect(database)
            cur = conn.cursor()
            cur.execute("UPDATE general SET value=? WHERE key='add_name'", (name,))
            cur.execute("UPDATE general SET value=? WHERE key='add_description'", (description,))
            cur.execute("UPDATE general SET value=NULL WHERE key='add_mac'")
            conn.commit()
            conn.close()

        output = output.replace("$name", name)
        output = output.replace("$device_type", device_type)
        output = output.replace("$description", description)
        output = output.replace("$hostname", advised_ip)
        return(output.replace("$title_signin", config.signin_title))

    @cherrypy.expose
    def manual_add_device_stage_4(self, name="John Doe", mac="", description="unknown"):
        conn = sql.connect(database)
        cur = conn.cursor()
        output = """
<html><head><link rel="stylesheet" type="text/css" href="/static/css/manual.css"><link rel="stylesheet" type="text/css" href="/static/css/font.css">
<meta http-equiv="refresh" content="5; url=/manual_internal?func=info&name=$name" />
</head><body>
<div class="message">
$message
</div>
</body></html>
            """

        new_mac = mac.lower()
        new_mac = new_mac.replace("-", ":")

        cur.execute("UPDATE general SET value=NULL WHERE key='add_name'")
        cur.execute("UPDATE general SET value=NULL WHERE key='add_description'")
        cur.execute("UPDATE general SET value=NULL WHERE key='add_mac'")
        try:
            cur.execute("INSERT INTO devices(name,mac,description,reliable) VALUES (?,?,?,1)",
                        (name, new_mac, description))
        except:
            output = output.replace(
                "$message", "This device is already registered in the system.<br><br>This may mean that we have decided this device is unreliable.")
        else:
            output = output.replace("$message", "Your device has been added!")

        conn.commit()
        conn.close()

        return(output.replace("$name", name).replace("$title_signin", config.signin_title))

    @cherrypy.expose
    def manual_wait_for_mac(self):
        conn = sql.connect(database)
        cur = conn.cursor()

        output = """
<html><head><link rel="stylesheet" type="text/css" href="/static/css/manual.css"><link rel="stylesheet" type="text/css" href="/static/css/font.css"><base target="_parent"></head><body>
<div class="message">
$content
</div>
</body></html>
        """

        output_waiting = """
Waiting...
        """

        output_finished = """
Your device is almost ready to be tracked.
<form method="post" action="/manual_add_device_stage_4">
<input type="hidden" name="name" value="$name">
<input type="hidden" name="mac" value="$mac">
<input type="hidden" name="description" value="$description">
<br><button type="submit">Finish</button>
</form>
        """

        add_name = cur.execute("SELECT value FROM general WHERE key='add_name'").fetchall()[0][0]
        add_description = cur.execute("SELECT value FROM general WHERE key='add_description'").fetchall()[0][0]
        add_mac = cur.execute("SELECT value FROM general WHERE key='add_mac'").fetchall()[0][0]
        if add_name == None or add_mac == None:
            output = output.replace("$content", output_waiting)
        else:
            output = output.replace("$content", output_finished)
            output = output.replace("$name", add_name)
            output = output.replace("$description", add_description)
            output = output.replace("$mac", add_mac)

        return(output)

    @cherrypy.expose
    def add(self):
        conn = sql.connect(database)
        cur = conn.cursor()
        output = """
<html><head><title>$title_signin</title><link rel="stylesheet" type="text/css" href="/static/css/manual.css"><link rel="stylesheet" type="text/css" href="/static/css/font.css"></head><body>
<div class="message">$message</div>
</body></html>
        """

        def get_mac():
            arp_output = subprocess.run(
                ["arp", cherrypy.request.remote.ip], stdout=subprocess.PIPE).stdout.decode('utf-8')
            arp_output = arp_output.split("\n")
            if len(arp_output) < 2:
                return("failure")
            arp_output = arp_output[1][33:50]
            if len(arp_output) == 0:
                return("failure")
            return(arp_output)

        mac = get_mac()
        add_name = cur.execute("SELECT value FROM general WHERE key='add_name'").fetchall()[0][0]
        add_mac = cur.execute("SELECT value FROM general WHERE key='add_mac'").fetchall()[0][0]
        if add_name == None or mac == "failure":
            output = output.replace("$message", "Something has gone wrong!<br><br>Please click I can't do that")
        else:
            cur.execute("UPDATE general SET value=? WHERE key='add_mac'", (mac,))
            output = output.replace("$message", "Excellent! Please continue on the attendance screen.")

        conn.commit()
        conn.close()
        return(output.replace("$title_signin", config.signin_title))

    @cherrypy.expose
    def peoplelist(self, sort_first='0'):
        conn = sql.connect(database)
        cur = conn.cursor()
        output = """
<html><head><title>People - $title</title><link rel="stylesheet" type="text/css" href="/static/css/admin.css"></head><body>
<a href="/">< Return</a><br><br>

<form method="post" action="/peoplelist_add">
<input name="name" type="text"><button type="submit">Add person</button>
</form>

<h3>$peoplecount People:</h3>
Sort by <a href="/peoplelist?sort_first=1">first name</a> <a href="/peoplelist">last name</a><br><br>
<div style="line-height: 2em;">$peoplelistHtml</div>

</body></html>
        """

        # Get list of names
        cur.execute("SELECT name FROM people")
        names = order_names(cur.fetchall(), by_first=(sort_first == '1'))

        # Set people count
        output = output.replace("$peoplecount", str(len(names)))

        # Create html
        peoplelist_html = ""
        for i in range(0, len(names)):
            # Get devices
            cur.execute(
                "SELECT description FROM devices WHERE name=? ORDER BY description", (names[i],))
            devices = cur.fetchall()
            if len(devices) == 0:
                devices_text = "no devices"
            else:
                devices_text = ""
                for f in range(0, len(devices)):
                    if devices[f][0] == None:
                        description = "unknown"
                    else:
                        description = devices[f][0]
                    devices_text = devices_text + description + ", "
                devices_text = devices_text[:-2]

            # Get categories
            cur.execute(
                "SELECT category FROM categories WHERE name=? ORDER BY category", (names[i],))
            categories = cur.fetchall()
            if len(categories) == 0:
                categories_text = "no categories"
            else:
                categories_text = ""
                for f in range(0, len(categories)):
                    categories_text = categories_text + categories[f][0] + ", "
                categories_text = categories_text[:-2]
            peoplelist_html = peoplelist_html + "<a style=\"color: black; font-weight: bold; text-decoration: none;\" href=\"/person/" + \
                names[i] + "\">" + names[i] + \
                "</a> <i>(" + devices_text + "), (" + \
                categories_text + ")</i><br>"
        output = output.replace("$peoplelistHtml", peoplelist_html)

        conn.close()
        return(output.replace("$title", config.admin_title))

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
<html><head><title>$name - $title</title><link rel="stylesheet" type="text/css" href="/static/css/admin.css"></head><body>
<a href="/peoplelist">< Return</a><br><br>

<h2>$name</h2>
<h3>General</h3>
<form method="post" action="/person_rename">
<input name="old_name" type="hidden" value="$name">
<input name="new_name" type="text"><button type="submit">Rename</button>
</form>

<form method="post" action="/person_remove">
<input name="name" type="hidden" value="$name"><button type="submit">Remove Person</button>
</form>

<h3>Categories</h3>
<form method="post" action="/person_add_category">
<input type="hidden" value="$name" name="name">
<select name="category">$selectionHtml</select>
<button type="submit">Add Category</button>
</form>
<div style="line-height: 1.5em;">$categoriesHtml</div>

<h3>Devices</h3>
<a href="/manual_add_device_stage_1?name=$name" target="_blank">Add Device</a><br><br>
<div style="line-height: 1.5em;">$devicesHtml</div>

</body></html>
        """
        output = output.replace("$name", name)

        # Generate category selection
        cur.execute("SELECT name FROM possible_categories")
        possible_categories = cur.fetchall()
        for i in range(0, len(possible_categories)):
            possible_categories[i] = possible_categories[i][0]
        temp_selection_html = ""
        for i in range(0, len(possible_categories)):
            temp_selection_html = temp_selection_html + "<option value=\"" + \
                possible_categories[i] + "\">" + \
                possible_categories[i] + "</option>"
        output = output.replace("$selectionHtml", temp_selection_html)

        # Get devices
        cur.execute(
            "SELECT id,description,reliable FROM devices WHERE name=?", (name,))
        devices = cur.fetchall()

        # Generate devices html
        devices_html = ""
        for i in range(0, len(devices)):
            if devices[i][2] == 1:
                toggle_text = "Mark as unreliable"
            else:
                toggle_text = "Mark as reliable"
            if devices[i][1] == None:
                description = "unknown"
            else:
                description = devices[i][1]
            devices_html = devices_html + "<i>" + description + "</i>"
            devices_html = devices_html + " - <a href=\"/person_toggle_reliable/" + \
                str(devices[i][0]) + "\">" + toggle_text + "</a>"
            devices_html = devices_html + " - <a href=\"/person_removeDevice/" + \
                str(devices[i][0]) + "\">Remove device</a><br>"
        output = output.replace("$devicesHtml", devices_html)

        # Get categories
        cur.execute("SELECT category FROM categories WHERE name=?", (name,))
        categories = cur.fetchall()
        for i in range(0, len(categories)):
            categories[i] = categories[i][0]

        # Generate categories html
        categories_html = ""
        for i in range(0, len(categories)):
            categories_html = categories_html + "<i>" + categories[i] + "</i>"
            categories_html = categories_html + " - <a href=\"/person_remove_category?name=" + \
                name + "&category=" + \
                categories[i] + "\">Remove category</a><br>"
        output = output.replace("$categoriesHtml", categories_html)

        conn.close()
        return(output.replace("$title", config.admin_title))

    @cherrypy.expose
    def person_rename(self, old_name="John Doe", new_name="John Doe"):
        conn = sql.connect(database)
        cur = conn.cursor()

        cur.execute("UPDATE people SET name=? WHERE name=?",
                    (new_name, old_name))
        cur.execute("UPDATE devices SET name=? WHERE name=?",
                    (new_name, old_name))
        cur.execute("UPDATE history_cache SET name=? WHERE name=?",
                    (new_name, old_name))
        cur.execute("UPDATE categories SET name=? WHERE name=?",
                    (new_name, old_name))
        add_name = cur.execute("SELECT value FROM general WHERE key='add_name'").fetchall()[0][0]
        if add_name == old_name:
            cur.execute("UPDATE general SET value=? WHERE key='add_name'", (new_name,))

        conn.commit()
        conn.close()

        log_conn = sql.connect(log_database)
        log_cur = conn.cursor()

        cur.execute("UPDATE lookup SET value=? WHERE value=?",
                    (new_name, old_name))

        log_conn.commit()
        log_cur.close()

        output = """<meta http-equiv="refresh" content="0; url=/person/$name" />"""
        output = output.replace("$name", new_name)
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
    def person_add_category(self, name="John Doe", category=""):
        conn = sql.connect(database)
        cur = conn.cursor()

        cur.execute(
            "INSERT INTO categories(name,category) VALUES (?,?)", (name, category))

        output = """<meta http-equiv="refresh" content="0; url=/person/$name" />"""
        output = output.replace("$name", name)

        conn.commit()
        conn.close()
        return(output)

    @cherrypy.expose
    def person_remove_category(self, name="John Doe", category=""):
        conn = sql.connect(database)
        cur = conn.cursor()

        cur.execute(
            "DELETE FROM categories WHERE name=? AND category=?", (name, category))

        output = """<meta http-equiv="refresh" content="0; url=/person/$name" />"""
        output = output.replace("$name", name)

        conn.commit()
        conn.close()
        return(output)

    @cherrypy.expose
    def person_toggle_reliable(self, id=-1):
        conn = sql.connect(database)
        cur = conn.cursor()

        cur.execute("SELECT reliable FROM devices WHERE id=?", (id,))
        data = cur.fetchall()
        if len(data) > 0:
            if data[0][0] == 0:
                new_value = 1
            else:
                new_value = 0
            cur.execute("UPDATE devices SET reliable=? WHERE id=?",
                        (new_value, id))

        output = """<meta http-equiv="refresh" content="0; url=/person/$name" />"""

        # Find name
        cur.execute("SELECT name FROM devices WHERE id=?", (id,))
        output = output.replace("$name", cur.fetchall()[0][0])

        conn.commit()
        conn.close()
        return(output)

    @cherrypy.expose
    def person_remove_device(self, id=-1):
        conn = sql.connect(database)
        cur = conn.cursor()

        # Find name
        cur.execute("SELECT name FROM devices WHERE id=?", (id,))
        name = cur.fetchall()[0][0]

        cur.execute("DELETE FROM devices WHERE id=?", (id,))

        output = """<meta http-equiv="refresh" content="0; url=/person/$name" />"""
        output = output.replace("$name", name)

        conn.commit()
        conn.close()
        return(output)

    @cherrypy.expose
    def manual_display_type(self):
        conn = sql.connect(database)
        cur = conn.cursor()

        cur.execute("SELECT value FROM general WHERE key='pure_slideshow'")
        output = str(cur.fetchall()[0][0])

        conn.close()
        return(output)


def error_page(status, message, traceback, version):
    output = """
<html><head><title>Error - $title</title></head><body>
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
    return(output.replace("$title", config.admin_title))

clients = []
def send_complete(request_id):
    for client in clients:
        client.send_message(str(request_id))
        cherrypy.log("Sent data '" + str(request_id) + "' to " + client.address[0])

class status_server(WebSocket):
    global clients
    
    def handle(self):
        cherrypy.log("Received data '" + self.data + "' from " + self.address[0])

    def connected(self):
        cherrypy.log("Socket opened from " + self.address[0])
        clients.append(self)
    
    def handle_close(self):
        cherrypy.log("Socket closed to " + self.address[0])
        clients.remove(self)

def run_status_server():
    server = WebSocketServer(config.web_host, config.web_socket_port, status_server)
    cherrypy.log("Starting web socket server on ws://" + config.web_host + ":" + str(config.web_socket_port))
    server.serve_forever()
    cherrypy.log("Stopping web socket server on ws://" + config.web_host + ":" + str(config.web_socket_port))
    
def slack_poster():
    while not recordkeeper.get_liveready():
        time.sleep(1)
    cherrypy.log("Live data ready, starting slack poster")
    while True:
        old_live = [x["name"] for x in recordkeeper.get_livecache()]
        time.sleep(1)
        new_live = [x["name"] for x in recordkeeper.get_livecache()]
        if new_live != old_live:
            for old_name in old_live:
                if old_name not in new_live:
                    slack_post(old_name + " left at " + time.strftime("%-I:%M %p on %a %-m/%-d"))
            for new_name in new_live:
                if new_name not in old_live:
                    slack_post(new_name + " arrived at " + time.strftime("%-I:%M %p on %a %-m/%-d"))

if __name__ == "__main__":
    recordkeeper.start_live_server()
    server_thread = threading.Thread(target=run_status_server, daemon=True)
    server_thread.start()
    if config.enable_slack:
    	slack_thread = threading.Thread(target=slack_poster, daemon=True)
    	slack_thread.start()
    cherrypy.config.update({'server.socket_port': config.web_port, 'server.host': config.web_host,
                            'error_page.500': error_page, 'error_page.404': error_page})
    cherrypy.quickstart(main_server(), "/", {"/": {"log.access_file": config.data + "/logs/serverlog.log", "log.error_file": "", "tools.sessions.on": True, "tools.sessions.timeout": 30}, "/static": {
                        "tools.staticdir.on": True, "tools.staticdir.dir": config.repo + "/static"}, "/favicon.ico": {"tools.staticfile.on": True, "tools.staticfile.filename": config.repo + "/static/img/favicon.ico"}})
