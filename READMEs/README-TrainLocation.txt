HOW TO OPERATE:

The TrainLocationFinal.py file is the program we currently use to keep track of the trains using the pi. Before use make sure that:
-The SPROG is plugged in, and JRMI Panel Pro is on (for using JMRI, see the JMRI readme) - turning on Panel Pro/Decoder Pro can wait till last, but it doesn't hurt to have it on
-The turnout power source is plugged in
-The power box for the large breadboard is plugged in (power source for the relays and beam breakers)
-Set up the trains on the track

Steps to start the trains running:
1. Set up the trains in the segments you want them to start in (for segment numbers, see the picture of the track). It is recommended that you start trains in non-adjacent segments as this will allow the trains the greatest opportunity to initialize without messing each other up.
2. Start the program. To run the program from the terminal, use the command "sudo python TrainLocationFinal.py <train2startsegment> <train2startSpeed> <train5startsegment> <train5startSpeed>" where you insert the values you want for the train start segments and speed (speed can be in the values of [0.0,0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0]). Having the starting segment as 0 means that the train is not on the track. (For segment and block numbers, see the TrainLayout photos in the folder ExampleImages)
3. Run the script ScriptPowerAndFile.py using Panel Pro and going to Panel->Run Script... (Make sure to start the script only after all turnouts are initialized and it is past the wait time used to ignore beam breaker noise from the Arduino. A safe bet is starting the script a little after 10 seconds after the program is started).

To stop the trains:
-Hit Ctrl-C in the terminal the program is running on. The program will catch this exception, shut off the track power, and turn off the light.

---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
A note on putting trains in segments to start:
-It is recommended that you put trains in non-adjacent segments to start. The reason for this is because if a train enters the same segment as another train before both trains are initialized, the program will not know which train sets off the next beam breaker. So set up the trains in the starting segments so that the trains do not enter the same segment until both are initialized (the trains become initialized after two beam breaker hits each). It is also recommended that you start the train a little ways away from the beam breaker that it will first hit so that the train has a little time to gather speed before becoming initialized. See example starting position photos in the folder ExampleImages.
