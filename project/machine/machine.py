"""Edge Device

The script is intended to simulate a machine that communicates with the edge device via the mqtt protocol over localhost:1883. 
This machine has the task of doing jobs. Depending on the job assigned by the edge device, 
the machine wears down and leads to the machine decaying in various states.

This script can be started without any arguments.

Required imports: paho-mqtt.

The main loop will execute the check_state_of_machine() and publish_machine() functions. 1 loop == 1 Cycle

States:
    * RUNNABLE                                              - Machine will cool down until change on WORKING Status. 

    * WORKING                                               - Machine will do the job when its in WORKING state. It will execute the do_the_job() function and will
                                                              check with the is_broken() function with different limits as argument if the machine gets broken. When true its
                                                              change state to BROKEN. When an job is finished it will wait until the edge device take the job. When its get taken 
                                                              then the edge device will publish an message to finished_jobs/MACHINE_ID that will received by the machine to change 
                                                              the state to RUNNABLE

    * BROKEN                                                - Machine will do nothing until change on MAINTANCE Status. This change on MAINTANCE will be an message by the edge device
                                                              on topic remaining_repair_time/MACHINE_ID

    * MAINTANCE                                             - Machine will get repaired then set the status on RUNNABLE. Every Cycle it dekrements the remaining_repair_time -= 1.
                                                              When its on 0 it will reset all values and set the status on RUNNABLE. After this it will get an new remaining_time
                                                              by the edge device and an new job. 

Functions: 
    * on_connect(client, userdata, flags, rc): none         - Gets triggered when the client connect to the Mqtt broker.

    * on_message(client, userdata, msg): none               - Gets messages that are sended to the topic remain_time/MACHINE_ID, remaining_repair_time/MACHINE_ID, jobs/MACHINE_ID
                                                              and finished_job/MACHINE_ID. When an subscribed topic receive an message.
                                                              It will become an message from the edge device that will change the values and state 
                                                              of the machine. 

    * publish_machine(): none                               - Publish __data to machines/ (edge device). This will be executed once in the Main loop.

    * do_the_job(): none                                    - The logic for work off the Jobs and demolating the machine every loop when the machine has an Job.
                                                              A value between 0.5 - 0.1 will add to the variables temperatur and wear depend on the job attributes.
                                                              A value between 0.5 - 0.1 will add to alignment randomly. 
                                                              1 will add to working_time. -1 will add to remaining_job_time. 
    
    * is_broken(lower, upper, probability): bool            - Checks if any of the attributes of the Machine is between this values (lower - upper) to 
                                                              decide if the machine is broken or not.
                                                              If between -> return if (randomly generatet value from 0 to 100 ) < (probability).
                                                              If not between -> return false
                                                              Lower an upper are included limits.

    * check_state_of_machine(): none                        - Checks the Status of the Machine and apply the "state-machine-logic". It will executed every loop.
"""


# -------------------------------- Imports -------------------------------- #

from datetime import datetime
import time
import os
import json
import paho.mqtt.client as mqtt
import random

# -------------------------------- Variables -------------------------------- #

# Constant reseted job
__reseted_job       = { "JOB_ID": "none", "job_time": 0, "remaining_job_time": 0, "quantity": 0, "type": "none", "status": "none" }

# All Machine attributes
__data              = {
"MACHINE_ID"                : os.environ["MACHINE_ID"],
"Job"                       : { "JOB_ID": "none", "job_time": 0,"remaining_job_time": 0, "quantity": 0, "type": "none", "status": "none" },
"status"                    : "RUNNABLE",
"remain_time"               :-1,
"working_time"              : 0,
"remaining_repair_time"     : 0,
"wear"                      : 0.0,
"alignment"                 : 0.0,
"temperatur"                : 0.0,
}

# -------------------------------- Functions -------------------------------- #

