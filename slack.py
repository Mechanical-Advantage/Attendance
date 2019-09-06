import requests

webhook_url = open("/home/attendance/Attendance_data/slack_url.txt", "r").read()
def post(message):
	requests.post(webhook_url, json={"text": message})
