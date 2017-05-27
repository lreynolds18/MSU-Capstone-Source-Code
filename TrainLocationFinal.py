import serial
import string
import time
import RPi.GPIO as GPIO, time
import datetime
import os
import csv
import sys
import lightHandler
import random
import json
import paho.mqtt.client as mqtt

#Class for beam breakers
class BeamBreaker:
    def beamBroken(self):
        time = datetime.datetime.utcnow()
        # Sometimes when starting up, the Arduino shows that one or two beam breakers have gone off (for no reason).
        #  so wait for a small amount of time since the start of the program before allowing beam breaker inputs to be counted as real
        if (time-self.beam_breaker_bank.time_since_start).total_seconds() < 10:
            if self.beam_breaker_bank.debug: print("Time since program start: " + str((time-self.beam_breaker_bank.time_since_start).total_seconds()))
        #Test to see if the beam breaker has not been hit in the last WAIT_TIME amount of seconds
        elif (datetime.datetime.utcnow() - self.time_of_last_break).total_seconds() > self.wait_time:
            self.beam_breaker_bank.breakerActivated(self, time)
        else:
            if self.beam_breaker_bank.debug: print("The same train activated the beam break! ID: ", self.breaker_id)
        # Update time of last break
        self.time_of_last_break = datetime.datetime.utcnow()

    #Constructor
    # breaker_id: The id of the beam breaker
    # left_segment: The segment to the left of the beam breaker, in counter-clockwise orientation
    # right_segment: The segment to the right of the beam breaker, in counter-clockwise orientation
    # block: The block this beam breaker is in. For beam breakers, it is considered to be in the block to the right
    #        of the breaker (in counter-clockwise orientation), at a distance of 0 in the block
    # beam_breaker_bank: The controller that handles the beam breaker activation
    def __init__(self, breaker_id, left_segment, right_segment, block, beam_breaker_bank):
        self.breaker_id = breaker_id
        self.block = block
        self.beam_breaker_bank = beam_breaker_bank
        self.left_segment = left_segment
        self.right_segment = right_segment
        self.wait_time = 1 # The time since breaker was last hit to ignore any other hits registered, avoids interference
        self.time_of_last_break = datetime.datetime.utcnow()

# Class for holding all of the beam breakers
class TrainLayout:
    # Constructor
    # train1_start_segment: The starting segment for the first train
    # train1_start_speed: The starting sprog speed for the first train
    # train2_start_segment: The starting segment for the second train
    # train2_start_speed: The starting sprog speed for the second train
    def __init__(self,train1_start_segment,train1_start_speed,train2_start_segment,train2_start_speed):
        #Constants
        self.TRAIN_CHECK_DIST = 6 # distance in front and behind beam breaker to check for train
        self.TRAIN_CHECK_DIST_LONGER = 15 # Same as TRAIN_CHECK_DIST, but 15 inches instead of 6. If breaker went off and turnouts haven't gone off in last TURNOUT_TIME_BUFFER seconds, use this distance if haven't found in TRAIN_CHECK_DIST 
        self.TURNOUT_TIME_BUFFER = 2 # used to check for errors in beam breakers going off
        self.LAG_TIME = 1 # time for train to reach a turnout 
        self.COLLISION_TIME_BUFFER = 5 # when a train is catching up, if they'll collide in less than this time, speed up/slow down a train 
        self.TRAIN_DISTANCE_BUFFER = 15 # Similar to COLLISION_TIME_BUFFER, if trains are within this distance, speed up/slow down 
        self.TURNOUT_COLLISION_TIME_BUFFER = 1.5 # both trains are reaching turnout at same time, if it takes them this amount of time or lower, take action
        self.TRAIN_COLLISION_DIST_CHECK = 45 # distance to check in front and in back of the checkTrain for various objects
        self.TURNOUT_COLLISION_DIST_CHECK = 50 # distance to check in the paths of a turnout for trains/other turnouts
        self.FIX_TIME_BUFFER = 0.1 # Buffer for fix time remaining, so no extra actions are taken within at least this time window
        self.MIN_SPEED = 0.3 + 0.15 # increase by 0.15 to prevent problems with rounding error
        self.MAX_SPEED = 1.0 - 0.15 # decrease by 0.15 to prevent problems with rounding error
        self.TRAIN_SPEED_DIFF_TOLERANCE = 0.5 # Used for checking differences in train speed, if within this interval then could have problem due to error

        self.breaker_8_offset = 0 # Breaker 8 is jank since it activates on train exit, not entry, so we have to adjust its virtual position
        self.state = 0
        
        self.beam_breakers = [] # Array for beam breaker objects
        self.trains = [] # Array for train objects
        self.turnouts = [] # Array for turnout objects
        self.blocks = [] # Array for block objects
        self.pairs = [] # distances between beam breaker pairs
        self.time_since_start = datetime.datetime.utcnow()
        self.fix_time_remaining = 0 # time till next acceptable action
        self.time_of_last_check = datetime.datetime.utcnow() # Time since possible collisions were checked for
        self.time_of_last_turnout_activation = datetime.datetime.utcnow()
        self.collision_averted = True
        self.debug = True # DEBUGGING! :D Set to true to get a lot more print statements

        self.mqtt_connection = mqtt.Client()
        self.mqtt_connection.connect("127.0.0.1", 1883, 120)
        self.mqtt_connection.loop_start()
        if self.debug: print("connected successfully")


        # Initialize turnouts, blocks, trains, and breakers here
	    # 0 for train starting position means the train isn't being used
        if(train1_start_segment != 0):
            train1 = Train(2,train1_start_segment)
            train1.sprog_speed = train1_start_speed
            if self.debug: print("Setting Train " + str(train1.train_id) + " to have SPROG speed: " + str(train1.sprog_speed))
            os.system("python changeSpeedOfficial.py " + str(train1.train_id) + " " + str(train1.sprog_speed))
            self.trains.append(train1)
        if(train2_start_segment != 0):
            train2 = Train(5,train2_start_segment)
            train2.sprog_speed = train2_start_speed
            if self.debug: print("Setting Train " + str(train2.train_id) + " to have SPROG speed: " + str(train2.sprog_speed))
            os.system("python changeSpeedOfficial.py " + str(train2.train_id) + " " + str(train2.sprog_speed))
            self.trains.append(train2)
        if(len(self.trains) == 0):
            print("There are no trains to keep track of!")
            sys.exit()

        # Set debug value for all trains
        for train in self.trains:
            train.setDebug(self.debug)


        # Set up the turnouts with the appropriate pins, orientation, and wanted started orientation
        self.turnouts.append(Turnout(1,20,21, "counter-clockwise","straight"))
        time.sleep(1)
        self.turnouts.append(Turnout(2,7,5, "clockwise","turn"))
        time.sleep(1)
        self.turnouts.append(Turnout(3,12,16, "clockwise","straight"))
        time.sleep(1)
        self.turnouts.append(Turnout(4,19,26, "clockwise","straight"))
        time.sleep(1)
        self.turnouts.append(Turnout(5,6,13, "counter-clockwise","straight"))

        # Set the debug value for the turnouts
        for turnout in self.turnouts:
            turnout.setDebug(self.debug)

        #Set up the initial blocks
        #                            LBS  LBT  TL   RBS  RBT  TR
        self.blocks.append(Block(1,12.875,None,None,None,None,None,self.turnouts[5-1]))
        self.blocks.append(Block(2,38.9375,self.blocks[1-1],None,None,None,None,None))
        self.blocks.append(Block(3,27.5,self.blocks[2-1],None,None,None,None,self.turnouts[1-1]))
        self.blocks.append(Block(4,6.3125,self.blocks[3-1],None,None,None,None,None))
        self.blocks.append(Block(5,23.125,self.blocks[4-1],None,None,None,None,None))
        self.blocks.append(Block(6,22.4375,self.blocks[5-1],None,None,None,None,None))
        self.blocks.append(Block(7,4.625,self.blocks[6-1],None,self.turnouts[4-1],self.blocks[1-1],None,None))
        self.blocks.append(Block(8,38.875 + self.breaker_8_offset,self.blocks[1-1],None,None,None,None,None))
        self.blocks.append(Block(9,5.125 - self.breaker_8_offset,self.blocks[8-1],None,None,None,None,None))
        self.blocks.append(Block(10,10.5625,self.blocks[9-1],None,self.turnouts[3-1],None,None,None))
        self.blocks.append(Block(11,7.375,self.blocks[10-1],None,None,None,None,None))
        self.blocks.append(Block(12,5.5,None,self.blocks[11-1],self.turnouts[2-1],None,None,None))
        self.blocks.append(Block(13,17.8125,self.blocks[12-1],None,None,self.blocks[7-1],None,None))
        self.blocks.append(Block(14,6.3125,self.blocks[3-1],None,None,None,None,None))
        self.blocks.append(Block(15,10.125,self.blocks[14-1],None,None,self.blocks[12-1],None,None))
        self.blocks.append(Block(16,6.125,None,None,None,None,None,None))
        self.blocks.append(Block(17,12.875,self.blocks[16-1],None,None,self.blocks[10-1],None,None))
        #Initialize the rest of the block connections here that could not be set up by the block creation
        self.blocks[1-1].addRightStraight(self.blocks[2-1])
        self.blocks[1-1].addRightTurn(self.blocks[8-1])
        self.blocks[3-1].addRightStraight(self.blocks[4-1])
        self.blocks[3-1].addRightTurn(self.blocks[14-1])
        self.blocks[6-1].addRightStraight(self.blocks[7-1])
        self.blocks[7-1].addLeftTurn(self.blocks[13-1])
        self.blocks[9-1].addRightStraight(self.blocks[10-1])
        self.blocks[10-1].addLeftTurn(self.blocks[17-1])
        self.blocks[11-1].addRightStraight(self.blocks[12-1])
        self.blocks[12-1].addLeftStraight(self.blocks[15-1])

        #Now that all blocks are defined, set up the turnout blocks
        self.turnouts[1-1].setBlock(self.blocks[3-1],self.blocks[3-1].distance)
        self.turnouts[2-1].setBlock(self.blocks[12-1],0)
        self.turnouts[3-1].setBlock(self.blocks[10-1],0)
        self.turnouts[4-1].setBlock(self.blocks[7-1],0)
        self.turnouts[5-1].setBlock(self.blocks[1-1],self.blocks[1-1].distance)

        # Set up the pairs
        # Pair are defined in a counter-clockwise order!!
        self.pairs.append(Pair(2,8,51.75+self.breaker_8_offset))
        self.pairs.append(Pair(2,9,51.8125))
        self.pairs.append(Pair(1,2,22.4375))
        self.pairs.append(Pair(9,5,33.8125))
        self.pairs.append(Pair(5,1,15.625))
        self.pairs.append(Pair(4,1,12.875))
        #self.pairs.append(Pair(4,7,Distance))
        self.pairs.append(Pair(8,4,15.6875-self.breaker_8_offset))
        self.pairs.append(Pair(9,6,33.8125))
        self.pairs.append(Pair(6,3,23.125))
        self.pairs.append(Pair(3,2,27.0625))
        # Other pairs for if a beam breaker fails
        self.pairs.append(Pair(8,1,28.5625-self.breaker_8_offset))
        self.pairs.append(Pair(2,4,67.4375))
        self.pairs.append(Pair(6,2,50.1875))
        self.pairs.append(Pair(1,8,74.1875+self.breaker_8_offset))
        self.pairs.append(Pair(3,8,78.8125+self.breaker_8_offset))
        self.pairs.append(Pair(1,9,74.25))
        self.pairs.append(Pair(3,9,78.875))
        self.pairs.append(Pair(8,2,51-self.breaker_8_offset))
        self.pairs.append(Pair(2,5,85.625))
        self.pairs.append(Pair(5,2,38.0625))
        self.pairs.append(Pair(4,8,87.0625+self.breaker_8_offset))
        self.pairs.append(Pair(4,2,35.3125))
        self.pairs.append(Pair(9,3,56.9375))
        self.pairs.append(Pair(9,1,49.4375))
        self.pairs.append(Pair(3,4,94.5))
        self.pairs.append(Pair(2,6,85.625))

        #Initialize beam breakers
        self.beam_breakers.append(BeamBreaker(1,6,4,self.blocks[13-1],self))
        self.beam_breakers.append(BeamBreaker(2,4,1,self.blocks[1-1],self))
        self.beam_breakers.append(BeamBreaker(3,3,4,self.blocks[6-1],self))
        self.beam_breakers.append(BeamBreaker(4,5,6,self.blocks[11-1],self))
        self.beam_breakers.append(BeamBreaker(5,2,6,self.blocks[15-1],self))
        self.beam_breakers.append(BeamBreaker(6,2,3,self.blocks[5-1],self))
        self.beam_breakers.append(BeamBreaker(7,7,5,self.blocks[17-1],self))
        self.beam_breakers.append(BeamBreaker(8,1,5,self.blocks[9-1],self))
        self.beam_breakers.append(BeamBreaker(9,1,2,self.blocks[3-1],self))

        # Create the GE light handler and turn track power on
        self.light = lightHandler.lightHandler(self.debug)
        os.system("sudo python turnTrackOnOfficial.py")

        # Send MQTT call to restart graphs on dashboard
        unixTime = int(time.time())
        self.mqtt_connection.publish("tojs", self.formatJson("ON", "STRING", unixTime, "sprogPower") , 2)

    # Method to format a JSON string for sending data to Predix
    def formatJson(self, value, valueType, unixTime, name):
        js = json.dumps({"timestamp" : unixTime, \
                         "category" : "REAL", \
                         "address" : "com.ge.dspmicro.machineadapter.modbus://127.0.0.1:1883/2/20", \
                         "name" : name, \
                         "quality" : "NOT_SUPPORTED (20000000) ", \
                         "value" : value, \
                         "datatype" : valueType})
        # js = "{timestamp : " + str(unixTime) + ", category : REAL, address : com.ge.dspmicro.machineadapter.modbus://127.0.0.1:1883/2/20, name : " +str(name) + ", quality : NOT_SUPPORTED (20000000) , value : " + str(value) + ", datatype : " + str(valueType) + "}"
        if self.debug: print(js)
        return js

    # Method to send the data from the train set (such as speed) over MQTT
    def mqttUpdate(self):
        train1speed = float(abs(self.trains[0].speed))
        train1sprogSpeed = float(abs(self.trains[0].sprog_speed))
        train1block = int(self.trains[0].current_block.block_id)
        train1distInBlock = float(self.trains[0].distance_in_block)
        train2speed = float(self.trains[1].speed)
        train2sprogSpeed = float(self.trains[1].sprog_speed)
        train2block = int(self.trains[1].current_block.block_id)
        train2distInBlock = float(self.trains[1].distance_in_block)
        unixTime = int(time.time())
        self.mqtt_connection.publish("tojs", self.formatJson(train1speed, "FLOAT", unixTime, "train1ActualSpeed") , 2)
        self.mqtt_connection.publish("tojs", self.formatJson(train1sprogSpeed, "FLOAT", unixTime, "train1SprogSpeed") , 2)
        self.mqtt_connection.publish("tojs", self.formatJson(train1block * 100 + train1distInBlock, "FLOAT", unixTime, "train1Block") , 2)
        self.mqtt_connection.publish("tojs", self.formatJson(train2speed, "FLOAT", unixTime, "train2ActualSpeed") , 2)
        self.mqtt_connection.publish("tojs", self.formatJson(train2sprogSpeed, "FLOAT", unixTime, "train2SprogSpeed") , 2)
        self.mqtt_connection.publish("tojs", self.formatJson(train2block * 100 + train2distInBlock, "FLOAT", unixTime, "train2Block") , 2)
        
        
    # Method to take in a beam breaker id, and then search through the list of beam breakers
    # and call beamBroken on the beam breaker object with id matching the number passed in
    def activateBreaker(self, breaker_id):
        for breaker in self.beam_breakers:
            if breaker.breaker_id == breaker_id:
                breaker.beamBroken()
                break

    # Method to update the train virtual location
    def updateTrains(self):
        if self.debug: print("Total time running: " + str((datetime.datetime.utcnow()-self.time_since_start).total_seconds()) + " seconds")
        # For each train that is initialized, update location
        for train in self.trains:
            if(train.initialized):
                train.updateTrain(datetime.datetime.utcnow())
                print("Train : " + str(train.train_id) + " Block: " + str(train.current_block.block_id) + " Location: " + str(train.distance_in_block) + " Speed: " + str(train.speed) + " Sprog Speed: " + str(train.sprog_speed))
        if len(self.trains) > 1:
            #Update fix time remaining
            elapsed_since_check = (datetime.datetime.utcnow()-self.time_of_last_check).total_seconds()
            if(self.fix_time_remaining < elapsed_since_check):
                self.fix_time_remaining = 0

            if self.trains[0].initialized != False and self.trains[1].initialized != False:
                self.mqttUpdate()
                if self.fix_time_remaining <= 0:
                    #self.randomSwitch() # Stopped random track switching for now
                    if (self.collision_averted == False):
                        self.collision_averted = True
                        unixTime = int(time.time())
                        self.mqtt_connection.publish("tojs", self.formatJson("offTrainWarning", "STRING", unixTime, "message") , 2)
                    self.checkForCollisions()

    # Method to randomly switch a track (very small chance to occur)
    def randomSwitch(self):
        # Make a random switch a 1 in X chance
        X = 100
        randomNumber = random.randint(0,X)
        if self.debug: print("Random number: " + str(randomNumber))
        if(randomNumber == X):
            # For now, only have the possibility of turnouts 1 and 5 randomly switching as those are the only turnouts affecting counter-clockwise movement
            turnout_to_switch = random.randint(1,2)
            if(turnout_to_switch == 2):
                turnout_to_switch = 5
            for turnout in self.turnouts:
                if(turnout_to_switch == turnout.turnout_id):
                    self.switchTurnout(turnout,0)
                    print("")
                    print("---------------------------------------------------PERFORMING A RANDOM TURNOUT SWITCH ON " + str(turnout.turnout_id))
                    print("")

    # Method to check for collisions between the trains
    def checkForCollisions(self):
        if self.debug: print("Checking for collision cases")
        #Only check the first train since there are only 2 trains, will do actions on either/both trains depending on what needs to be done
        checkTrain = self.trains[0]
        otherTrain = self.trains[1]
        #will be checking self.TRAIN_COLLISION_DIST_CHECK inches in front and behind the train, so distance = 0 means at the train
        checkDistance = self.TRAIN_COLLISION_DIST_CHECK
        currentDistance = 0
        CCWArray = [] # Counter-clockwise direction array
        CWArray = [] # Clockwise direction array

        # Note: These arrays are populated with tuples that have the following format: (object,distance_away,is_valid)
        # is_valid is a value used for some collision checks, since we check in all directions, but the direction in which a turnout is not in
        # is not valid

        # Check in the counter-clockwise direction
        # First check to see if the other train is in this block and in correct direction for check. If so put it in the array
        if otherTrain.current_block == checkTrain.current_block and otherTrain.distance_in_block > checkTrain.distance_in_block and (otherTrain.distance_in_block - checkTrain.distance_in_block) < checkDistance:
            CCWArray.append((otherTrain, otherTrain.distance_in_block - checkTrain.distance_in_block,True))
        # If remaining distance to check is greater than the remaining distance to the end of the block, change values accordingly and then call appropriate methods
        if checkDistance > checkTrain.current_block.distance - checkTrain.distance_in_block:
            checkDistance -= checkTrain.current_block.distance - checkTrain.distance_in_block
            currentDistance += checkTrain.current_block.distance - checkTrain.distance_in_block
            # If turnout is None, then only block in counter-clockwise direction is the right_block_straight, so call check method on that block and append results
            if checkTrain.current_block.turnout_right == None:
                appendArray = self.checkBlockCCW(checkTrain.current_block.right_block_straight, checkDistance, currentDistance, True, checkTrain.direction, checkTrain.current_block)
                CCWArray.extend(appendArray)
            else:
                # Append right turnout object since it exists
                CCWArray.append((checkTrain.current_block.turnout_right, checkTrain.current_block.distance - checkTrain.distance_in_block, True))
                # If train direction is also counter-clockwise, then only the direction that matches the state of the turnout is valid. Other direction is not.
                if checkTrain.direction == "counter-clockwise":
                    if self.debug: print("Making a decision on the valid values of future trains")
                    if checkTrain.current_block.turnout_right.current_state == "straight":
                        appendArray = self.checkBlockCCW(checkTrain.current_block.right_block_straight, checkDistance, currentDistance, True, checkTrain.direction, checkTrain.current_block)
                        CCWArray.extend(appendArray)
                        appendArray2 = self.checkBlockCCW(checkTrain.current_block.right_block_turn, checkDistance, currentDistance, False, checkTrain.direction, checkTrain.current_block)
                        CCWArray.extend(appendArray2)
                    elif checkTrain.current_block.turnout_right.current_state == "turn":
                        appendArray = self.checkBlockCCW(checkTrain.current_block.right_block_straight, checkDistance, currentDistance, False, checkTrain.direction, checkTrain.current_block)
                        CCWArray.extend(appendArray)
                        appendArray2 = self.checkBlockCCW(checkTrain.current_block.right_block_turn, checkDistance, currentDistance, True, checkTrain.direction, checkTrain.current_block)
                        CCWArray.extend(appendArray2)
                else:
                    appendArray = self.checkBlockCCW(checkTrain.current_block.right_block_straight, checkDistance, currentDistance, True, checkTrain.direction, checkTrain.current_block)
                    CCWArray.extend(appendArray)
                    appendArray2 = self.checkBlockCCW(checkTrain.current_block.right_block_turn, checkDistance, currentDistance, True, checkTrain.direction, checkTrain.current_block)
                    CCWArray.extend(appendArray2)
        if self.debug: print(CCWArray)


        # Check in the clockwise direction
        # Re-initalize check distance and current distance
        checkDistance = self.TRAIN_COLLISION_DIST_CHECK
        currentDistance = 0

        # First check to see if the other train is in this block and in correct direction for check. If so put it in the array
        if otherTrain.current_block == checkTrain.current_block and otherTrain.distance_in_block < checkTrain.distance_in_block and (checkTrain.distance_in_block - otherTrain.distance_in_block) < checkDistance:
            CWArray.append((otherTrain, checkTrain.distance_in_block - otherTrain.distance_in_block, True))
        # If remaining distance to check is greater than the remaining distance to the end of the block, changes values accordingly and then call appropriate methods
        if checkDistance > checkTrain.distance_in_block:
            checkDistance -= checkTrain.distance_in_block
            currentDistance += checkTrain.distance_in_block
            # IF turnout is None, then only block in the clockwise direction is the left_block_straight, so call check method based on that block and append results
            if checkTrain.current_block.turnout_left == None:
                appendArray = self.checkBlockCW(checkTrain.current_block.left_block_straight, checkDistance, currentDistance, True, checkTrain.direction, checkTrain.current_block)
                CWArray.extend(appendArray)
            else:
                # Append left turnout object since it exists
                CWArray.append((checkTrain.current_block.turnout_left, checkTrain.distance_in_block, True))
                # If train direction is also clockwise, then only the direction that matches the state of the turnout is valid. Other direction is not.
                if checkTrain.direction == "clockwise":
                    if self.debug: print("Making a decision on the valid values of future trains")
                    if checkTrain.current_block.turnout_left.current_state == "straight":
                        appendArray = self.checkBlockCW(checkTrain.current_block.left_block_straight, checkDistance, currentDistance, True, checkTrain.direction, checkTrain.current_block)
                        CWArray.extend(appendArray)
                        appendArray2 = self.checkBlockCW(checkTrain.current_block.left_block_turn, checkDistance, currentDistance, False, checkTrain.direction, checkTrain.current_block)
                        CWArray.extend(appendArray2)
                    elif checkTrain.current_block.turnout_left.current_state == "turn":
                        appendArray = self.checkBlockCW(checkTrain.current_block.left_block_straight, checkDistance, currentDistance, False, checkTrain.direction, checkTrain.current_block)
                        CWArray.extend(appendArray)
                        appendArray2 = self.checkBlockCW(checkTrain.current_block.left_block_turn, checkDistance, currentDistance, True, checkTrain.direction, checkTrain.current_block)
                        CWArray.extend(appendArray2)
                else:
                    appendArray = self.checkBlockCW(checkTrain.current_block.left_block_straight, checkDistance, currentDistance, True, checkTrain.direction, checkTrain.current_block)
                    CWArray.extend(appendArray)
                    appendArray2 = self.checkBlockCW(checkTrain.current_block.left_block_turn, checkDistance, currentDistance, True, checkTrain.direction, checkTrain.current_block)
                    CWArray.extend(appendArray2)
        if self.debug: print(CWArray)


        # Check for collision conditions, with array directions based on directions of trains
        if(checkTrain.direction == otherTrain.direction and checkTrain.direction == "counter-clockwise"):
            if self.debug: print("Checking same direction counter-clockwise")
            self.sameDirectionCollisionChecks(CCWArray, CWArray, checkTrain)
        elif(checkTrain.direction == otherTrain.direction and checkTrain.direction == "clockwise"):
            if self.debug: print("Checking same direction clockwise")
            self.sameDirectionCollisionChecks(CWArray, CCWArray, checkTrain)
        else:
            # Currently no method for dealing with checking collisions when trains are going in the opposite directions
            if self.debug: print("Checking different directions")

        if(self.fix_time_remaining == 0):
            self.light.setGreen()


    # Method to check for turnouts, train in the counter-clockwise direction
    def checkBlockCCW(self, block, checkDist, currentDist, validValue, trainDirection, previousBlock):
        returnArray = []
        newValidValue = validValue
        # If block is None, don't try to do any checks (block may be None due to dead end)
        if block != None:
            if self.debug: print("Block: " + str(block.block_id) + ", Previous Block: " + str(previousBlock.block_id))
            # If turnout left is not None, append it
            if block.turnout_left != None:
                returnArray.append((block.turnout_left, currentDist, newValidValue))
                # If train is going clockwise, if the previous block does not match the turnout state, it is not valid
                if trainDirection == "clockwise":
                    if block.turnout_left.current_state == "straight" and previousBlock == block.left_block_turn:
                        newValidValue = False
                    elif block.turnout_left.current_state == "turn" and previousBlock == block.left_block_straight:
                        newValidValue = False
            # Append any trains in this block if within check distance
            for train in self.trains:
                if train.current_block == block and train.distance_in_block < checkDist:
                    returnArray.append((train, currentDist+train.distance_in_block, newValidValue))
            # If check distance is greater than block distance, subtract values and call checkBlockCCW on appropriate next blocks
            if checkDist > block.distance:
                checkDist -= block.distance
                currentDist += block.distance
                # If turnout right is None, only block in counter-clockwise direction is right_block_straight
                if block.turnout_right == None:
                    temp = self.checkBlockCCW(block.right_block_straight, checkDist, currentDist, newValidValue, trainDirection, block)
                    returnArray.extend(temp)
                else:
                    # Append turnout right since it exists
                    returnArray.append((block.turnout_right, currentDist, newValidValue))
                    # If train direciton is counter-clockwise, then valid value is False if block does not match the state of the turnout
                    if trainDirection == "counter-clockwise":
                        if block.turnout_right.current_state == "straight":
                            temp = self.checkBlockCCW(block.right_block_straight, checkDist, currentDist, newValidValue, trainDirection, block)
                            returnArray.extend(temp)
                            temp2 = self.checkBlockCCW(block.right_block_turn, checkDist, currentDist, False, trainDirection, block)
                            returnArray.extend(temp2)
                        elif block.turnout_right.current_state == "turn":
                            temp = self.checkBlockCCW(block.right_block_straight, checkDist, currentDist, False, trainDirection, block)
                            returnArray.extend(temp)
                            temp2 = self.checkBlockCCW(block.right_block_turn, checkDist, currentDist, newValidValue, trainDirection, block)
                            returnArray.extend(temp2)
                    else:
                        temp = self.checkBlockCCW(block.right_block_straight, checkDist, currentDist, newValidValue, trainDirection, block)
                        returnArray.extend(temp)
                        temp2 = self.checkBlockCCW(block.right_block_turn, checkDist, currentDist, newValidValue, trainDirection, block)
                        returnArray.extend(temp2)
        return returnArray

    # Method to check for turnouts, train in the clockwise direction
    def checkBlockCW(self, block, checkDist, currentDist, validValue, trainDirection, previousBlock):
        returnArray = []
        newValidValue = validValue
        # If block is None, don't try to do any checks (block may be None due to dead end)
        if block != None:
            if self.debug: print("Block: " + str(block.block_id) + ", Previous Block: " + str(previousBlock.block_id))
            # If turnout right is not None, append it
            if block.turnout_right != None:
                returnArray.append((block.turnout_right, currentDist, newValidValue))
                # If train is going counter-clockwise, if the previous block does not match the turnout state, it is not valid
                if trainDirection == "counter-clockwise":
                    if block.turnout_right.current_state == "straight" and previousBlock == block.right_block_turn:
                        newValidValue = False
                    elif block.turnout_right.current_state == "turn" and previousBlock == block.right_block_straight:
                        newValidValue = False
            # Append any trains in this block if within check distance
            for train in self.trains:
                if train.current_block == block and block.distance-train.distance_in_block < checkDist:
                    returnArray.append((train, currentDist+block.distance-train.distance_in_block, newValidValue))
            # If check distance is greater than block distance, subtract values and call checkBlockCCW on appropriate next blocks
            if checkDist > block.distance:
                checkDist -= block.distance
                currentDist += block.distance
                # If turnout left is None, only block in counter-clockwise direction is left_block_straight
                if block.turnout_left == None:
                    temp = self.checkBlockCW(block.left_block_straight, checkDist, currentDist, newValidValue, trainDirection, block)
                    returnArray.extend(temp)
                else:
                    # Append turnout left since it exists
                    returnArray.append((block.turnout_left, currentDist, newValidValue))
                    # If train direciton is clockwise, then valid value is False if block does not match the state of the turnout
                    if trainDirection == "clockwise":
                        if block.turnout_left.current_state == "straight":
                            temp = self.checkBlockCW(block.left_block_straight, checkDist, currentDist, newValidValue, trainDirection, block)
                            returnArray.extend(temp)
                            temp2 = self.checkBlockCW(block.left_block_turn, checkDist, currentDist, False, trainDirection, block)
                            returnArray.extend(temp2)
                        elif block.turnout_left.current_state == "turn":
                            temp = self.checkBlockCW(block.left_block_straight, checkDist, currentDist, False, trainDirection, block)
                            returnArray.extend(temp)
                            temp2 = self.checkBlockCW(block.left_block_turn, checkDist, currentDist, newValidValue, trainDirection, block)
                            returnArray.extend(temp2)
                    else:
                        temp = self.checkBlockCW(block.left_block_straight, checkDist, currentDist, newValidValue, trainDirection, block)
                        returnArray.extend(temp)
                        temp2 = self.checkBlockCW(block.left_block_turn, checkDist, currentDist, newValidValue, trainDirection, block)
                        returnArray.extend(temp2)
        return returnArray

    # Method to switch a turnout
    # also sets the light to yellow and sets the fix time remaining for the collision fix
    def switchTurnout(self, turnout, time_to_reach):
        unixTime = int(time.time())
        self.mqtt_connection.publish("tojs", self.formatJson("Switching turnout: " + str(turnout.turnout_id), "STRING", unixTime, "message") , 2)
        if self.debug:
            if time_to_reach != 0: print("SETTING LIGHT TO YELLOW")
        if self.debug: print("SWITCHING A TURNOUT: " + str(turnout.turnout_id))
        if time_to_reach != 0: self.light.setYellow() # Only set light to yellow if time to reach is not zero (zero means it is a random track switch)
        self.fix_time_remaining = time_to_reach
        if self.debug: print("Fix time remaining: " + str(self.fix_time_remaining))
        self.time_of_last_check = datetime.datetime.utcnow()
        turnout.switchState()
        self.time_of_last_turnout_activation = datetime.datetime.utcnow()

    # Method for checking for collisions when trains are going in the same direction
    def sameDirectionCollisionChecks(self, frontArray, backArray, checkTrain):
        #Check to see if other train is ahead or behind train, and use this to perform checks
        trainInFront = False
        trainInBack = False
        otherTrain = None
        otherTrainDist = None
        for distTuple in frontArray:
            if isinstance(distTuple[0], Train):
                # Only include train if it is valid
                if (distTuple[2] == True):
                    otherTrain = distTuple[0]
                    otherTrainDist = distTuple[1]
                    trainInFront = True
                else:
                    if self.debug: print("Train was False, not included. ---------------- - -- ------------------- - -  - -- - -- - - -")
        for distTuple in backArray:
            if isinstance(distTuple[0], Train):
                # Only include train if it is valid
                if (distTuple[2] == True):
                    otherTrain = distTuple[0]
                    otherTrainDist = distTuple[1]
                    trainInBack = True
                else:
                    if self.debug: print("Train was False, not included. ---------------- - -- ------------------- - -  - -- - -- - - -")
        if self.debug: print("Front: " + str(trainInFront) + " Back: " + str(trainInBack))
                
        if(trainInBack == True):
            #Check to see if other train is faster, if not do nothing, no collision imminent
            if(otherTrain.speed > checkTrain.speed):
                #Second train faster, will eventually catch up.
                #Check to see if there is a direction-matching turnout between trains that we could switch
                for distTuple in backArray:
                    if distTuple[1] < otherTrainDist and isinstance(distTuple[0], Turnout) and distTuple[0].orientation == checkTrain.direction:
                        # Switch the Turnout if enough time before otherTrain reaches.
                        dist_between_train_and_turnout = otherTrainDist - distTuple[1]
                        time_to_reach = dist_between_train_and_turnout/abs(otherTrain.speed)
                        #Make sure time to reach is greater than lag time to change turnout
                        if(time_to_reach > self.LAG_TIME):
                            checkTrainBlock = checkTrain.current_block.block_id
                            otherTrainBlock = otherTrain.current_block.block_id
                            # Check the blocks of the trains, if the following cases hold than we do not want turnout 1 going off
                            if(distTuple[0].turnout_id == 1):
                                if(checkTrainBlock == 8 or checkTrainBlock == 9) and (otherTrainBlock == 12 or otherTrainBlock == 13):
                                    if self.debug: print("----------------------------------------------------------------------AVOIDING TURNOUT 1 BUG")
                                elif(otherTrainBlock == 8 or otherTrainBlock == 9) and (checkTrainBlock == 12 or checkTrainBlock == 13):
                                    if self.debug: print("----------------------------------------------------------------------AVOIDING TURNOUT 1 BUG")
                                else:
                                    self.switchTurnout(distTuple[0], time_to_reach)
                            else:
                                self.switchTurnout(distTuple[0], time_to_reach)
                            #found fix, ending method
                            return
                #If here, this means there was no turnout that could be swtiched in time
                # so see if time to collision is smaller than some margin, if so, slow down back train
                # or speed up front train
                time_to_collision = otherTrainDist/(otherTrain.speed - checkTrain.speed)
                if(time_to_collision < self.COLLISION_TIME_BUFFER or otherTrainDist <  self.TRAIN_DISTANCE_BUFFER):
                    #Slow down back train (other train) or speed up front train (check train)
                    if self.debug: print("Case: train is catching up and cannot swtich turnout in time")
                    try_both = True
                    if(otherTrain.sprog_speed > self.MIN_SPEED):
                        # Slow down the other train, testing new speed in 0.2 increments
                        if self.debug: print("-------------------------------------------------------------TESTING NEW SPROG SPEED----------------------")
                        if self.debug: print("Other train slowing down?")
                        speed_steps = otherTrain.getSpeedStepsArray()
                        if self.debug: print("Speed steps: " + str(speed_steps))
                        curr_test_sprog_speed = otherTrain.sprog_speed
                        if self.debug: print("Current train sprog speed: " + str(curr_test_sprog_speed))
                        speed_change_good = False
                        new_speed_max = abs(checkTrain.speed)
                        if self.debug: print("New max speed we need: " + str(new_speed_max))
                        while(curr_test_sprog_speed > self.MIN_SPEED and speed_change_good == False):
                            curr_test_sprog_speed -= 0.2
                            if self.debug: print("Current testing sprog speed: " + str(curr_test_sprog_speed))
                            new_approx_speed = speed_steps[int(round(curr_test_sprog_speed*10))]
                            if self.debug: print("New approximate speed: " + str(new_approx_speed))
                            if(new_approx_speed < new_speed_max):
                                speed_change_good = True
                                try_both = False
                        change_in_sprog_speed = curr_test_sprog_speed - otherTrain.sprog_speed
                        if self.debug: print("Calculated change in sprog speed: " + str(change_in_sprog_speed))
                        if self.debug: print("---------------------------------------------------------END TESTING NEW SPROG SPEED----------------------")
                        
                        self.changeTrainSpeed(otherTrain,change_in_sprog_speed, True)
                        if try_both == False:
                            return
                    if(checkTrain.sprog_speed < self.MAX_SPEED and try_both == True):
                        # Speed up the check train if we could not slow down the other train
                        # or we determined that slowing down the other train was not enough
                        if self.debug: print("-------------------------------------------------------------TESTING NEW SPROG SPEED----------------------")
                        if self.debug: print("Check Train speeding up?")
                        speed_steps = checkTrain.getSpeedStepsArray()
                        if self.debug: print("Speed steps: " + str(speed_steps))
                        curr_test_sprog_speed = checkTrain.sprog_speed
                        if self.debug: print("Current train sprog speed: " + str(curr_test_sprog_speed))
                        speed_change_good = False
                        new_speed_min = abs(otherTrain.speed)
                        while(curr_test_sprog_speed < self.MAX_SPEED and speed_change_good == False):
                            curr_test_sprog_speed += 0.2
                            if self.debug: print("Current testing sprog speed: " + str(curr_test_sprog_speed))
                            new_approx_speed = speed_steps[int(round(curr_test_sprog_speed*10))]
                            if self.debug: print("New approximate speed: " + str(new_approx_speed))
                            if(new_approx_speed > new_speed_min):
                                speed_change_good = True
                        change_in_sprog_speed = curr_test_sprog_speed - checkTrain.sprog_speed
                        if self.debug: print("Calculated change in sprog speed: " + str(change_in_sprog_speed))
                        if self.debug: print("---------------------------------------------------------END TESTING NEW SPROG SPEED----------------------")
                        
                        self.changeTrainSpeed(checkTrain,change_in_sprog_speed, True)
                        return
            else:
                # if other train has less approximate speed but if still within a certain speed of the check train, then it
                # could actually be faster due to error. So speed up the front train and slow down the back train (only by 0.2
                # to make speed difference more apparent
                if(checkTrain.speed - otherTrain.speed) < self.TRAIN_SPEED_DIFF_TOLERANCE:
                    if(otherTrain.sprog_speed > self.MIN_SPEED):
                        self.changeTrainSpeed(otherTrain,-0.2, True)
                    if(checkTrain.sprog_speed < self.MAX_SPEED):
                        self.changeTrainSpeed(checkTrain,0.2, True)
                    

        elif(trainInFront == True):
            #Check to see if this train is faster. If not, do nothing; no collision imminent
            if(otherTrain.speed < checkTrain.speed):
                #This train faster, will eventually catch up.
                #Check to see if there is a direction-matching turnout between trains that we could switch
                for distTuple in frontArray:
                    if distTuple[1] < otherTrainDist and isinstance(distTuple[0], Turnout) and distTuple[0].orientation == checkTrain.direction:
                        # Switch the Turnout if enough time before otherTrain reaches.
                        dist_between_train_and_turnout = distTuple[1]
                        time_to_reach = dist_between_train_and_turnout/abs(checkTrain.speed)
                        #Make sure time to reach is greater than lag time to change turnout
                        if(time_to_reach > self.LAG_TIME):
                            checkTrainBlock = checkTrain.current_block.block_id
                            otherTrainBlock = otherTrain.current_block.block_id
                            # Check the blocks of the trains, if the following cases hold than we do not want turnout 1 going off
                            if(distTuple[0].turnout_id == 1):
                                if(checkTrainBlock == 8 or checkTrainBlock == 9) and (otherTrainBlock == 12 or otherTrainBlock == 13):
                                    if self.debug: print("----------------------------------------------------------------------AVOIDING TURNOUT 1 BUG")
                                elif(otherTrainBlock == 8 or otherTrainBlock == 9) and (checkTrainBlock == 12 or checkTrainBlock == 13):
                                    if self.debug: print("----------------------------------------------------------------------AVOIDING TURNOUT 1 BUG")
                                else:
                                    self.switchTurnout(distTuple[0], time_to_reach)
                            else:
                                self.switchTurnout(distTuple[0], time_to_reach)
                            #found fix, ending method
                            return
                #If here, this means there was no turnout that could be swtiched in time
                # so see if time to collision is smaller than some margin, if so, slow down back train
                # or speed up front train
                time_to_collision = otherTrainDist/(checkTrain.speed - otherTrain.speed)
                if(time_to_collision < self.COLLISION_TIME_BUFFER or otherTrainDist < self.TRAIN_DISTANCE_BUFFER):
                    #Slow down back train (other train) or speed up front train (check train)
                    if self.debug: print("Case: train is catching up and cannot swtich turnout in time")
                    try_both = True
                    if(checkTrain.sprog_speed > self.MIN_SPEED):
                        # Slow down the check train in 0.2 increments
                        if self.debug: print("-------------------------------------------------------------TESTING NEW SPROG SPEED----------------------")
                        if self.debug: print("Check train slowing down?")
                        speed_steps = checkTrain.getSpeedStepsArray()
                        if self.debug: print("Speed steps: " + str(speed_steps))
                        curr_test_sprog_speed = checkTrain.sprog_speed
                        if self.debug: print("Current train sprog speed: " + str(curr_test_sprog_speed))
                        speed_change_good = False
                        new_speed_max = abs(otherTrain.speed)
                        if self.debug: print("New max speed we need: " + str(new_speed_max))
                        while(curr_test_sprog_speed > self.MIN_SPEED and speed_change_good == False):
                            curr_test_sprog_speed -= 0.2
                            if self.debug: print("Current testing sprog speed: " + str(curr_test_sprog_speed))
                            new_approx_speed = speed_steps[int(round(curr_test_sprog_speed*10))]
                            if self.debug: print("New approximate speed: " + str(new_approx_speed))
                            if(new_approx_speed < new_speed_max):
                                speed_change_good = True
                                try_both = False
                        change_in_sprog_speed = curr_test_sprog_speed - checkTrain.sprog_speed
                        if self.debug: print("Calculated change in sprog speed: " + str(change_in_sprog_speed))
                        if self.debug: print("---------------------------------------------------------END TESTING NEW SPROG SPEED----------------------")
                        
                        
                        self.changeTrainSpeed(checkTrain,change_in_sprog_speed, True)
                        if try_both == False:
                            return
                    if(otherTrain.sprog_speed < self.MAX_SPEED and try_both == True):
                        # Speed up the other train if we could not slow down the check train or if
                        # it was determined that slowing down the other train wasn't enough
                        if self.debug: print("-------------------------------------------------------------TESTING NEW SPROG SPEED----------------------")
                        if self.debug: print("Other Train speeding up?")
                        speed_steps = otherTrain.getSpeedStepsArray()
                        if self.debug: print("Speed steps: " + str(speed_steps))
                        curr_test_sprog_speed = otherTrain.sprog_speed
                        if self.debug: print("Current train sprog speed: " + str(curr_test_sprog_speed))
                        speed_change_good = False
                        new_speed_min = abs(checkTrain.speed)
                        while(curr_test_sprog_speed < self.MAX_SPEED and speed_change_good == False):
                            curr_test_sprog_speed += 0.2
                            if self.debug: print("Current testing sprog speed: " + str(curr_test_sprog_speed))
                            new_approx_speed = speed_steps[int(round(curr_test_sprog_speed*10))]
                            if self.debug: print("New approximate speed: " + str(new_approx_speed))
                            if(new_approx_speed > new_speed_min):
                                speed_change_good = True
                        change_in_sprog_speed = curr_test_sprog_speed - otherTrain.sprog_speed
                        if self.debug: print("Calculated change in sprog speed: " + str(change_in_sprog_speed))
                        if self.debug: print("---------------------------------------------------------END TESTING NEW SPROG SPEED----------------------")
                        
                        self.changeTrainSpeed(otherTrain,0.2, True)
                        return
            else:
                # if other train has less approximate speed but if still within a certain speed of the check train, then it
                # could actually be faster due to error. So speed up the front train and slow down the back train (only by 0.2
                # to make speed difference more apparent
                if(otherTrain.speed - checkTrain.speed) < self.TRAIN_SPEED_DIFF_TOLERANCE:
                    if(checkTrain.sprog_speed > self.MIN_SPEED):
                        self.changeTrainSpeed(checkTrain,-0.2, True)
                    if(otherTrain.sprog_speed < self.MAX_SPEED):
                        self.changeTrainSpeed(otherTrain,0.2, True)



        #traverse turnouts that are in opposite directions if a train was not found in the back or the front
        # this will check for collisions where the trains crash at a turnout
        else:
            # Only check turnouts in the front direction
            for distTuple in frontArray:
                if(isinstance(distTuple[0], Turnout) and distTuple[0].orientation != checkTrain.direction):
                    if self.debug: print("Checking for possible turnout collision")
                    turnout = distTuple[0]
                    ArrayStraight = []
                    ArrayTurn = []
                    if turnout.orientation == "clockwise":
                        checkDistance = self.TURNOUT_COLLISION_DIST_CHECK
                        currentDistance = 0
                        ArrayStraight = self.processBlockForTrainCW(turnout.block.left_block_straight, checkDistance, currentDistance, True, checkTrain.direction, turnout.block)
                        ArrayTurn = self.processBlockForTrainCW(turnout.block.left_block_turn, checkDistance, currentDistance, True, checkTrain.direction, turnout.block)

                    elif turnout.orientation == "counter-clockwise":
                        checkDistance = self.TURNOUT_COLLISION_DIST_CHECK
                        currentDistance = 0
                        ArrayStraight = self.processBlockForTrainCCW(turnout.block.right_block_straight, checkDistance, currentDistance, True, checkTrain.direction, turnout.block)
                        ArrayTurn = self.processBlockForTrainCCW(turnout.block.right_block_turn, checkDistance, currentDistance, True, checkTrain.direction, turnout.block)

                    if self.debug: print("Array Straight for turnout: " + str(ArrayStraight))
                    if self.debug: print("Array Turn for turnout: " + str(ArrayTurn))
                    # Check to see if a train is in each direction of the turnout, and both are valid
                    if len(ArrayStraight) == 1 and len(ArrayTurn) == 1 and ArrayStraight[0][0].train_id != ArrayTurn[0][0].train_id and ArrayStraight[0][2] == True and ArrayTurn[0][2] == True:
                        if self.debug: print("Inside of check for turnout collision")
                        train1 = ArrayStraight[0][0]
                        train2 = ArrayTurn[0][0]

                        train1Dist = ArrayStraight[0][1]
                        train2Dist = ArrayTurn[0][1]

                        train1TimeToTurnout = train1Dist / abs(train1.speed)
                        train2TimeToTurnout = train2Dist / abs(train2.speed)

                        # if time to get to the turnout is low enough, take an action
                        if abs(train1TimeToTurnout - train2TimeToTurnout) <= self.TURNOUT_COLLISION_TIME_BUFFER:
                            #check distance of trains, either slow down train that will reach second or speed up train that will reach first
                            if self.debug: print("Case: Train collision possible at a turnout")
                            if(train1TimeToTurnout > train2TimeToTurnout):
                                try_both = True
                                potential_solution_found = False
                                #Train 1 will reach second, so try to slow train down
                                if(train1.sprog_speed > self.MIN_SPEED):
                                    potential_solution_found = True
                                    #Slow down train1, by calculating appropriate change in sprog speed to prevent collision,
                                    # go down by 0.2 to prevent trains from having same sprog speed, keeps things interesting

                                    # Want to change speed so that train1TimeToTurnout - train2TimeToTurnout > self.TURNOUT_COLLISION_TIME_BUFFER
                                    
                                    if self.debug: print("-------------------------------------------------------------TESTING NEW SPROG SPEED----------------------")
                                    if self.debug: print("Train 1 slowing down?")
                                    speed_steps = train1.getSpeedStepsArray()
                                    if self.debug: print("Speed steps: " + str(speed_steps))
                                    curr_test_sprog_speed = train1.sprog_speed
                                    if self.debug: print("Current train sprog speed: " + str(curr_test_sprog_speed))
                                    speed_change_good = False
                                    new_speed_max = train1Dist / (self.TURNOUT_COLLISION_TIME_BUFFER + train2TimeToTurnout)
                                    if self.debug: print("New max speed we need: " + str(new_speed_max))
                                    while(curr_test_sprog_speed > self.MIN_SPEED and speed_change_good == False):
                                        curr_test_sprog_speed -= 0.2
                                        if self.debug: print("Current testing sprog speed: " + str(curr_test_sprog_speed))
                                        new_approx_speed = speed_steps[int(round(curr_test_sprog_speed*10))]
                                        if self.debug: print("New approximate speed: " + str(new_approx_speed))
                                        if(new_approx_speed < new_speed_max):
                                            speed_change_good = True
                                            try_both = False
                                    change_in_sprog_speed = curr_test_sprog_speed - train1.sprog_speed
                                    if self.debug: print("Calculated change in sprog speed: " + str(change_in_sprog_speed))
                                    if self.debug: print("---------------------------------------------------------END TESTING NEW SPROG SPEED----------------------")
                                    
                                    self.changeTrainSpeed(train1,change_in_sprog_speed, False)
                                    # Override the fix time, since want to wait for train to pass turnout, not for train to finish changing speed
                                    # Use the larger time value to ensure at least one train is past the turnout before collisions are checked again
                                    self.setFixTime(train1TimeToTurnout)
                                    if try_both == False:
                                        return # Stop looking for collisions, fix is in place
                                # potentially speed up the second train if could not speed up the first train or speed up from first train isn't enough
                                if(train2.sprog_speed < self.MAX_SPEED and try_both == True):
                                    potential_solution_found = True
                                    #Speed up train2

                                    if self.debug: print("-------------------------------------------------------------TESTING NEW SPROG SPEED----------------------")
                                    if self.debug: print("Train 2 speeding up?")
                                    speed_steps = train2.getSpeedStepsArray()
                                    if self.debug: print("Speed steps: " + str(speed_steps))
                                    curr_test_sprog_speed = train2.sprog_speed
                                    if self.debug: print("Current train sprog speed: " + str(curr_test_sprog_speed))
                                    speed_change_good = False
                                    new_speed_min = train2Dist / (train1TimeToTurnout - self.TURNOUT_COLLISION_TIME_BUFFER)
                                    while(curr_test_sprog_speed < self.MAX_SPEED and speed_change_good == False):
                                        curr_test_sprog_speed += 0.2
                                        if self.debug: print("Current testing sprog speed: " + str(curr_test_sprog_speed))
                                        new_approx_speed = speed_steps[int(round(curr_test_sprog_speed*10))]
                                        if self.debug: print("New approximate speed: " + str(new_approx_speed))
                                        if(new_approx_speed > new_speed_min):
                                            speed_change_good = True
                                    change_in_sprog_speed = curr_test_sprog_speed - train2.sprog_speed
                                    if self.debug: print("Calculated change in sprog speed: " + str(change_in_sprog_speed))
                                    if self.debug: print("---------------------------------------------------------END TESTING NEW SPROG SPEED----------------------")
                                    
                                    self.changeTrainSpeed(train2,change_in_sprog_speed, False)
                                    # Override the fix time, since want to wait for train to pass turnout, not for train to finish changing speed
                                    # Use the larger time value to ensure at least one train is past the turnout before collisions are checked again
                                    self.setFixTime(train1TimeToTurnout)
                                    return # Stop looking for collisions, fix is in place
                                if(potential_solution_found == False):
                                    #This option means that train 1 cannot slow down, and train 2 cannot speed up
                                    # So, then speed up train 2 by 0.6
                                    # and slow down train 3 by 0.6
                                    if self.debug: print("--------------------------------------------------------------CASE 3 SLOW 2 SPEED 1!----------------------")
                                    self.changeTrainSpeed(train1,0.6, False)
                                    self.changeTrainSpeed(train2,-0.6, False)
                                    # Override the fix time, since want to wait for train to pass turnout, not for train to finish changing speed
                                    # Use the larger time value to ensure at least one train is past the turnout before collisions are checked again
                                    self.setFixTime(train1TimeToTurnout)
                                    return # Stop looking for collisions, fix is in place
                            elif(train2TimeToTurnout > train1TimeToTurnout):
                                #Train 2 will reach the turnout second, so first try to slow that down.
                                try_both = True
                                potential_solution_found = False
                                if(train2.sprog_speed > self.MIN_SPEED):
                                    potential_solution_found = True
                                    #Slow down train 2

                                    # Want to change speed so that train1TimeToTurnout - train2TimeToTurnout > self.TURNOUT_COLLISION_TIME_BUFFER
                                    if self.debug: print("-------------------------------------------------------------TESTING NEW SPROG SPEED----------------------")
                                    if self.debug: print("Train 2 slowing down?")
                                    speed_steps = train2.getSpeedStepsArray()
                                    if self.debug: print("Speed steps: " + str(speed_steps))
                                    curr_test_sprog_speed = train2.sprog_speed
                                    if self.debug: print("Current train sprog speed: " + str(curr_test_sprog_speed))
                                    speed_change_good = False
                                    new_speed_max = train2Dist / (self.TURNOUT_COLLISION_TIME_BUFFER + train1TimeToTurnout)
                                    if self.debug: print("New max speed we need: " + str(new_speed_max))
                                    while(curr_test_sprog_speed > self.MIN_SPEED and speed_change_good == False):
                                        curr_test_sprog_speed -= 0.2
                                        if self.debug: print("Current testing sprog speed: " + str(curr_test_sprog_speed))
                                        new_approx_speed = speed_steps[int(round(curr_test_sprog_speed*10))]
                                        if self.debug: print("New approximate speed: " + str(new_approx_speed))
                                        if(new_approx_speed < new_speed_max):
                                            speed_change_good = True
                                            try_both = False
                                    change_in_sprog_speed = curr_test_sprog_speed - train2.sprog_speed
                                    if self.debug: print("Calculated change in sprog speed: " + str(change_in_sprog_speed))
                                    if self.debug: print("---------------------------------------------------------END TESTING NEW SPROG SPEED----------------------")
                                    
                                    self.changeTrainSpeed(train2,change_in_sprog_speed, False)
                                    # Override the fix time, since want to wait for train to pass turnout, not for train to finish changing speed
                                    # Use the larger time value to ensure at least one train is past the turnout before collisions are checked again
                                    self.setFixTime(train2TimeToTurnout)
                                    if try_both == False:
                                        return # Stop looking for collisions, fix is in place
                                # possibly speed up train 1 if could not slow down train 2 or slowing down train 2 is not enough
                                if(train1.sprog_speed < self.MAX_SPEED and try_both == True):
                                    potential_solution_found = True
                                    # Speed up train 1

                                    if self.debug: print("-------------------------------------------------------------TESTING NEW SPROG SPEED----------------------")
                                    if self.debug: print("Train 1 speeding up?")
                                    speed_steps = train1.getSpeedStepsArray()
                                    if self.debug: print("Speed steps: " + str(speed_steps))
                                    curr_test_sprog_speed = train1.sprog_speed
                                    if self.debug: print("Current train sprog speed: " + str(curr_test_sprog_speed))
                                    speed_change_good = False
                                    new_speed_min = train1Dist / (train2TimeToTurnout - self.TURNOUT_COLLISION_TIME_BUFFER)
                                    while(curr_test_sprog_speed < self.MAX_SPEED and speed_change_good == False):
                                        curr_test_sprog_speed += 0.2
                                        if self.debug: print("Current testing sprog speed: " + str(curr_test_sprog_speed))
                                        new_approx_speed = speed_steps[int(round(curr_test_sprog_speed*10))]
                                        if self.debug: print("New approximate speed: " + str(new_approx_speed))
                                        if(new_approx_speed > new_speed_min):
                                            speed_change_good = True
                                    change_in_sprog_speed = curr_test_sprog_speed - train1.sprog_speed
                                    if self.debug: print("Calculated change in sprog speed: " + str(change_in_sprog_speed))
                                    if self.debug: print("---------------------------------------------------------END TESTING NEW SPROG SPEED----------------------")

                                    self.changeTrainSpeed(train1,change_in_sprog_speed, False)
                                    # Override the fix time, since want to wait for train to pass turnout, not for train to finish changing speed
                                    # Use the larger time value to ensure at least one train is past the turnout before collisions are checked again
                                    self.setFixTime(train2TimeToTurnout)
                                    return # Stop looking for collisions, fix is in place
                                # if all else fails, "switch" the speeds
                                if(potential_solution_found == False):
                                    #This option means that train 2 cannot slow down, and train 1 cannot speed up
                                    # So, then speed up train 2 by 0.6
                                    # and slow down train 1 by 0.6
                                    if self.debug: print("--------------------------------------------------------------CASE 3 SLOW 1 SPEED 2!----------------------")
                                    self.changeTrainSpeed(train1,-0.6, False)
                                    self.changeTrainSpeed(train2,0.6, False)
                                    # Override the fix time, since want to wait for train to pass turnout, not for train to finish changing speed
                                    # Use the larger time value to ensure at least one train is past the turnout before collisions are checked again
                                    self.setFixTime(train2TimeToTurnout)
                                    #self.light.setGreen()
                                    return # Stop looking for collisions, fix is in place

                        
                    
    # Method to set the fix time
    def setFixTime(self, fix_time):
        self.collision_averted = False
        unixTime = int(time.time())
        self.mqtt_connection.publish("tojs", self.formatJson("Possible train collision detected!", "STRING", unixTime, "message") , 2)
        self.fix_time_remaining = fix_time
        if self.debug: print("Calculated fix time: " + str(self.fix_time_remaining))
        self.time_of_last_check = datetime.datetime.utcnow()


    # Method to check for collisions when trains are not going in the same direction
    # Currently not implemented 
    def oppositeDirectionCollisionChecks(self, frontArray, backArray, checkTrain):
        #Check to see if other train is ahead or behind train, and use this to perform checks
        trainInFront = False
        trainInBack = False
        otherTrain = None
        otherTrainDist = None
        for distTuple in frontArray:
            if isinstance(distTuple[0], Train):
                otherTrain = distTuple[0]
                otherTrainDist = distTuple[1]
                trainInFront = True
        for distTuple in backArray:
            if isinstance(distTuple[0], Train):
                otherTrain = distTuple[0]
                otherTrainDist = distTuple[1]
                trainInBack = True                                                                                                                                                                                                                                          

    # Method to take in an array and return an array without any turnout objects
    def stripOfTurnouts(self, array):
        returnArray = []
        for tuple in array:
            if not isinstance(tuple[0], Turnout):
                returnArray.append(tuple)
        return returnArray

    # Method to process blocks for a train in the counter-clockwise direction
    def processBlockForTrainCCW(self, block, checkDist, currentDist, validValue, trainDirection, previousBlock):
        returnArray = self.checkBlockCCW(block, checkDist, currentDist, validValue, trainDirection, previousBlock)
        returnArray = self.stripOfTurnouts(returnArray)
        return returnArray

    # Method to process blocks for a train in the clockwise direction
    def processBlockForTrainCW(self, block, checkDist, currentDist, validValue, trainDirection, previousBlock):
        returnArray = self.checkBlockCW(block, checkDist, currentDist, validValue, trainDirection, previousBlock)
        returnArray = self.stripOfTurnouts(returnArray)
        return returnArray

    # Function to change the speed of a train, including updating the train
    #  before changing speed
    # Only update fix time if update_fix_time is True
    def changeTrainSpeed(self, train, sprog_speed_change, update_fix_time):
        new_speed = train.sprog_speed + sprog_speed_change
        os.system("python changeSpeedOfficial.py " + str(train.train_id) + " " + str(new_speed))
        if self.debug: print("Changing the speed of " + str(train.train_id) + " to " + str(new_speed) + " from " + str(train.sprog_speed))
        train.updateTrain(datetime.datetime.utcnow())
        change_time = train.setNewSPROGSpeed(new_speed)
        self.light.setYellow()
        if(update_fix_time == True):
            self.setFixTime(change_time + self.FIX_TIME_BUFFER)
        
        
    # Function to handle when a beam breaker is activated
    def breakerActivated(self, breaker, time_of_break):
        print("")
        if self.debug: print("Activated: " + str(breaker.breaker_id))

        #See if trains are all initialized
        initialized = True
        for train in self.trains:
            if train.initialized == False:
                initialized = False
                break
        if(initialized == False):
            # If all trains are not yet initialized, then use the beam breaker hit to initialize a train
            available_trains = []
            for train in self.trains:
                if(train.current_segment == breaker.left_segment or train.current_segment == breaker.right_segment):
                    if(train.initialized == False and train.last_breaker_hit !=  breaker):
                        available_trains.append(train)
            if(len(available_trains)==1):
                # Means only one train could have set this off based on segment,  so update this train (takes two hits
                # to fully initialize a train)
                if(available_trains[0].last_breaker_hit == None):
                    if self.debug: print("Initialize 1")
                    #Calculate direction
                    available_trains[0].last_breaker_hit = breaker.breaker_id
                    available_trains[0].time_of_last_hit = time_of_break
                    if(available_trains[0].current_segment == breaker.left_segment):
                        if self.debug: print("C-Clockwise")
                        if self.debug: print("B" + str(breaker.right_segment))
                        available_trains[0].direction = "counter-clockwise"
                        available_trains[0].current_segment = breaker.right_segment
                    elif(available_trains[0].current_segment == breaker.right_segment):
                        if self.debug: print("Clockwise")
                        available_trains[0].direction = "clockwise"
                        if self.debug: print("B" + str(breaker.left_segment))
                        available_trains[0].current_segment = breaker.left_segment
                elif(available_trains[0].last_breaker_hit != None and available_trains[0].speed == None):
                    if self.debug: print("Initialize 2")
                    #Calculate speed
                    distance = 0
                    temp = None
                    # Determine Pair based on direction
                    if(available_trains[0].direction == "counter-clockwise"):
                        temp = Pair(available_trains[0].last_breaker_hit,breaker.breaker_id,0)
                    elif(available_trains[0].direction == "clockwise"):
                        temp = Pair(breaker.breaker_id,available_trains[0].last_breaker_hit,0)
                    for pair in self.pairs:
                        if(pair.compare(temp)):
                            distance = pair.distance
                            break
                    available_trains[0].setSpeedForAverage(distance/((time_of_break-available_trains[0].time_of_last_hit).total_seconds()))
                    if(available_trains[0].direction == "clockwise"):
                        available_trains[0].speed *= (-1)
                    if self.debug: print(available_trains[0].speed)
                    # Set block; beam breakers are all at distance 0 in their respective block
                    available_trains[0].current_block = breaker.block
                    available_trains[0].distance_in_block = 0
                    #Set as initialized
                    available_trains[0].initialized = True
                    # Set last hit breaker and time
                    available_trains[0].last_breaker_hit = breaker.breaker_id
                    available_trains[0].time_of_last_hit = time_of_break
                    # Set time so can start updating
                    available_trains[0].last_update_time = datetime.datetime.utcnow()
        #After if block

        # If train is initialized, search for it and if a train is found, update the speed and location
        #Check for trains within certain distance to beam breaker
        self.updateTrains()

        trainArray = []
        # Search for trains in both directions, trainDirection variable does not matter for this so it is set to "counter-clockwise" for both calls
        trainArray.extend(self.processBlockForTrainCCW(breaker.block, self.TRAIN_CHECK_DIST, 0, True, "counter-clockwise", breaker.block.left_block_straight))
        trainArray.extend(self.processBlockForTrainCW(breaker.block.left_block_straight, self.TRAIN_CHECK_DIST, 0, True, "counter-clockwise", breaker.block))
        if self.debug: print(trainArray)

        train_to_update = None
        train_distance = None
        # Get the closest train
        for trainTuple in trainArray:
            if train_to_update == None:
                train_to_update = trainTuple[0]
                train_distance = trainTuple[1]
            else:
                if trainTuple[1] < train_distance:
                    train_to_update = trainTuple[0]
                    train_distance = trainTuple[1]

        if train_to_update == None:
            #If turnouts have not been set off in a while, it must have been a train. So check farther.
            if self.debug: print("train to update is empty")
            if self.debug: print("Time since turnout: " + str((datetime.datetime.utcnow()-self.time_of_last_turnout_activation).total_seconds()))
            if((datetime.datetime.utcnow()-self.time_of_last_turnout_activation).total_seconds() > self.TURNOUT_TIME_BUFFER):
                #Try searching with longer distance
                if self.debug: print("--------------------------------------------------------------------TESTING WITH LONGER DISTANCES!!")
                trainArray = []
                trainArray.extend(self.processBlockForTrainCCW(breaker.block, self.TRAIN_CHECK_DIST_LONGER, 0, True, "counter-clockwise", breaker.block.left_block_straight))
                trainArray.extend(self.processBlockForTrainCW(breaker.block.left_block_straight, self.TRAIN_CHECK_DIST_LONGER, 0, True, "counter-clockwise", breaker.block))
                for trainTuple in trainArray:
                    if train_to_update == None:
                        train_to_update = trainTuple[0]
                        train_distance = trainTuple[1]
                    else:
                        if trainTuple[1] < train_distance:
                            train_to_update = trainTuple[0]
                            train_distance = trainTuple[1]
                if self.debug: print(trainArray)

                if train_to_update == None:
                    # This should never be hit, or there is a problem, no train was "close enough" (using the longer distance) to set breaker off
                    print("--------------------------------------------------------------------NO TRAIN COULD HAVE SET THIS OFF!!")
                    self.light.setRed()
            else:
                if self.debug: print("--------------------------------------------------------------------NO TRAIN COULD HAVE SET THIS OFF!!")
        if train_to_update != None:
            #Update the train that was selected for update
            
            if self.debug: print("Checking train: " + str(train_to_update.train_id))
            if((time_of_break-train_to_update.time_of_last_hit).total_seconds()!=0.0):
                if self.debug: print("Inside first check")
                if self.debug: print("Train block: " + str(train_to_update.current_block.block_id) + " Breaker Block: " + str(breaker.block.block_id))
                if self.debug: print("Distance: " + str(train_distance))
                if self.debug: print("Updating Train!")
                #Update speed and block distance
                pair_distance = 0
                temp = None
                # Determine Pair based on direction
                if(train_to_update.direction == "counter-clockwise"):
                    temp = Pair(train_to_update.last_breaker_hit,breaker.breaker_id,0)
                elif(train_to_update.direction == "clockwise"):
                    temp = Pair(breaker.breaker_id,train_to_update.last_breaker_hit,0)
                for pair in self.pairs:
                    if(pair.compare(temp)):
                        pair_distance = pair.distance
                        break
                if(pair_distance == 0):
                    if self.debug: print("---------------------------------------------------------------------PAIR DISTANCE IS ZERO--------" + str(train_to_update.last_breaker_hit) + str(breaker.breaker_id))
                if self.debug: print("Pair Distance: " + str(pair_distance))
                if self.debug: print("Time: " + str(((time_of_break-train_to_update.time_of_last_hit).total_seconds())))
                # Only update the speed if the last breaker hit was not the same as this breaker (means that we have gone around without hitting a few breakers), or pair distance is 0
                # Also don't update if the train is currently changing speed or if the train has just finished changing speed (because then we need to hit two breakers to re-initialize speed)
                #  (Specifically, the variable restart_beam_breaker_hit is used to ignore changing speed if this is the first breaker hit after a speed change)
                if(train_to_update.last_breaker_hit != breaker.breaker_id and train_to_update.changing_speed == False and train_to_update.restart_beam_breaker_hit == False and pair_distance != 0):
                    train_to_update.setSpeedForAverage(pair_distance/((time_of_break-train_to_update.time_of_last_hit).total_seconds()))
                    if(train_to_update.direction == "clockwise"):
                        train_to_update.speed *= (-1)
                    if self.debug: print("Speed: " + str(train_to_update.speed))
                elif(train_to_update.changing_speed == False and train_to_update.restart_beam_breaker_hit == True):
                    train_to_update.restart_beam_breaker_hit = False
                train_to_update.distance_in_block = 0
                train_to_update.current_block = breaker.block
                #Update last breaker hit and time of hit and update
                train_to_update.last_breaker_hit = breaker.breaker_id
                train_to_update.time_of_last_hit = time_of_break
                train_to_update.last_update_time = time_of_break

        if self.debug: print(" ")
                

