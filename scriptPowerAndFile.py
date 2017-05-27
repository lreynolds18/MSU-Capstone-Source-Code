# This is an example script for a JMRI "Automat" in Python
# It is based on the AutomatonExample.
#
# It runs a locomotive back and forth using time delays. 
#
# Times are in milliseconds
#
# Author: Bob Jacobsen, July 2008
# Based on BackAndForth.py 
# Author: Howard Watkins, January 2007
# Part of the JMRI distribution

import jmri
import jarray
import csv

#Class for the train object
class Train(object):
    # Constructor
    # decoderID: The decoder ID for the train
    # speed: The speed for the train
    # isForward: Boolean representing is train is going forward
    #            True means going forward, False means going backwards
    def __init__(self, decoderID, speed, isForward):
        self.decoderID = decoderID
        self.speed = speed
        self.isForward = isForward

# Class to handle the trains
class TrainHandler(jmri.jmrit.automat.AbstractAutomaton):

        def init(self):
                # init() is called exactly once at the beginning to do
                # any necessary configuration.
                print "Inside init(self)"

                self.continueLoop = False
                self.trains = []
                self.initialized = False

                # Read the initial values for speed and direction from the file
                # First row is True or FalseA
                # Every row after has the format ID,SPROG_SPEED,True/False for id, speed (0.0-1.0), and boolean for direction
                print "reading from file"
                try:
                    f = open('/home/pi/teamge/user/josh/GECapstoneFiles/trainProperties.txt')
                    try:
                        reader = csv.reader(f)
                        firstRow = True
                        for row in reader:
                            if(firstRow):
                                print "Reading from first row"
                                if(row[0] == "True"):
                                    self.continueLoop = True
                                elif(row[0] == "False"):
                                    self.continueLoop = False
                                else:
                                    print("error")
                                firstRow = False
                            else:
                                print "Reading from another row"
                                print(str(row[0])+","+str(row[1])+str(row[2]))
                                newTrain = Train(int(row[0]),float(row[1]),bool(row[2]=="True"))
                                self.trains.append(newTrain)
                    finally:
                        f.close()
                except IOError:
                    print("Could not open file")

                # Set up throttle for first train
                print "Throttle"
                self.throttle = self.getThrottle(int(self.trains[0].decoderID), False)
                print "After throttle"

                # Set up throttle for second train
                print "Throttle 2"
                self.throttle1 = self.getThrottle(int(self.trains[1].decoderID), False)
                print "after throttle 2"

                return

        def handle(self):
                # handle() is called repeatedly until it returns false.
                #print "Inside handle(self)"

                # If not initialized, set the initial direction and speed for both throttles, then
                # set initialized to False
                if(self.initialized == False):
                    LayoutPowerOn().start()
                    self.throttle.setSpeedSetting(self.trains[0].speed)
                    self.throttle.setIsForward(self.trains[0].isForward)
                    self.throttle1.setSpeedSetting(self.trains[1].speed)
                    self.throttle1.setIsForward(self.trains[1].isForward)
                    self.initialized = True


                # Wait half a second, and then check file again to see if values have updated
                self.waitMsec(250)
                try:
                    f = open('/home/pi/teamge/user/josh/GECapstoneFiles/trainProperties.txt')
                    try:
                        reader = csv.reader(f)
                        firstRow = True
                        currentRow = 0
                        for row in reader:
                            if(firstRow):
                                #print "Reading from first row"
                                if(row[0] == "True"):
                                    self.continueLoop = True
                                elif(row[0] == "False"):
                                    self.continueLoop = False
                                else:
                                    print("error")
                                firstRow = False
                            else:
                                if(self.trains[currentRow].decoderID != int(row[0])):
                                    print "File decoder ID does not match train ID"
                                if(self.trains[currentRow].speed != float(row[1])):
                                    print "Changing speed for train: " + str(currentRow)
                                    self.trains[currentRow].speed = float(row[1])
                                    if currentRow == 0:
                                        #First train
                                        self.throttle.setSpeedSetting(self.trains[currentRow].speed)
                                    elif currentRow == 1:
                                        #Second Train
                                        self.throttle1.setSpeedSetting(self.trains[currentRow].speed)
                                if(self.trains[currentRow].isForward != bool(row[2]=="True")):
                                    print "Changing direction for train: " + str(currentRow)
                                    self.trains[currentRow].isForward = bool(row[2]=="True")
                                    if currentRow == 0:
                                        #First train
                                        self.throttle.setIsForward(self.trains[currentRow].isForward)
                                    elif currentRow == 1:
                                        #Second Train
                                        self.throttle1.setIsForward(self.trains[currentRow].isForward)
                                currentRow = currentRow + 1
                                #newTrain = Train(int(row[0]),float(row[1]),bool(row[2]))
                                #self.trains.append(newTrain)
                    finally:
                        f.close()
                except IOError:
                    print("Could not open file")
        
                # Shut layout power off if continueLoop was updated to be False from the file
                if(not self.continueLoop):
                    self.throttle.setSpeedSetting(self.trains[0].speed)
                    self.throttle1.setSpeedSetting(self.trains[1].speed)
                    self.waitMsec(1000)
                    print "Turning power off"
                    LayoutPowerOff().start()
                
                # and continue around again if continue loop is true
                return int(self.continueLoop)    

# end of class definition

# Start of power classes

# Class for turning the power to the track on
class LayoutPowerOn(jmri.jmrit.automat.AbstractAutomaton):
        def init(self):
                self.condition = 'on' 
 
        def handle(self):
                powermanager.setPower(jmri.PowerManager.ON)
                return 0

# Class for turning the power to the track off
class LayoutPowerOff(jmri.jmrit.automat.AbstractAutomaton):
        def init(self):
                self.condition = 'off'

        def handle(self):
                powermanager.setPower(jmri.PowerManager.OFF)
                return 0

# End of power classes

# Start the TrainHandler loop
TrainHandler().start()
