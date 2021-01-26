#!/usr/bin/env python3

# Derived from:
# https://github.com/waveform80/picamera/blob/release-1.13/docs/examples/web_streaming.py
# 
# Copyright 2021 Chris Derossi <chris@makermusings.com>
# 
# Copyright 2013-2015 Dave Jones <dave@waveform.org.uk>
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the copyright holder nor the
#       names of its contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.


import io
import picamera
import logging
import socketserver
from threading import Condition
from http import server

PAGE="""\
<html>
<head>
<title>picamera MJPEG streaming demo</title>
<style>
    body {
        background-color: #094b86;
    }
    label {
        xcolor: white;
        margin-left: 2em;
    }
    .container { 
        position: relative;
        width: 640px;
        margin: auto;
        color: white;
    }
    .width1024 {
        width: 1024px;
    }
    .vline {
        background-color: red;
        width: 0.2px;
        height: 480px;
        position: absolute;
        top: 0;
        left: 320;
    }
    .vline1024 {
        height: 768px;
        left: 512;
    }
    .hline {
        background-color: red;
        width: 640px;
        height: 0.2px;
        position: absolute;
        top: 240;
        left: 0;
    }
    .hline1024 {
        width: 1024;
        top: 384;
    }
    .hidden {
        display: none;
    }
    .fov {
        margin-top: 1em;
    }
    .fov input {
        width: 4em;
    }
    .fovanswer {
        margin-top: 1em;
        font-size: 150%;
    }
    input::-webkit-outer-spin-button,
    input::-webkit-inner-spin-button {
      -webkit-appearance: none;
      margin: 0;
    }
    input[type=number] {
      -moz-appearance: textfield;
    }
</style>
<script>
    var resolution = "640"

    function checkCrosshairs()
    {
        var checkbox = document.getElementById('crosshairs')
        if (checkbox.checked)
        {
            document.getElementById('vline').classList.remove('hidden')
            document.getElementById('hline').classList.remove('hidden')
        }
        else
        {
            document.getElementById('vline').classList.add('hidden')
            document.getElementById('hline').classList.add('hidden')
        }
    }

    function checkFOV()
    {
        var distance = parseFloat(document.getElementById('distance').value)
        var visible = parseFloat(document.getElementById('visible').value)
        if (distance > 0 && visible > 0)
        {
            var angle = Math.atan((visible / 2) / distance) * 2 * 180 / Math.PI
            document.getElementById('fovvalue').innerText = "" + angle.toFixed(2)
            document.getElementById('fovanswer').classList.remove('hidden')
        }
        else
        {
                document.getElementById('fovanswer').classList.add('hidden')
        }
    }

    function changeResolution()
    {
        var selector = document.getElementById('resolution')
        if (selector.value != resolution)
        {
            resolution = selector.value
            var videoImg = document.getElementById('video')
            videoImg.src = ""
            if (resolution == "640")
            {
                document.getElementById('vline').classList.remove('vline1024')
                document.getElementById('hline').classList.remove('hline1024')
                document.getElementById('container').classList.remove('width1024')
            }
            else
            {
                document.getElementById('vline').classList.add('vline1024')
                document.getElementById('hline').classList.add('hline1024')
                document.getElementById('container').classList.add('width1024')
            }
            setTimeout(() => {
                videoImg.src = "stream" + resolution + ".mjpg"
            }, 100)
        }
    }
</script>
</head>
<body>
    <div id="container" class="container">
        <img id="video" class="camvideo" src="stream640.mjpg" />
        <div class="controls">
            <label for="resolution">Resolution:</label>
            <select id="resolution" onchange="changeResolution()">
                <option value="640">640 x 480</option>
                <option value="1024">1024 x 768</option>
            </select>

            <label for="crosshairs">Show Crosshairs:</label>
            <input type="checkbox" id="crosshairs" onclick="checkCrosshairs()"/>
        </div>
        <div class="fov">
            <div>
                <label for="distance">Distance to lens:</label>
                <input id="distance" type="number" oninput="checkFOV()"/>
            </div>
            <div>
                <label for="visible">Total visible length:</label>
                <input id="visible" type="number" oninput="checkFOV()"/>
            </div>
            <div class="fovanswer hidden" id="fovanswer">
                <label>Field of view:</label>
                <span id="fovvalue"></span>&deg;
            </div>
        </div>
        <div id="vline" class="vline hidden"></div>
        <div id="hline" class="hline hidden"></div>
    </div>
</body>
</html>
"""

class StreamingOutput(object):
    def __init__(self):
        self.frame = None
        self.buffer = io.BytesIO()
        self.condition = Condition()
        self.first = True

    def write(self, buf):
        if buf.startswith(b'\xff\xd8'):
            # New frame, copy the existing buffer's content and notify all
            # clients it's available
            self.buffer.truncate()
            with self.condition:
                self.frame = self.buffer.getvalue()
                if self.first:
                    self.first = False
                else:
                    self.condition.notify_all()
            self.buffer.seek(0)
        return self.buffer.write(buf)

class StreamingHandler(server.BaseHTTPRequestHandler):
    def stream_common(self):
        self.send_response(200)
        self.send_header('Age', 0)
        self.send_header('Cache-Control', 'no-cache, private')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
        self.end_headers()
        try:
            while True:
                with self.output.condition:
                    self.output.condition.wait()
                    frame = self.output.frame
                self.wfile.write(b'--FRAME\r\n')
                self.send_header('Content-Type', 'image/jpeg')
                self.send_header('Content-Length', len(frame))
                self.end_headers()
                self.wfile.write(frame)
                self.wfile.write(b'\r\n')
        except Exception as e:
            self.camera.stop_recording()
            self.camera.close()
            logging.warning(
                'Removed streaming client %s: %s',
                self.client_address, str(e))

    def do_GET(self):
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
        elif self.path == '/index.html':
            content = PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == '/stream640.mjpg':
            self.output = StreamingOutput()
            self.camera = picamera.PiCamera(resolution='640x480', framerate=24)
            self.camera.start_recording(self.output, format='mjpeg')
            self.stream_common()
        elif self.path == '/stream1024.mjpg':
            self.output = StreamingOutput()
            self.camera = picamera.PiCamera(resolution='1024x768', framerate=24)
            self.camera.start_recording(self.output, format='mjpeg')
            self.stream_common()
        else:
            self.send_error(404)
            self.end_headers()

class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

address = ('', 8000)
httpd = StreamingServer(address, StreamingHandler)
httpd.serve_forever()

# vim: set ts=4 sw=4 expandtab:

