#!/usr/bin/env python3

import cv2
import matplotlib.pyplot as plt
from scipy.signal import butter, lfilter
from PIL import Image
import threading
from http import server
import socketserver
import io
import time
import socket

capture=None

# Declare buffer size for reading from TCP command socket
COMMAND_BUFFER_SIZE = 1024

# Declare buffer size for reading from TCP waveform socket.
WAVEFORM_BUFFER_SIZE = 181420

#Bandpass filter settings
ORDER = 3
LOW_CUTOFF = 300
HIGH_CUTOFF = 7000

#Data plot settings
TIME_RANGE = 30 #seconds

PAGE="""
<html>
<head>
<title>Electrophys streaming demo</title>
<style>
    body {
	width: 100%;
	margin: 10 0 10 0;
    }

    h1{
        margin: auto;
        margin-bottom: 20px;
        text-align: center;
    }
	
    .container {
        margin: auto;
	display: flex;
	flex-flow: row wrap;
	justify-content: center;
    }

    .camera {
	max-width: 640px;
	width: 100%;
    }

    .data {
	max-width: 960px;
	width: 100%;
    }
    
</style>
<script>
    var channel = "a-010"
    
    function changeChannel()
    {
        var selector = document.getElementById('channels')
        if (selector.value != channel)
        {
            channel = selector.value
            var data = document.getElementById('data')
            data.src = ""

            setTimeout(() => {
                data.src = channel + "_data.mjpg"
            }, 100)
        }
    }
</script>
</head>
<body>
<h1>Live Locust Behavior Demo</h1>
<div class="container">
    <div>
    	<img src="cam.mjpg" class="camera"/>
    </div>
    <img src="a-010_data.mjpg" id="data" class="data"/>
</div>
<div class="controls">
    <label for="channels">Channel:</label>
    <select id="channels" onchange="changeChannel()">
        <option value="a-000">A-000</option>
        <option value="a-001">A-001</option>
        <option value="a-002">A-002</option>
        <option value="a-003">A-003</option>
        <option value="a-004">A-004</option>
        <option value="a-005">A-005</option>
        <option value="a-006">A-006</option>
        <option value="a-007">A-007</option>
        <option value="a-008">A-008</option>
        <option value="a-009">A-009</option>
        <option value="a-010">A-010</option>
        <option value="a-011">A-011</option>
        <option value="a-012">A-012</option>
        <option value="a-013">A-013</option>
        <option value="a-014">A-014</option>
        <option value="a-015">A-015</option>
        <option value="a-016">A-016</option>
        <option value="a-017">A-017</option>
        <option value="a-018">A-018</option>
        <option value="a-019">A-019</option>
        <option value="a-020">A-020</option>
        <option value="a-021">A-021</option>
        <option value="a-022">A-022</option>
        <option value="a-023">A-023</option>
        <option value="a-024">A-024</option>
        <option value="a-025">A-025</option>
        <option value="a-026">A-026</option>
        <option value="a-027">A-027</option>
        <option value="a-028">A-028</option>
        <option value="a-029">A-029</option>
        <option value="a-030">A-030</option>
        <option value="a-031">A-031</option>
    </select>
</div>
</body>
</html>
"""

class CamHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.endswith('cam.mjpg'):
            self.send_response(200)
            self.send_header('Content-Type','multipart/x-mixed-replace; boundary=--jpgboundary')
            self.end_headers()
            while True:
                try:
                    rc,img = capture.read()
                    if not rc:
                        continue
                    imgRGB=cv2.cvtColor(img,cv2.COLOR_BGR2RGB)
                    jpg = Image.fromarray(imgRGB)
                    tmpFile = io.BytesIO()
                    jpg.save(tmpFile,'JPEG')
                    buffer = tmpFile.getvalue()
                    self.wfile.write(b'--jpgboundary\r\n')
                    self.send_header('Content-Type','image/jpeg')
                    self.send_header('Content-Length',str(len(buffer)))
                    self.end_headers()
                    self.wfile.write(buffer)
                    cv2.waitKey(1)
                except KeyboardInterrupt:
                    #print(e)
                    break
            return
        if self.path.endswith('data.mjpg'):
            channel = self.path[-15:-10]
            selectChannel(bytes(channel, "utf-8"))
            channel = channel.capitalize()
            #plt.clf()
            self.send_response(200)
            self.send_header('Content-Type','multipart/x-mixed-replace; boundary=--jpgboundary')
            self.end_headers()
            while True:
                try:
                    dataTmpFile = io.BytesIO()
                    timestamps = []
                    data = []
                    ReadWaveformData(timestamps, data)
                    min_time = int(timestamps[0] / TIME_RANGE) * TIME_RANGE
                    max_time = min_time + TIME_RANGE
                    data = lfilter(b, a, data)
                    plt.plot(timestamps, data, color='blue')
                    plt.title(channel + ' Amplifier Data')
                    plt.xlabel('Time (s)')
                    plt.ylabel('Voltage (uV)')
                    plt.xlim([min_time, max_time])
                    plt.savefig(dataTmpFile, format='jpg')
                    buffer = dataTmpFile.getvalue()
                    self.wfile.write(b'--jpgboundary\r\n')
                    self.send_header('Content-Type','image/jpeg')
                    self.send_header('Content-Length',str(len(buffer)))
                    self.end_headers()
                    self.wfile.write(buffer)
                    cv2.waitKey(1)
                except KeyboardInterrupt:
                    #print(e)
                    break
            return
        if self.path.endswith('.html'):
            content = PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type','text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
            return


