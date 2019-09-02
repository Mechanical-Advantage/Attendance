import requests

webhook_url = "https://hooks.slack.com/services/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"
def post(message):
	requests.post(webhook_url, json={"text": message})