# Class for a block object
class Block:
    # Constructor
    # block_id : The ID of the block
    # distance: length of the block
    # left_block_straight: if the block has a turnout to the left, this is the straight part of it. Also default if it doesn't have a turnout
    # left_block_turn: if the block has a turnout to the left, this is the turned part of it.
    # turnout_left: The turnout to the left of the block. If there is none, this is None
    # right_block_straight: if the block has a turnout to the right, this is the straight part of it. Also default if it doesn't have a turnout
    # right_block_turn: if the block has a turnout to the right, this is the turned part of it.
    # turnout_right: The turnout to the right of the block. If there is none, this is None
    def __init__(self, block_id, distance, left_block_straight, left_block_turn, turnout_left, right_block_straight, right_block_turn, turnout_right):
        self.block_id = block_id
        self.distance = distance
        self.left_block_straight = left_block_straight
        self.left_block_turn = left_block_turn
        self.turnout_left = turnout_left
        self.right_block_straight = right_block_straight
        self.right_block_turn = right_block_turn
        self.turnout_right = turnout_right

        # Code to help initialize all of the blocks as they are created
        if(self.turnout_left == None and self.left_block_straight != None and self.left_block_straight.turnout_right == None):
            self.left_block_straight.right_block_straight = self

        if(self.turnout_right == None and self.right_block_straight != None and self.right_block_straight.turnout_left == None):
            self.right_block_straight.left_block_straight = self

    def addLeftTurn(self, left_block_turn):
        self.left_block_turn = left_block_turn

    def addRightTurn(self, right_block_turn):
        self.right_block_turn = right_block_turn

    def addLeftStraight(self, left_block_straight):
        self.left_block_straight = left_block_straight

    def addRightStraight(self, right_block_straight):
        self.right_block_straight = right_block_straight

    def getRight(self):
        if(self.turnout_right == None):
            return self.right_block_straight
        else:
            if(self.turnout_right.current_state == "straight"):
                return self.right_block_straight
            else:
                return self.right_block_turn

    def getLeft(self):
        if(self.turnout_left == None):
            return self.left_block_straight
        else:
            if(self.turnout_left.current_state == "straight"):
                return self.left_block_straight
            else:
                return self.left_block_turn

    def __str__(self):
        print_string = "Block: " + str(self.block_id)
        print_string += " Distance: " + str(self.distance)
        if(self.left_block_straight!=None):
            print_string += " Left Block Straight: " + str(self.left_block_straight.block_id)
        if(self.right_block_straight!=None):
            print_string += " Right Block Straight: " + str(self.right_block_straight.block_id)
        if(self.left_block_turn!=None):
            print_string += " Left Block Turn: " + str(self.left_block_turn.block_id)
        if(self.right_block_turn!=None):
            print_string += " Right Block Turn: " + str(self.right_block_turn.block_id)
        if(self.turnout_left!=None):
            print_string += " Left Turnout: " + str(self.turnout_left.turnout_id)
        if(self.turnout_right!=None):
            print_string += " Right Turnout: " + str(self.turnout_right.turnout_id)
        return print_string