class ThreadedHTTPServer(socketserver.ThreadingMixIn, server.HTTPServer):
    """Handle requests in a separate thread."""

def readUint32(array, arrayIndex):
    variableBytes = array[arrayIndex : arrayIndex + 4]
    variable = int.from_bytes(variableBytes, byteorder='little', signed=False)
    arrayIndex = arrayIndex + 4
    return variable, arrayIndex

def readInt32(array, arrayIndex):
    variableBytes = array[arrayIndex : arrayIndex + 4]
    variable = int.from_bytes(variableBytes, byteorder='little', signed=True)
    arrayIndex = arrayIndex + 4
    return variable, arrayIndex

def readUint16(array, arrayIndex):
    variableBytes = array[arrayIndex : arrayIndex + 2]
    variable = int.from_bytes(variableBytes, byteorder='little', signed=False)
    arrayIndex = arrayIndex + 2
    return variable, arrayIndex

def selectChannel(channel):
    # Clear TCP data output to ensure no TCP channels are enabled
    scommand.sendall(b'execute clearalldataoutputs')
    time.sleep(0.1)

    # Send TCP commands to set up TCP Data Output Enabled for wide
    # band of channel A-010
    scommand.sendall(b'set ' + channel + b'.tcpdataoutputenabled true')
    time.sleep(0.1)

def ReadWaveformData(timestamps, data):
    # Calculations for accurate parsing
    # At 30 kHz with 1 channel, 1 second of wideband waveform data (including magic number, timestamps, and amplifier data) is 181,420 bytes
    # N = (framesPerBlock * waveformBytesPerFrame + SizeOfMagicNumber) * NumBlocks where:
    # framesPerBlock = 128 ; standard data block size used by Intan
    # waveformBytesPerFrame = SizeOfTimestamp + SizeOfSample ; timestamp is a 4-byte (32-bit) int, and amplifier sample is a 2-byte (16-bit) unsigned int
    # SizeOfMagicNumber = 4; Magic number is a 4-byte (32-bit) unsigned int
    # NumBlocks = NumFrames / framesPerBlock ; At 30 kHz, 1 second of data has 30000 frames. NumBlocks must be an integer value, so round up to 235

    framesPerBlock = 128
    waveformBytesPerFrame = 4 + 2
    waveformBytesPerBlock = framesPerBlock * waveformBytesPerFrame + 4

    # Read waveform data
    rawData = swaveform.recv(WAVEFORM_BUFFER_SIZE)
    if len(rawData) % waveformBytesPerBlock != 0:
        raise Exception('An unexpected amount of data arrived that is not an integer multiple of the expected data size per block')
    numBlocks = int(len(rawData) / waveformBytesPerBlock)

    rawIndex = 0 # Index used to read the raw data that came in through the TCP socket
    #amplifierTimestamps = [] # List used to contain scaled timestamp values in seconds
    #amplifierData = [] # List used to contain scaled amplifier data in microVolts

    for block in range(numBlocks):
        # Expect 4 bytes to be TCP Magic Number as uint32.
        # If not what's expected, raise an exception.
        magicNumber, rawIndex = readUint32(rawData, rawIndex)
        if magicNumber != 0x2ef07a08:
            raise Exception('Error... magic number incorrect')

        # Each block should contain 128 frames of data - process each
        # of these one-by-one
        for frame in range(framesPerBlock):
            # Expect 4 bytes to be timestamp as int32.
            rawTimestamp, rawIndex = readInt32(rawData, rawIndex)

            # Multiply by 'timestep' to convert timestamp to seconds
            timestamps.append(rawTimestamp * timestep)

            # Expect 2 bytes of wideband data.
            rawSample, rawIndex = readUint16(rawData, rawIndex)
            
            # Scale this sample to convert to microVolts
            data.append(0.195 * (rawSample - 32768))

def main():
    global capture
    capture = cv2.VideoCapture(0)
    global img
    global scommand
    global swaveform
    global timestep
    global b
    global a

    # Connect to TCP command server - default home IP address at port 5000
    print('Connecting to TCP command server...')
    scommand = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    scommand.connect(('127.0.0.1', 5000))

    # Connect to TCP waveform server - default home IP address at port 5001
    print('Connecting to TCP waveform server...')
    swaveform = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    swaveform.connect(('127.0.0.1', 5001))

    # Query sample rate from RHX software
    scommand.sendall(b'get sampleratehertz')
    commandReturn = str(scommand.recv(COMMAND_BUFFER_SIZE), "utf-8")
    expectedReturnString = "Return: SampleRateHertz "
    if commandReturn.find(expectedReturnString) == -1: # Look for "Return: SampleRateHertz N" where N is the sample rate
        raise Exception('Unable to get sample rate from server')
    else:
        sampleRate = float(commandReturn[len(expectedReturnString):])
        
    nyq = 0.5*sampleRate
    low = LOW_CUTOFF / nyq
    high = HIGH_CUTOFF / nyq
    b, a = butter(ORDER, [low, high], btype='band')
    
    # Calculate timestep from sample rate
    timestep = 1 / sampleRate
        
    selectChannel(b'a-010')

    plt.rcParams['figure.figsize'] = [9.6, 4.8]
    
    try:
        httpd = ThreadedHTTPServer(('', 8000), CamHandler)
        print("server started")
        httpd.serve_forever()
    except KeyboardInterrupt:
        capture.release()
        httpd.socket.close()

if __name__ == '__main__':
    main()
