import string
import sys
import os
import time
import datetime
import GELight

#constants for keeping track of the light and time buffer between light changes so it doesn't flash like crazy
GREEN = 0
YELLOW = 1
RED = 2
WHITE = 3
TIME_BUFFER = 1.0

class lightHandler:
    def __init__(self, debug):
	#sets up the light and initializes to green
        self.color = GREEN
	self.light = GELight.GELight()
	self.light.setGreen()
        self.timeOfLastUpdate = datetime.datetime.utcnow()
	self.greenCounter = 0
	self.debug = debug	

#sets light to green
#because of the weird bug that changes the light to magenta or some other random color, it forces it to refresh every 3rd call, regardless of whether or not it's green 
#"train is good"
    def setGreen(self):
        currentTime = datetime.datetime.utcnow()
        if self.debug: print("currentTime for light change: " + str(currentTime))
	if self.debug: print("total seconds from last light change: " + str((currentTime - self.timeOfLastUpdate).total_seconds()))
	self.greenCounter = (self.greenCounter + 1) % 3

	if(self.greenCounter == 2):
		self.color = GREEN
		if self.debug: print("Setting light to -------------------------------------------------------------- green to help clear weird bug")
		self.light.setOff()
		self.light.setGreen()
		greenCounter = 0
		self.timeOfLastUpdate = datetime.datetime.utcnow()
		return

	if self.color != GREEN:
	    if(currentTime - self.timeOfLastUpdate).total_seconds() > TIME_BUFFER:
                self.color = GREEN
                if self.debug: print("Setting light to -------------------------------------------------------------- green")
		self.light.setOff()
                self.light.setGreen()
		self.light.setGreen()
		self.timeOfLastUpdate = datetime.datetime.utcnow()
            else:
		if self.debug: print("----------------------------------------------------------------- must wait to change light to green!")

        else:
            if self.debug: print("------------------------------------------------------Light is already green!")
           

#sets light to yellow
#used to show that a train is speeding up, slowing down, or a turnout is going off
#once the change is done, it goes back to green (not in this code)
#"change is happening to a train"
    def setYellow(self):
        currentTime = datetime.datetime.utcnow()
        if self.debug: print("currentTime for light change: " + str(currentTime))
	if self.debug: print("total seconds from last light change: " + str((currentTime - self.timeOfLastUpdate).total_seconds()))
        
	if self.color != YELLOW:
            if(currentTime - self.timeOfLastUpdate).total_seconds() > TIME_BUFFER:
                self.color = YELLOW
                if self.debug: print("Setting light to -------------------------------------------------------------- yellow")
                self.light.setOff()
		self.light.setYellow()
                self.timeOfLastUpdate = datetime.datetime.utcnow()
            else:
		if self.debug: print("----------------------------------------------------------------- must wait to change light to yellow!")
            

        else:
            if self.debug: print("------------------------------------------------------Light is already Yellow!")

#sets light to red
#used to show that the trains crashed and need to be fixed
#program needs to be restarted to get rid of this
#"trains crashed, fix now"
    def setRed(self):
        currentTime = datetime.datetime.utcnow()
        if self.debug: print("currentTime for light change: " + str(currentTime))
	if self.debug: print("total seconds from last light change: " + str((currentTime - self.timeOfLastUpdate).total_seconds()))
        
	if self.color != RED:
            if(currentTime - self.timeOfLastUpdate).total_seconds() > TIME_BUFFER:
                self.color = RED
                if self.debug: print("Setting light to -------------------------------------------------------------- red")
                self.light.setOff()
		self.light.setRed()
                self.timeOfLastUpdate = datetime.datetime.utcnow()
            else:
		if self.debug: print("----------------------------------------------------------------- must wait to change light to red!")
            

        else:
            if self.debug: print("------------------------------------------------------Light is already Red!")
 
#changes light to white
#used in debugging
    def setWhite(self):
        currentTime = datetime.datetime.utcnow()
        if self.debug: print("currentTime for light change: " + str(currentTime))
	if self.debug: print("total seconds from last light change: " + str((currentTime - self.timeOfLastUpdate).total_seconds()))
        
	if self.color != WHITE:
	    if(currentTime - self.timeOfLastUpdate).total_seconds() > TIME_BUFFER:
                self.color = WHITE
                if self.debug: print("Setting light to -------------------------------------------------------------- white")
		self.light.setOff()
                self.light.setWhite()
		self.timeOfLastUpdate = datetime.datetime.utcnow()
            else:
		if self.debug: print("----------------------------------------------------------------- must wait to change light to white!")

        else:
            if self.debug: print("------------------------------------------------------Light is already white!")
            