class Pair:
    # Constructor
    # num_1 : The segment to the left (going counter-clockwise)
    # num_2 : The segment to the right (going counter-clockwise)
    def __init__(self, num_1, num_2, distance):
        self.GPIO1 = num_1
        self.GPIO2 = num_2
        self.distance = distance

    # Method to compare if two pairs are the same
    def compare(self, pair):
        if(self.GPIO1 == pair.GPIO1 and self.GPIO2 == pair.GPIO2):
            return True
        return False

# Class for the train object
class Train:
    # Constructor
    # train_id : The ID of the train
    # starting_segment : The segment the train is starting in 
    def __init__(self, train_id, starting_segment):
        self.current_segment = starting_segment # The current segment the train is in, used for initializing
        self.current_block = None # The current block the train is in
        self.last_breaker_hit = None # The last breaker that the train has hit
        self.time_of_last_hit = None # The time of the last breaker hit
        self.train_id = train_id
        self.distance_in_block = None # The distance the train is in the block
        self.speed = None
        self.num_speed_data_points = 0 # The number of speed data points being currently used to get the average speed
        self.direction = None
        self.initialized = False
        self.last_update_time = None
        self.sprog_speed = None
        self.debug = False # Default is False

        #Variables and constants for when slowing down and speeding up
        self.CHANGE_RATE = 8
        self.LAG_TIME = 1.5 # The approximate lag time between the call to change speed and the actual change of speed
        self.remaining_lag_time = 0
        self.remaining_change_time = 0
        self.changing_speed = False
        self.speeding_up = None
        self.restart_beam_breaker_hit = False

        #number of slots in the array of speeds for the train
        self.speed_slots = 10
        self.speed_slots_count = 0
        self.speed_array = []
        # The speed arrays for the various different trains
        self.sprog_speed_steps_array_1_wheels = [0,.5,5.140,8.965,11.571,13.189,14.286,15.291,16.144,16.821,17.357]
        self.sprog_speed_steps_array_1 = [0,.11111,.9628,4.4325,6.944,8.8668,10.3515,11.1621,11.6118,13.0761,14.1569]
        self.sprog_speed_steps_array_3 = [0,.4817,6.4,9.81,12.42,13.99,14.7,15.99,16.78,17.355,17.75]
        self.sprog_speed_steps_array_4 = [0,1,3.1919,4.2174,4.9541,5.3739,5.6252,5.8399,5.9947,6.0793,6.3020]
        self.sprog_speed_steps_array_2 = [0,.5555,5.555,9.014,11.237,12.677,13.602,14.316,14.593,15.084,15.169]
        self.sprog_speed_steps_array_5 = [0,.3333,2.746,5.811,8.605,10.210,11.247,12.123,12.845,13.311,13.674]

    # Method to set the debug value of the train
    def setDebug(self, debug):
        self.debug = debug

    # A method to update the train, input of the train of update
    def updateTrain(self, time_of_update):
        elapsed_time = (time_of_update - self.last_update_time).total_seconds()
        if self.debug: print("Elapsed update time: " + str(elapsed_time))
        # If not changing speed, then update as normal, go forward a distance based on current speed
        if(self.changing_speed == False):
            if self.debug: print("Updating train as normal")
            if(elapsed_time > 0):
                distance_since_last = self.speed*elapsed_time
                new_dist = self.distance_in_block + distance_since_last
                do_again = True
                while do_again:
                    do_again = False
                    if(new_dist > self.current_block.distance):
                        new_dist -= self.current_block.distance
                        self.current_block = self.current_block.getRight()
                        do_again = True
                    elif(new_dist < 0):
                        self.current_block = self.current_block.getLeft()
                        new_dist += self.current_block.distance
                        do_again = True
                self.distance_in_block = new_dist
                self.last_update_time = time_of_update
            else:
                self.light.setYellow()
                if self.debug: print("Negative elapsed time???")
        else:
            # If changing speed, then update location based on a linear slow down/speed up after an amount of lag time
            if self.debug: print("Updating train as changing speed")
            if(elapsed_time < self.remaining_lag_time):
                # If train is in "LAG_TIME", then still update as normal, as the train hasn't actually changed speed yet
                if self.debug: print("IN LAG TIME")
                if self.debug: print("Elapsed time: " + str(elapsed_time))
                distance_since_last = self.speed*elapsed_time
                new_dist = self.distance_in_block + distance_since_last
                do_again = True
                while do_again:
                    do_again = False
                    if(new_dist > self.current_block.distance):
                        new_dist -= self.current_block.distance
                        self.current_block = self.current_block.getRight()
                        do_again = True
                    elif(new_dist < 0):
                        self.current_block = self.current_block.getLeft()
                        new_dist += self.current_block.distance
                        do_again = True
                self.distance_in_block = new_dist
                self.last_update_time = time_of_update
                self.remaining_lag_time -= elapsed_time
                if self.debug: print("Remaining lag time: " + str(self.remaining_lag_time))
                if self.debug: print("Last update time: " + str(self.last_update_time))
                if self.debug: print("Remaining change time: " + str(self.remaining_change_time))
            elif(elapsed_time > self.remaining_lag_time and elapsed_time < self.remaining_lag_time+self.remaining_change_time):
                # If train is past lag time but below the projected time of final speed, then update based on remaining lag time
                # and then the rest based on linear slow down/speed up
                if self.debug: print("ABOVE LAG TIME BELOW FINAL")
                if(self.speeding_up == False):
                    distance_since_last = abs(self.speed)*self.remaining_lag_time + (1.0/2.0)*(elapsed_time-self.remaining_lag_time)**2*self.CHANGE_RATE+(abs(self.speed)-self.CHANGE_RATE*(elapsed_time-self.remaining_lag_time))*(elapsed_time-self.remaining_lag_time)
                elif(self.speeding_up == True):
                    distance_since_last = abs(self.speed)*self.remaining_lag_time + (1.0/2.0)*(elapsed_time-self.remaining_lag_time)**2*self.CHANGE_RATE+abs(self.speed)*(elapsed_time-self.remaining_lag_time)
                else:
                    if self.debug: print("FREAK OUT!")
                if(self.direction == "clockwise"):
                    #Make distance covered negative if going clockwise
                    distance_since_last *= -1
                new_dist = self.distance_in_block + distance_since_last
                do_again = True
                while do_again:
                    do_again = False
                    if(new_dist > self.current_block.distance):
                        new_dist -= self.current_block.distance
                        self.current_block = self.current_block.getRight()
                        do_again = True
                    elif(new_dist < 0):
                        self.current_block = self.current_block.getLeft()
                        new_dist += self.current_block.distance
                        do_again = True
                self.distance_in_block = new_dist
                self.last_update_time = time_of_update

                if self.debug: print("Old speed: " + str(self.speed))
                if(self.speeding_up == False):
                    self.speed = (abs(self.speed)-self.CHANGE_RATE*(elapsed_time-self.remaining_lag_time))
                elif(self.speeding_up == True):
                    self.speed = (abs(self.speed)+self.CHANGE_RATE*(elapsed_time-self.remaining_lag_time))
                if(self.direction == "clockwise"):
                    #Make speed negative
                    self.speed *= -1
                if self.debug: print("New derived speed: " + str(self.speed))
                self.remaining_change_time -= elapsed_time-self.remaining_lag_time
                self.remaining_lag_time = 0
                if self.debug: print("Remaining lag time: " + str(self.remaining_lag_time))
                if self.debug: print("Last update time: " + str(self.last_update_time))
                if self.debug: print("Remaining change time: " + str(self.remaining_change_time))
            elif(elapsed_time > self.remaining_lag_time + self.remaining_change_time):
                # If past lag time and projected time of final speed, then update based on the remainder of those times, and then use the
                # remaining time to update with the new projected speed. Also set changing speed to false after this as now we want train to update
                # normally
                if self.debug: print("ABOVE FINAL")
                if(self.speeding_up == False):
                    distance_since_last = abs(self.speed)*self.remaining_lag_time+(1.0/2.0)*(self.remaining_change_time)**2*self.CHANGE_RATE+(abs(self.speed)-self.CHANGE_RATE*(self.remaining_change_time))*(self.remaining_change_time)+(elapsed_time-(self.remaining_lag_time+self.remaining_change_time))*(abs(self.speed)-self.CHANGE_RATE*(self.remaining_change_time))
                elif(self.speeding_up == True):
                    distance_since_last = abs(self.speed)*self.remaining_lag_time+(1.0/2.0)*(self.remaining_change_time)**2*self.CHANGE_RATE+abs(self.speed)*(self.remaining_change_time)+(elapsed_time-(self.remaining_lag_time+self.remaining_change_time))*(abs(self.speed)+self.CHANGE_RATE*(self.remaining_change_time))
                else:
                    if self.debug: print("FREAK OUT!")
                if(self.direction == "clockwise"):
                    #Make distance covered negative
                    distance_since_last *= -1
                new_dist = self.distance_in_block + distance_since_last
                do_again = True
                while do_again:
                    do_again = False
                    if(new_dist > self.current_block.distance):
                        new_dist -= self.current_block.distance
                        self.current_block = self.current_block.getRight()
                        do_again = True
                    elif(new_dist < 0):
                        self.current_block = self.current_block.getLeft()
                        new_dist += self.current_block.distance
                        do_again = True
                self.distance_in_block = new_dist
                self.last_update_time = time_of_update

                self.speed_slots_count = 0
                self.speed_array = []
                if(self.sprog_speed != 0.0):
                    if(self.speeding_up == False):
                        self.setSpeedForAverage((abs(self.speed)-self.CHANGE_RATE*(self.remaining_change_time)))
                    elif(self.speeding_up == True):
                        self.setSpeedForAverage((abs(self.speed)+self.CHANGE_RATE*(self.remaining_change_time)))
                else:
                    self.setSpeedForAverage(0.0)
                if(self.direction == "clockwise"):
                    #Make speed negative
                    self.speed *= -1
                self.remaining_change_time = 0
                self.remaining_lag_time = 0
                self.changing_speed = False
                if self.debug: print("Remaining lag time: " + str(self.remaining_lag_time))
                if self.debug: print("Last update time: " + str(self.last_update_time))
                if self.debug: print("Remaining change time: " + str(self.remaining_change_time))

    # Set the new sprog speed for the train and prepare for the change in speed
    #  Also return the remaining lag time + remaining change time for collision checking purporses
    def setNewSPROGSpeed(self, sprog_speed):
        #Only change if the new sprog speed is different
        if(sprog_speed != self.sprog_speed):
            if self.debug: print("SETTING SPROG SPEED --------------------------------------------------------------------SPEED------------------")
            if(self.sprog_speed > sprog_speed):
                #We are slowing down
                self.speeding_up = False
            else:
                self.speeding_up = True
            self.sprog_speed = sprog_speed
            if self.debug: print("New sprog speed: " + str(sprog_speed))
            self.remaining_lag_time = self.LAG_TIME
            if self.debug: print(self.sprog_speed)
            if self.debug: print(int(self.sprog_speed))
            if self.debug: print(str(self.sprog_speed*10))
            if self.debug: print(int(round(self.sprog_speed*10)))
            calculated_new_speed = (self.getSpeedStepsArray())[int(round(self.sprog_speed*10))]
            if self.debug: print("Calculated new speed: " + str(calculated_new_speed))
            speed_diff = abs(abs(self.speed)-calculated_new_speed)
            #self.sprog_speed = sprog_speed
            if self.debug: print("Speed diff: " + str(speed_diff))
            self.remaining_change_time = speed_diff/self.CHANGE_RATE
            self.changing_speed = True
            self.restart_beam_breaker_hit = True
            return self.remaining_lag_time + self.remaining_change_time

    # Add the speed to the speed array to calculate average speed
    def setSpeedForAverage(self, speed):

        if len(self.speed_array) < self.speed_slots:
            self.speed_array.append(speed)
        else:
            self.speed_array[self.speed_slots_count] = speed
            self.speed_slots_count = (self.speed_slots_count+1) % self.speed_slots
        #Set speed to absolute value for calculations, program above will
        #  change it back to negative if clockwise
        self.speed = abs(sum(self.speed_array)/float(len(self.speed_array)))

    # Get the appropriate speed array for this train
    def getSpeedStepsArray(self):
        if(self.train_id == 1):
            return self.sprog_speed_steps_array_1_wheels
        elif(self.train_id == 3):
            return self.sprog_speed_steps_array_1
        elif(self.train_id == 4):
            return self.sprog_speed_steps_array_4
        elif(self.train_id == 2):
            return self.sprog_speed_steps_array_2
        elif(self.train_id == 5):
            return self.sprog_speed_steps_array_5


    def __str__(self):
        return "Train: " + str(self.train_id)

    def __repr__(self):
        return "Train: " + str(self.train_id)

