# picam_util
Web streaming utility for the Raspberry Pi camera.

Based on the web streaming recipe in the picamera docs at https://picamera.readthedocs.io/en/release-1.13/recipes2.html#web-streaming.

# Installation

* Assuming you're using a standard version of Raspbian OS, you should have the Python picamera module installed by default. If not, see https://picamera.readthedocs.io/en/release-1.13/install.html.
* Enable the camera using `raspi-config`.
* Save the file `web_streaming.py` somewhere and make it executable with `chmod +x web_streaming.py`.

# Usage

* On the Raspberry Pi, start the streaming server: `./web_streaming.py`
* In your browser, navigate to `http://<pi-name-or-ip-address>:8000/`

![screenshot](/screenshot.png)

* Use the dropdown to select 640x480 or 1024x768 resolution. **Note:** Since this utility controls the camera, it is not meant to support multiple simultaneous browser clients.
* Show or hide center crosshairs with the checkbox.
* To calculate actual or required field of view (FOV):
  * enter the distance from the lens to the object being viewed. (The simple chart shown in the screenshot to help with focus and FOV measurements is included in this repository.)
  * enter the total length, horizontally, vertically, or diagonally that you can see/want to be able to see
  * the calculated FOV will be shown in degrees

