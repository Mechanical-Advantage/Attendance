//Config
const displayLength = 10000
const maxOpacity = 0.7
const imageSelector1 = ".slideshow1"
const imageSelector2 = ".slideshow2"

var currentMaxOpacity = maxOpacity
var startTime = Date.now()
var currentImage = 1
var image1 = document.querySelector(imageSelector1)
var image2 = document.querySelector(imageSelector2)

function advance(images) {
  const timePassed = Date.now() - startTime

  const image1_slide = (Math.floor((timePassed+(displayLength*0.5))/(displayLength*2))*2 + 1) % images.length
  if (image1.src != images[image1_slide]) {
    image1.style.backgroundImage = "url('/static/backgrounds/" + images[image1_slide] + "')"
  }

  const image2_slide = (Math.floor((timePassed+(displayLength*1.5))/(displayLength*2))*2) % images.length
  if (image2.src != images[image2_slide]) {
    image2.style.backgroundImage = "url('/static/backgrounds/" + images[image2_slide] + "')"
  }

  correctCurrentImage = (Math.floor(timePassed/displayLength) % 2) + 1
  if (correctCurrentImage != currentImage) {
    currentImage = correctCurrentImage
    if ((currentImage) == 1) {
      image1.style.opacity = currentMaxOpacity
      image2.style.opacity = 0
    } else {
      image1.style.opacity = 0
      image2.style.opacity = currentMaxOpacity
    }
  }
}

function updateDisplayType() {
  const http = new XMLHttpRequest()

  http.onreadystatechange = function() {
    if (this.readyState == 4 && this.status == 200) {
      var mainDiv = document.querySelector(".aboveSlideshow")
      var linkblocker = document.querySelector(".linkblocker")

      if (this.responseText == "0") {
        currentMaxOpacity = maxOpacity
        mainDiv.style.opacity = 1
        linkblocker.style.display = "none"

      } else {
        currentMaxOpacity = 1
        mainDiv.style.opacity = 0
        linkblocker.style.display = "initial"

      }
      if ((currentImage) == 1) {
        image1.style.opacity = currentMaxOpacity
        image2.style.opacity = 0
      } else {
        image1.style.opacity = 0
        image2.style.opacity = currentMaxOpacity
      }
    }
  }

  http.open("GET", "/manual_displayType")
  http.send()
}
