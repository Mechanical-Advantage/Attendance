var socket = new WebSocket("ws://" + window.location.hostname + ":8001")
socket.onmessage = function(event) {
    if (event.data == "1") {
        socket.close()
        window.location = "/show_records?request_id=" + requestId.toString()
    }
}
function checkStatus() {
    socket.send(requestId)
}
setInterval(function() {checkStatus()}, 50)

const funnyTexts = ["The robots are hard at work!",
                    "Searching for the missing clue...",
                    "Sorting through the files...",
                    "Connecting the clues...",
                    "Everything is about to become clear...",
                    "We've got our nose to the grindstone!",
                    "The pressure is building!",
                    "We're almost ready to take flight!",
                    "The sandstorm is approaching!",
                    "Don't worry - a few bits tried to escape, but we caught them.",
                    "While the satellite moves into position...",
                    "The bits are flowing slowly today...",
                    "We're making you a cookie...",
                    "Contacting the attendance ghost...",
                    "Calculating social security numbers...",
                    "Adjusting flux capacitor...",
                    "99 bottles of lubricant on the wall...",
                    "Computing the secret to life, the universe, and everything...",
                    "May the forks be with you.",
                    "The parts are being milled...",
                    "The flywheel is being spun up...",
                    "Shoveling coal into the server...",
                    "While we drown in a sea of MAC addresses.",
                    "Unlocking the attendance vault...",
                    "While the robots do all the work.",
                    "Sacrificing a resistor to the machine gods...",
                    "The efficiency of robots is limited.",
                    "Preparing to power up!",
                    "Motion profiling to victory...",
                    "Installing hatch panels...",
                    "Loading cargo for takeoff...",
                    "The attendance elves are hard at work.",
                    "SoH mIS. qatlh yIv? qatlh mughwI' lo'?",
                    "Averaging the median deviation...",
                    "Accelerating to 88 mph...",
                    "Doing the macarena...",
                    "Generating random data...",
                    "Tuning PID...",
                    "Banishing evil wizards...",
                    "Dividing by zero...",
                    "Consuming spagetti code...",
                    "Running in the pits...",
                    "Searching for aluminum magnets...",
                    "Adjusting aluminum magnets...",
                    "Pay no attention to the robot behind the curtain.",
                    "Deploying the spork...",
                    "Bag day? Where we're going, we don't need bag day!",
                    "Toto, I've got a feeling we're not in open loop anymore.",
                    "\"Open the pod bay doors, Bot-Bot.\"",
                    "The data hung in the sky in much the same way that bricks don't.",
                    "So long and thanks for all the data.",
                    "You keep using those words. I do not think they mean what you think they mean.",
                    "Real data is the best thing in the world, except for cough drops.",
                    "Anybody want a peanut?",
                    "Never go in against an attendance system when death is on the line.",
                    "Harry -- yer a robot wizard.",
                    "\"Inconceivable!\"",
                    "But why? The answer is 42."]

function writeText() {
    var text = funnyTexts[Math.floor(Math.random()*funnyTexts.length)]
    document.getElementById("funnyText").innerHTML = text
}
writeText()

var canvas = document.getElementById("loadingCanvas")
var context = canvas.getContext("2d")
var loadingImage = document.getElementById("loadingImage")
function whenLoaded() {
    var clipHeight = loadingImage.height
    var clipWidth = (canvas.width / canvas.height) * loadingImage.height
    
    function drawFrame() {
        var time = new Date().getTime() / 1000
        position = (time - startTime) * 500 // pixels per second
        position = position % (loadingImage.width * (2/3))
        var xPos = loadingImage.width - clipWidth - position
        context.clearRect(0, 0, canvas.width, canvas.height)
        context.drawImage(loadingImage, xPos, 0, clipWidth, clipHeight, 0, 0, canvas.width, canvas.height)
    }
    var startTime = new Date().getTime() / 1000
    setInterval(function() {drawFrame()}, 20)
}

loadingImage.onload = function() {
    whenLoaded()
}
if (loadingImage.complete) {
    whenLoaded()
}
