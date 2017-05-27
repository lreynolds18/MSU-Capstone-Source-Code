import time
import RPi.GPIO as GPIO, time
import sys

#sets up GPIO pins, then sends signal
#used to activate turnouts

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

pin = int(sys.argv[1])

GPIO.setup(pin, GPIO.OUT)
try:
    #sets off turnout, waits a little to make sure it's changed, then sets back to low to not melt the turnout
    GPIO.output(pin, GPIO.HIGH)
    time.sleep(0.3)
    GPIO.output(pin, GPIO.LOW)
except KeyboardInterrupt:
    #Do it anyway, prevent KeyboardInterrupt from TrainLocationProgram from melting a turnout
    GPIO.output(pin, GPIO.HIGH)
    time.sleep(0.3)
    GPIO.output(pin, GPIO.LOW)