def on_connect(client, user__data, flags, rc):
    """ Prints at successful connection
        Define the connect callback implementation.

        Expected signature for MQTT v3.1 and v3.1.1 is:
            connect_callback(client, userdata, flags, rc, properties=None)

        and for MQTT v5.0:
            connect_callback(client, userdata, flags, reasonCode, properties)

        client:     the client instance for this callback
        userdata:   the private user data as set in Client() or userdata_set()
        flags:      response flags sent by the broker
        rc:         the connection result
        reasonCode: the MQTT v5.0 reason code: an instance of the ReasonCode class.
                    ReasonCode may be compared to interger.
        properties: the MQTT v5.0 properties returned from the broker.  An instance
                    of the Properties class.
                    For MQTT v3.1 and v3.1.1 properties is not provided but for compatibility
                    with MQTT v5.0, we recommand adding properties=None.

        flags is a dict that contains response flags from the broker:
            flags['session present'] - this flag is useful for clients that are
                using clean session set to 0 only. If a client with clean
                session=0, that reconnects to a broker that it has previously
                connected to, this flag indicates whether the broker still has the
                session information for the client. If 1, the session still exists.

        The value of rc indicates success or not:
            0: Connection successful
            1: Connection refused - incorrect protocol version
            2: Connection refused - invalid client identifier
            3: Connection refused - server unavailable
            4: Connection refused - bad username or password
            5: Connection refused - not authorised
            6-255: Currently unused.
    """    
    print("Connected with result code " + str(rc))

def on_message(client, user__data, msg):
    """ Gets triggered when an subscribed topic receive an message.
        It will become an message from the edge device that will change the values and states 
        of the machine.  
        Define the message received callback implementation.

        Expected signature is:
            on_message_callback(client, userdata, message)

        client:     the client instance for this callback
        userdata:   the private user data as set in Client() or userdata_set()
        message:    an instance of MQTTMessage.
                    This is a class with members topic, payload, qos, retain.
    """

    # Prints the topic and message
    print(msg.topic + " " + str(msg.payload))
    
    # convert to json
    job = json.loads(msg.payload)
    
    # If Machine get r_t from edge device set it    
    if msg.topic == "remain_time/" + __data["MACHINE_ID"] + "/":
        __data["remain_time"] = job["remain_time"]
    
    # If Machine get an remaining_repair_time its going to MAINTANCE 
    elif msg.topic == "remaining_repair_time/" + __data["MACHINE_ID"] + "/":
        __data["Job"]                               = __reseted_job
        __data["remaining_repair_time"]             = job["remaining_repair_time"]
        __data["status"]                            = "MAINTANCE"

    # Set Job and status on WORKING 
    elif msg.topic == "jobs/" + __data["MACHINE_ID"] + "/":
        __data["status"]    = "WORKING"
        __data["Job"]       = job

    # Set state on RUNNABLE when an job is fininshed and reset the job 
    elif msg.topic == "finished_job/" + __data["MACHINE_ID"] + "/":
        __data["status"]    = "RUNNABLE"
        __data["Job"]       = __reseted_job
          
def publish_machine():
    """Publish __data to machines/ (edge device).

    Returns
    -------
    none
    
    """
    # Publish values of the machine to edge device
    client.publish("machines/", json.dumps(__data))
    
    # Prints published message 
    print("machines/" + str(__data))

def do_the_job():
    """The logic for work off the Jobs and demolating the machine every loop when the machine has an Job. 
    A value between 0.5 - 0.1 will add to the variables temperatur and wear depend on the job attributes. A value between 0.5 - 0.1 will add to alignment randomly. 
    +1 will add to working_time. -1 will add to remaining_job_time. 

    Returns
    -------
    none
    
    """
    # If the machine has an Job. Dekrement the remaintime to finish the job.
    if __data["Job"]["JOB_ID"] != "none" and __data["status"] == "WORKING":
        
        # Wear += 0.1 - 0.5
        if __data["Job"]["type"] == "hard":
            __data["wear"] += 0.5
        elif __data["Job"]["type"] == "normal":
            __data["wear"] += 0.2
        elif __data["Job"]["type"] == "soft":
            __data["wear"] += 0.1

        # Temperatur += 0.1 - 0.5
        if int(__data["Job"]["quantity"]) >= 10:
            __data["temperatur"] += 0.5
        elif int(__data["Job"]["quantity"]) < 10 and int(__data["Job"]["quantity"]) >= 5:
            __data["temperatur"] += 0.2
        elif int(__data["Job"]["quantity"]) < 5:
            __data["temperatur"] += 0.1

        # Alignment += 0.1 - 0.5 
        __data["alignment"] += float(random.randrange(0,5) / 10)

        # Dekrement remain job time
        __data["Job"]["remaining_job_time"]    -= 1
        
        # Inkrement working_time
        __data["working_time"] += 1

