//Config
const serverAddress = "http://192.168.2.237:8080"

cycleCount = -1
lastUpdateRaw = 0
lastUpdateKnown = false
notLoaded = true
function reloadLastUpdate() {
  //Change cycle count
  cycleCount += 1
  if (cycleCount > 4) {
    cycleCount = 0
  }

  //Get last update time if neccessary
  if (cycleCount == 0) {
    const http = new XMLHttpRequest()

    http.onreadystatechange = function() {
      if (this.readyState == 4) {
        notLoaded = false
        if (this.status == 200) {
          lastUpdateRaw = Number(this.responseText)
          lastUpdateKnown = true
        } else {
          lastUpdateKnown = false
        }
      }
    }

    http.open("GET", serverAddress + "/lastUpdate")
    http.send()
  }

  currentTime = Math.floor(Date.now() / 1000)
  duration = currentTime - lastUpdateRaw
  hours = Math.floor(duration/3600)
  duration -= hours*3600
  minutes = Math.floor(duration/60)
  seconds = duration - minutes*60

  formatted = ""
  if (hours != 0) {
    formatted = String(hours) + "h "
  }
  if (minutes != 0) {
    formatted = formatted + String(minutes) + "m "
  }
  if (seconds != 0) {
    formatted = formatted + String(seconds) + "s "
  }
  formatted = formatted.substring(0, formatted.length - 1);
  if (formatted == "") {
    formatted = "0s"
  }

  if (lastUpdateKnown) {
    output = "Last known update was " + formatted + " ago"
  } else if (notLoaded) {
    output = "Loading..."
  } else {
    output = "Cannot connect to server"
  }

  document.getElementById("lastUpdate").innerHTML = output
}
