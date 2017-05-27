from Adafruit_BMP import BMP085
import time
import paho.mqtt.client as mqtt
import json

# {
#    "timestamp" : 1440608242631,
#    "category" : "REAL",
#    "address" : "com.ge.dspmicro.machineadapter.modbus://127.0.0.1:502/2/20",
#    "name" : "Node-2-1",
#    "quality" : "NOT_SUPPORTED (20000000) ",
#    "value" : 211
#    "datatype" : "INTEGER"
# }

def formatJson(value, valueType, unixTime, name):
    js = json.dumps({"timestamp" : unixTime, \
                     "category" : "REAL", \
                     "address" : "com.ge.dspmicro.machineadapter.modbus://127.0.0.1:1883/2/20", \
                     "name" : name, \
                     "quality" : "NOT_SUPPORTED (20000000) ", \
                     "value" : value, \
                     "datatype" : valueType})
    # js = "{timestamp : " + str(unixTime) + ", category : REAL, address : com.ge.dspmicro.machineadapter.modbus://127.0.0.1:1883/2/20, name : " +str(name) + ", quality : NOT_SUPPORTED (20000000) , value : " + str(value) + ", datatype : " + str(valueType) + "}"
    print(js)
    return js

mqttc = mqtt.Client()
mqttc.connect("127.0.0.1", 1883, 120)
mqttc.loop_start()
print("connected successfully")

bmp085 = BMP085.BMP085()


# while True:
#     inp = float(input())
#     unixTime = int(time.time())
#     (result, mid) = mqttc.publish("tojs", formatJson(inp, "FLOAT", unixTime, "train1Block") , 2)

while True:
    try:
        temp = float(bmp085.read_temperature())
        pressure = int(bmp085.read_pressure())
        altitude = float(bmp085.read_altitude())
        unixTime = int(time.time())
        # print(unixTime)
        # print("temperature: " + str(temp))
        # print("pressure: " + str(pressure))
        # print("altitude: " + str(altitude))

    
        (result, mid) = mqttc.publish("tojs", formatJson(temp, "FLOAT", unixTime, "temperature") , 2)
        (result, mid) = mqttc.publish("tojs", formatJson(pressure, "INTEGER", unixTime, "pressure") , 2)
        (result, mid) = mqttc.publish("tojs", formatJson(altitude, "FLOAT", unixTime, "altitude") , 2)
    except:
        pass
    time.sleep(1)
