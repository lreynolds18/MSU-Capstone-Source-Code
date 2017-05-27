import RPi.GPIO as GPIO
import time

pins = [21,20,5,7,16,12,26,19,13,6]

# Script to initialize all of the relay pins to first high, and then low. This is used to make sure all relays are working correctly.
# This script is also the one that is run when the pi starts up. (Might need to change the file path in /etc/rc.local so that
# it points to the correct file
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
for pin in pins:   
    GPIO.setup(pin, GPIO.OUT)

    GPIO.output(pin, GPIO.HIGH)
    time.sleep(0.3)
    GPIO.output(pin, GPIO.LOW)
    time.sleep(0.3)
