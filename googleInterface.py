import gspread
from oauth2client.service_account import ServiceAccountCredentials
import sqlite3 as sql
from operator import itemgetter
from datetime import datetime

cred_path = "/home/jaw99/Attendance_data/googleCredentials.json"
spreadsheet_name = "6328 Attendance"
database_path = "/home/jaw99/Attendance_data/attendance.db"

#Connect to sheet
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
try:
    creds = ServiceAccountCredentials.from_json_keyfile_name(cred_path, scope)
except:
    print('Failed to parse credentials for Google Sheet from file "' + cred_path + '"')
    exit(1)

try:
    client = gspread.authorize(creds)
except:
    print('Failed to authorize for Google Sheet with credentials from file "' + cred_path + '"')
    exit(1)

try:
    spreadsheet = client.open(spreadsheet_name)
except gspread.exceptions.SpreadsheetNotFound:
    print('Failed to open Google Sheet. Please share a spreadsheet titled "' + spreadsheet_name + '" to the address "' + creds.service_account_email + '"')
    exit(1)

worksheet = spreadsheet.get_worksheet(0)

#Connect to database
try:
    conn = sql.connect(database_path)
except:
    print('Failed to open database "' + database_path + '"')
    exit(1)
cur = conn.cursor()

def updateSpreadsheet():
    #Get people here from database
    cur.execute("SELECT name FROM live ORDER BY name")
    live = cur.fetchall()
    for i in range(len(live)):
        live[i] = live[i][0]

    #Get needed range from sheet
    currentPeopleHere = worksheet.col_values(1)
    lastRow = len(currentPeopleHere)
    if len(live) + 1 > lastRow:
        lastRow = len(live) + 1
    currentPeopleHere = worksheet.range(1, 1, lastRow, 1)
    del currentPeopleHere[0]

    #Extend live data
    while len(live) < len(currentPeopleHere):
        live.append("")

    #Update cells
    for i in range(len(currentPeopleHere)):
        currentPeopleHere[i].value = live[i]
    try:
        worksheet.update_cells(currentPeopleHere)
    except:
        print("Failed to update spreadsheet. Does the client have write permissions?")
        return

    #Get recent updates from database
    updateList = []
    cur.execute("SELECT name,timeIn FROM history")
    timeInList = cur.fetchall()
    for i in range(len(timeInList)):
        updateList.append({"name": timeInList[i][0], "time": timeInList[i][1], "descr": "signed in"})
    cur.execute("SELECT name,timeOut FROM history")
    timeOutList = cur.fetchall()
    for i in range(len(timeOutList)):
        if timeOutList[i][1] > 0:
            updateList.append({"name": timeOutList[i][0], "time": timeOutList[i][1], "descr": "signed out"})
    updateList = sorted(updateList, key=itemgetter("time"), reverse=True)
    for i in range(len(updateList)):
        updateList[i]["time"] = datetime.fromtimestamp(updateList[i]["time"]).strftime("%a %-m/%-d at %-I:%M %p")

    #Update history range
    cells = worksheet.range("B2:D26")
    for i in range(len(cells)):
        if cells[i].col == 2:
            cells[i].value = updateList[cells[i].row - 2]["name"]
        elif cells[i].col == 3:
            cells[i].value = updateList[cells[i].row - 2]["descr"]
        elif cells[i].col == 4:
            cells[i].value = updateList[cells[i].row - 2]["time"]
    worksheet.update_cells(cells)

    #Update "last update" cell
    worksheet.update_acell("E2", datetime.now().strftime("%a %-m/%-d at %-I:%M %p"))
