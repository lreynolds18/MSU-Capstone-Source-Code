import time
import paho.mqtt.client as mqtt
import json
import RPi.GPIO as GPIO
import MFRC522
import signal
import multiprocessing
import GELight


def publish(topic, value, valueType, unixTime):
# format sensor data into a json form that predix accepts
# {
#    "timestamp" : 1440608242631,
#    "category" : "REAL",
#    "address" : "com.ge.dspmicro.machineadapter.modbus://127.0.0.1:502/2/20",
#    "name" : "Node-2-1",
#    "quality" : "NOT_SUPPORTED (20000000) ",
#    "value" : 211
#    "datatype" : "INTEGER"
# }
    global mqttc
    js = json.dumps({"timestamp" : unixTime, \
                     "category" : "REAL", \
                     "address" : "com.ge.dspmicro.machineadapter.modbus://127.0.0.1:502/2/20", \
                     "name" : "Pi #2", \
                     "quality" : "NOT_SUPPORTED (20000000) ", \
                     "value" : value, \
                     "datatype" : valueType})
    # topic, payload, qualityOfService
    # return value is (result, mid)
    return mqttc.publish("PETT/" + topic, js, 2)


def RFID():
    global continue_reading

    # Create an object of the class MFRC522
    MIFAREReader = MFRC522.MFRC522()

    # This loop keeps checking for chips. If one is near it will get the UID and authenticate
    
    lastStatus = 0
    while continue_reading:
        (status,TagType) = MIFAREReader.MFRC522_Request(MIFAREReader.PICC_REQIDL)

        if status == MIFAREReader.MI_OK and lastStatus != status:
            unixTime = int(time.time())
            publish("RFID_Detect", 1, "INT", unixTime)
            # print("Card detected")

        lastStatus = status

        # Get the UID of the card
        (status,uid) = MIFAREReader.MFRC522_Anticoll()

        # If we have the UID, continue
        if status == MIFAREReader.MI_OK:
            unixTime = int(time.time())
            tag_id = str(uid[0]) + str(uid[1]) + str(uid[2]) + str(uid[3]) 
            publish("RFID_uid", tag_id, "STRING", unixTime)
            # print(tag_id)


def beamBreaker():
# multisensor read every one second
    global continue_reading
    bmp085 = BMP085.BMP085() # multisensor
    output = " "
    ser = serial.Serial('/dev/ttyACM0', 9600, 8, 'N', 1, timeout=1)
    
    while continue_reading:
        while output != "":
            output = ser.readline()
            if output.strip() != "":
                unixTime = int(time.time())
                beam_break = int(output.strip())
                print(beam_break)
                publish("beam-break", beam_break, "INT", unixTime)
        output = " "

    
### Helper function for GE Logo Light
def logoLightOnMessage(client, userdata, msg):
    global light
    output = msg.payload
    print("in here")
    if output == "red":
        light.setRed()
    elif output == "yellow":
        light.setYellow()
    elif output == "green":
        light.setGreen()
    elif output == "rainbow":
        light.setRainbow()
    elif output == "wheel":
        light.setWheel()
    else:
        light.setOff()

def logoLight():
    global light
    mqttc = mqtt.Client()
    mqttc.connect("localhost", 1883, 60)
    mqttc.loop_start()

    light.setRed()
    # tell Predix that turnouts are all straight
    # publish("turnout", "to" + str(i) + "-straight", "STRING", unixTime)

    mqttc.subscribe("PETT/logo-light")
    mqttc.on_message = logoLightOnMessage 
    mqttc.loop_forever()


def sprog():
    pass


# Capture SIGINT for cleanup when the script is aborted
def end_read(signal,frame):
    global continue_reading
    print("Ctrl+C captured, ending read.")
    continue_reading = False
    GPIO.cleanup()

if __name__ == "__main__":
    GPIO.setwarnings(False)
    continue_reading = True # stop all while loops when closing out
    signal.signal(signal.SIGINT, end_read) # Hook the SIGINT
    
    light = GELight.GELight() 
    mqttc = mqtt.Client()
    mqttc.connect("localhost", 1883, 60)
    mqttc.loop_start()
    print("Connected successfully to MQTTC server")
    pool = multiprocessing.Pool()
    
    # For Testing, use these
    # RFID()
    # beamBreaker()
    logoLight()
    # sprog()

    # For Production, use these (w/ multiple processes):
    # result1 = pool.apply_async(RFID, ())
    # result2 = pool.apply_async(beamBreaker, ())
    # result3 = pool.apply_async(logoLight, ())
    # result4 = pool.apply_async(sprog, ())

    # result1.wait()
    # result2.wait()
    pool.terminate()