# Class for controlling turnouts
class Turnout:
    # Constructor
    # turnout_id : The ID of the turnout
    # straight_pin_num : The pin number to set the turnout to straight
    # turn_pin_num : The pin number to set the turnout to turn
    # orientation: The orientation of the turnout i.e. The direction a train would need to be going to utilize the turnout
    def __init__(self, turnout_id, straight_pin_num, turn_pin_num, orientation, starting_state):
        self.turnout_id = turnout_id
        self.straight_pin_num = straight_pin_num
        self.turn_pin_num = turn_pin_num
        self.current_state = ""
        self.orientation = orientation
        self.block = None
        self.distance_in_block = None
        self.debug = False # Default is False

        # Send signal to make physical turnout to initial state
        if(starting_state == "straight"):
            self.activateStraight()
        elif(starting_state == "turn"):
            self.activateTurn()

    def __str__(self):
        return "Turnout: " + str(self.turnout_id)

    def __repr__(self):
        return "Turnout: " + str(self.turnout_id)

    # Method to set the debug value for the turnout
    def setDebug(self, debug):
        self.debug = debug

    # Put the turnout in the straight state
    def activateStraight(self):
        if self.current_state == "straight":
            if self.debug: print("Turnout is already in the 'straight' state")
        else:
            self.current_state = "straight"
            if self.debug: print("Putting turnout in 'straight' state")
            self.__activateRelay(self.straight_pin_num)

    # Put the turnout in the turned state
    def activateTurn(self):
        if self.current_state == "turn":
            if self.debug: print("Turnout is already in the 'turned' state")
        else:
            self.current_state = "turn"
            if self.debug: print("Putting turnout in 'turn' state")
            self.__activateRelay(self.turn_pin_num)

    # Switch the state of the turnout
    def switchState(self):
        if(self.current_state == "straight"):
            self.activateTurn()
        else:
            self.activateStraight()
            
    # send the signal to activate the correct pin on the pi
    def __activateRelay(self, pin_num):
        #Activate the pin for the duration of the time delay, then shut off
        if self.debug: print("ACTIVATING TURNOUT --------------------------------------------------------------------TURNOUT " + str(self.turnout_id) + "--------------")
        os.system("sudo python activatePin.py " + str(pin_num))
    
    # set the block and distance in block for the turnout
    def setBlock(self, block, dist_in_block):
        self.block = block
        self.distance_in_block = dist_in_block


# Main Program

#Set up the input arguments
train1_segment = 0
train1_speed = 0.0
train2_segment = 0
train2_speed = 0.0
if(len(sys.argv) == 3):
    train1_segment = sys.argv[1]
    train1_speed = sys.argv[2]
if(len(sys.argv) >= 5):
    train1_segment = sys.argv[1]
    train1_speed = sys.argv[2]
    train2_segment = sys.argv[3]
    train2_speed = sys.argv[4]
layout=TrainLayout(int(train1_segment),float(train1_speed),int(train2_segment),float(train2_speed))
print("started")
output = " "
# Setup the serial port reading from the Arduino
ser = serial.Serial('/dev/ttyACM0', 9600, 8, 'N', 1, timeout=1)

while True:
    try:
        while output != "":
            output = ser.readline()
            if output.strip() != "":
                beam_break = int(output.strip())
                layout.activateBreaker(beam_break)
        output = " "
        layout.updateTrains()
    except KeyboardInterrupt:
        print(" Ending program")
        # Turn off track power, shut off light, end the program
        os.system("python turnTrackOffOfficial.py")
        os.system("sudo python lightOff.py")
        sys.exit()