def is_broken(lower, upper, probability):
    """Checks if any of the attributes of the Machine is between this limits (lower - upper) to 
    decide if the machine is broken or not.
    If between -> return if (randomly generatet value from 0 to 100 ) < (probability).
    If not between -> return false
    Lower an upper are included limits.

    Parameters
    ----------
    lower : any
        lower limit
    upper : any
        upper limit
    probability : any
        if any of the values from the machine is between the limits 
        the probability decide whether the machine return true or false
    
    Returns
    -------
    bool
        True: Machine values are between the limits and the random number is under probability  
        False: Machine values are NOT between the limits OR the random number is OVER probability
    
    """
    # Organische random funktion. Noise function.
    # Decide if values are between limits and under the probability 
    if  (lower <= __data["wear"] <= upper) or (lower <= __data["alignment"] <= upper) or (lower <= __data["temperatur"] <= upper):
        return random.randrange(0,100) < probability
    else:
        return False

def check_state_of_machine():
    """Checks the Status of the Machine and apply the "state-machine-logic".
    
    Returns
    -------
    none    
    """

    global __data

    # Prints attributes of the machine
    print("Status: " + __data["status"] + ", Working Time: " + str(__data["working_time"])+ ", Alignment: " + str(__data["alignment"])+ ", Wear: " + str(__data["wear"])+ ", Temperatur: " + str(__data["temperatur"]))

    # Machine will cool down until change on WORKING Status
    if __data["status"] == "RUNNABLE":
        
        print("Waiting for an Job")

        # Cool down when no job have to do
        if __data["temperatur"] > 0:
            __data["temperatur"] -= 0.02
        else:
            __data["temperatur"] = 0

    # Machine will do the job
    elif __data["status"] == "WORKING":
        
        # Prints the remaining job time
        print("Remaining time to finish the Job:" + str(__data["Job"]["remaining_job_time"]))

        # If r_j_t is > 0 do the job
        if __data["Job"]["remaining_job_time"] > 0: 
            
            # Do the Job
            do_the_job()
        
            # Check if the Machine is broken if true set status on broken
            if is_broken(3, 5, 1) or is_broken(6, 8, 3) or is_broken(9, 11, 6) or is_broken(12, 14, 10) or is_broken(15, 9999999, 60):   
                __data["status"]    = "BROKEN"
        
        # else job is finished wait until job gets taken by the edge-device
        else:
            print("Job is finished")
        
    # Machine will do nothing until change on MAINTANCE Status
    elif __data["status"] == "BROKEN":
        print("Need to be repaired")

    # Machine will get repaired then set the status on RUNNABLE   
    elif __data["status"] == "MAINTANCE":

        # Prints r_r_t
        print("Remaining time to be rapaired:" + str(__data["remaining_repair_time"]))

        # If remain_time > 0 -> dekrement
        if __data["remaining_repair_time"] > 0:
            __data["remaining_repair_time"] -= 1

        # Else -> reset attributes and set status on RUNNABLE
        else:
            __data["status"]        = "RUNNABLE"
            __data["wear"]          = 0
            __data["alignment"]     = 0
            __data["temperatur"]    = 0
            __data["working_time"]  = 0
            __data["remain_time"]   = -1
        
# -------------------------------- Need to be Initialized -------------------------------- #

# Create an client, connect to the Mqtt Broker and subscribe to the topics.
client              = mqtt.Client()
client.on_connect   = on_connect
client.on_message   = on_message
client.connect("localhost", 1883, 60)
client.subscribe("jobs/" + __data["MACHINE_ID"] + "/#")
client.subscribe("remain_time/" + __data["MACHINE_ID"] + "/#")
client.subscribe("remaining_repair_time/" + __data["MACHINE_ID"] + "/#")
client.subscribe("finished_job/" + __data["MACHINE_ID"] + "/#")
client.loop_start()

# -------------------------------- Main Loop -------------------------------- #

while True:

    time.sleep(1)
    publish_machine() 
    check_state_of_machine()

