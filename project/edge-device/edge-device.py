"""Edge Device

This script enables the management of industrial machines and the processing of
virtual orders that are received via an interface to the database (Airtable).
With the approaches of edge computing and communication via an Mqtt protocol,
these virtual machines are supplied with orders so that the orders are also processed in a cyclical rhythm.
The orders are processed by using a machine learning approach wich will be more accurancy after an amount of data have saved.
To save the data, an Azure Storage (Blob Storage) must be created and the connection string must be setted via an ENV variable. The KI will be setted
after an model get downloaded from the cloud. If all Jobs have been done an csv file with the machine data will be uploaded to the cloud.
To establish the communication between machines and edge-device an Mqtt broker has to be started which can be reached via "localhost: 1883".
The communication to the cloud is etablished via the IoT-Hub wich will be reached with the connection string.

This script can be started without any arguments.

Required imports: 
    - airtable-python-wrapper
    - paho-mqtt
    - pandas
    - sklearn
    - azure-iot-device
    - azure-iot-hub
    - azure-iothub-service-client
    - azure-iothub-device-client
    - azure-storage-blob
    - joblib

The main loop will go through the machine list and check the states of the machines. 
It will react to three states:
    * RUNNABLE                                              - When an machine is RUNNABLE it will call the deploy_job function 
                                                              with the index for the actual machine.
    
    * WORKING                                               - When an machine is WORKING the edge device will publish an predicted 
                                                              remain_time for the machine with his actual values at this moment.
                                                              When the job have be done then it will publish to the machine that the machine can change
                                                              his state to RUNNABLE and it will take the job from the machine and write it as finished back to the DB.
                                                              When an machine have taken an riskly job (see below: deploy_job()) and finished it succesfully,
                                                              the machine change his state to MAINTANCE.

    *BROKEN                                                 - When an machine gets BROKEN that means for the edge device to write the actual job with his actual values 
                                                              back to the db and calculate an repair_time for the machine. 80% -> 50 Cycles, 20% -> 5 Cycles. After this set 
                                                              his state to MAINTANCE  

Functions: 
    * on_connect(client, userdata, flags, rc): none         - Gets triggered when the client connect to the Mqtt broker.

    * on_message(client, userdata, msg): none               - Gets messages that are sended to the topic machines/#. When __record_machine_data == True 
                                                              then it will save the Machine data in a csv file.
                                                              At the end it will update the machine variables.

    * deploy_job(machine_index): none                       - Gets unfinished jobs from Airtable and deploys the makeable job 
                                                              to the given machine (machine_index). For an Machine its makeable when
                                                              machine.remain_time > job.remain_time. When there isnt any Job that 
                                                              is shorter then the machine.remain_time then send the machine to the Maintance before
                                                              its gets broken but only if the machine worked before (machine.wokring_time > 0). 
                                                              When machine.working_time == 0 then give the machine the shortest Job 
                                                              that is over the remain_time (riskly job).

    * update_machine_list(msg): none                        - Gets triggered in the on_message function.
                                                              Only if an Machine update his Values or an new Machine send his 
                                                              first Message will trigger this method.
                                                              It will add an new Machine to the list or change values of an already exist Machine in the List.
                                                              When an Machine gets registered for the first time or after an MAINTANCE it will become an predicted remain_time.
    
    * set_job(JOB_ID, field, value): none                   - Updates an exist Entry in the DB (Airtable). 

    * write_machine_info_in_csv_file(machine, path): none   - This method just used to generate an Trainings csv file.
                                                              It will write the Machine values in an csv file except when an Machine is at MAINTANCE
                                                              and except the remain_time of the machine.

    * all_jobs_is_done(): bool                              - This method will just check if all Jobs have been done.
                                                              True : If all jobs have been done
                                                              Flase: If any job exist that is unfinished
    
    * send_data_to_cloud(): none                            - This Method will upload the data to the an Container in the cloud.
                                                              It will be an csv file of the machine data and will be named with the 
                                                              actual time and date. For this the __CONNECTION_STRING_TO_AZURE_STORAGE
                                                              and __CONTAINER_NAME need to be setted correct.

    * check_if_data_can_uploaded(): none                    - This method will check if all Jobs have been done. When True then
                                                              it will call the method send_data_to_cloud() once until new jobs added
                                                              to the db.

"""

# -------------------------------- Imports -------------------------------- #

import time
import random
import os
import csv
import json
import paho.mqtt.client as mqtt
import pandas as pd
import sklearn
import joblib
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from datetime import datetime
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from sklearn import preprocessing
from sklearn.cluster import KMeans
from sklearn.linear_model import LinearRegression
from airtable import Airtable

# -------------------------------- Variables -------------------------------- #

__AIRTABLE_TABLE_NAME                   = os.environ["AIRTABLE_TABLE_NAME"]                 # The db table name (Airtable)
__AIRTABLE_BASE_KEY                     = os.environ["AIRTABLE_BASE_KEY"]                   # Env Variable to etablish an connection to the db
__AIRTABLE_API_KEY                      = os.environ["AIRTABLE_API_KEY"]                    # Env Variable to etablish an connection to the db
__CONNECTION_STRING_TO_AZURE_STORAGE    = os.environ["CONNECTION_STRING_TO_AZURE_STORAGE"]  # Env Variable to etablish an connection to the Azure Storage
__CONTAINER_NAME                        = os.environ["CONTAINER_NAME"]                      # The Containername in the Cloud where the data get uploaded
__machines                              = list()                                            # Actual registered machine list
__prediction                            = os.environ["PREDICTION"]                          # Flag if ki prediction is wanted. If false deploy shortest job first 
__REPAIR_TIME                           = 5                                                 # Constant repair time
__TOTAL_DAMAGE_REPAIR_TIME              = 50                                                # Constant total damage repair time
__path_to_ml_file                       = os.environ["PATH_TO_ML_FILE"]                     # ML file with filled right remain_time. IF __prediction == true this will be used
__path_to_ml_file_without_r_t           = "machine_reports_without_remain_time.csv"         # ML file without remain_time. IF __prediction == false this will be used
__uploaded                              = False                                             # Flag if the data get uploaded before 
__record_machine_data                   = os.environ["RECORD_MACHINE_DATA"]                 # Flag if the data get saved in a csv file
__ki                                    = None                                              # KI-Model 
# -------------------------------- Functions -------------------------------- #

def on_connect(client, userdata, flags, rc):
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

def on_message(client, userdata, msg):
    """ Gets triggered when an subscribed topic receive an message.
        When __record_machine_data == True then it will save the 
        Machine data in a csv file.
        At the end it will update the machine variables.

        Define the message received callback implementation.

        Expected signature is:
            on_message_callback(client, userdata, message)

        client:     the client instance for this callback
        userdata:   the private user data as set in Client() or userdata_set()
        message:    an instance of MQTTMessage.
                    This is a class with members topic, payload, qos, retain.
    """
    if __record_machine_data:
        
        # Machine that gets updated
        machine     = json.loads(msg.payload)        
        
        # Writes the values of the machine in a csv file except remain_time and except when the machine is at state MAINTANCE 
        write_machine_info_in_csv_file(machine, __path_to_ml_file_without_r_t)        

    update_machine_list(msg)

def deploy_job(machine_index):
    """Gets jobs from the db and deploys an suitable unfinished job to the Machine.
    When there isnt any job_remain_time that is shorter then the remain_time of the machine then 
    decide between send machine to MAINTANCE (when machine.working_time > 0) or give machine
    an riskly job.

    Parameters
    ----------
    machine_index : any
        index of the machine in the __machines list.

    Returns
    -------
    none
    
    """

    global __machines

    # Get all Jobs
    all_jobs = Airtable(__AIRTABLE_BASE_KEY, __AIRTABLE_TABLE_NAME, __AIRTABLE_API_KEY).get_all()
    
    # List of unfinished jobs
    jobs = list()
    i = 0

    # Go over all jobs and push the unfinished jobs to the list
    while i < len(all_jobs):
        k  = 0
        already_taken = False

        while k < len(__machines):
            if __machines[k]["Job"]["JOB_ID"] == all_jobs[i]["fields"]["JOB_ID"]:
                already_taken = True
            k += 1
        
        if not (already_taken or all_jobs[i]["fields"]["status"] == "finished" or all_jobs[i]["fields"]["remaining_job_time"] <= 0):
            jobs.insert(len(jobs), all_jobs[i])

        i += 1

    i = 0
    job_found = False
    
    # When any job is unfinished
    if len(jobs) > 0:
        
        if __prediction:
            # Try to find an Job for the Machine that is shorter then the remain_time of the machine
            while i < len(jobs):

                # If remain_time of the machine is bigger than the job. Deploy the job to the machine
                if jobs[i]["fields"]["remaining_job_time"] < __machines[machine_index]["remain_time"]:
                
                    # Publish Job to the machine
                    client.publish("jobs/" +__machines[machine_index]["MACHINE_ID"] + "/", json.dumps(jobs[i]["fields"]))

                    # Set job to proccessing in DB
                    set_job(jobs[0]["fields"]["JOB_ID"],"status","processing")

                    # Set state of machine on WORKING
                    __machines[machine_index]["status"] = "WORKING"

                    # Out of while loop
                    i = len(jobs)                

                    # Job was found so set flag  
                    job_found = True

                i += 1

            # If any Job for the Machine didnt found decide betwween if send machine
            # to MAINTANCE or give machine an riskly job    
            if not job_found:

                # If the machine have worked before -> set repair time
                if __machines[machine_index]["working_time"] > 0:

                    # Set normal repair time
                    data = {"remaining_repair_time": __REPAIR_TIME}    

                    # Publish it to the machine
                    client.publish("remaining_repair_time/" +__machines[machine_index]["MACHINE_ID"] + "/", json.dumps(data))

                    # Set state of machine
                    __machines[machine_index]["status"] = "MAINTANCE" 

                # Else the reason that any job for the machine didnt found is that the remain_time is to small
                # But the Jobs must be done. So the only way to do the jobs is to take the risk and give the machine the smallest job             
                else:

                    # Sort jobs -> shortest first
                    jobs = sorted(jobs, key=lambda jobs: jobs["fields"]["remaining_job_time"])

                    # Publish Job to the machine
                    client.publish("jobs/" +__machines[machine_index]["MACHINE_ID"] + "/", json.dumps(jobs[0]["fields"]))

                    # Set job on processing in DB
                    set_job(jobs[0]["fields"]["JOB_ID"],"status","processing")

                    # Set machine state on WORKING
                    __machines[machine_index]["status"] = "WORKING"

                    # Prints an information that an riskly job was given to the machine
                    print("GIVE MACHINE: " + str(__machines[machine_index]["MACHINE_ID"]) +" AN JOB OVER THE REMAIN_TIME: " + str(jobs[0]["fields"]["JOB_ID"]) + " remaining_job_time: " + str(jobs[0]["fields"]["remaining_job_time"]))
        
        # Without prediction give machine the shortest job
        else:
            # Sort jobs -> shortest first
            jobs = sorted(jobs, key=lambda jobs: jobs["fields"]["remaining_job_time"])
                    
            # Publish Job to the machine
            client.publish("jobs/" +__machines[machine_index]["MACHINE_ID"] + "/", json.dumps(jobs[0]["fields"]))
    
            # Set job on processing in DB
            set_job(jobs[0]["fields"]["JOB_ID"],"status","processing")
    
            # Set machine state on WORKING
            __machines[machine_index]["status"] = "WORKING"
    
            # Prints an information about the job that was given to the machine
            print("GIVE MACHINE: " + str(__machines[machine_index]["MACHINE_ID"]) +" AN JOB: " + str(jobs[0]["fields"]["JOB_ID"]) + " remaining_job_time: " + str(jobs[0]["fields"]["remaining_job_time"]))
      
    else:
        print("No Jobs. Machine with ID:" + __machines[machine_index]["MACHINE_ID"] + " is waiting for an Job...")
    
def update_machine_list(machine):
    """Only if an Machine update his Values or an new Machine send his 
    first Message will trigger this method.
    It will add an new Machine to the list or change values of an already exist Machine in the List.
    When an Machine gets registered for the first time or after an MAINTANCE it will become an predicted remain_time.

    Parameters
    ----------
    machine : any
        machine that send an message to the edge device. This machine will get updated.

    Returns
    -------
    none
    
    """

    global __machines

    # Machine that gets updated
    machine     = json.loads(machine.payload)
    
    i           = 0
    isUpdated   = False
    
    # If machine dont get an r_t give him one and then add to the list __machines 
    if int(machine["remain_time"]) == -1 and __prediction:
        
        # Get predicted r_t
        remain_time =  int(__ki.predict([[machine["working_time"], machine["wear"], machine["alignment"], machine["temperatur"]]]))
        
        # If r_t is negative
        if remain_time < 0:
            remain_time = 0

        # Publish r_t to the machine    
        client.publish("remain_time/" + machine["MACHINE_ID"] + "/", json.dumps({"remain_time": remain_time}))
        
        # Print first predicted r_t
        print(machine["MACHINE_ID"]+ ": FIRST PREDICTED REMAIN_TIME: " + str(remain_time))

    # Else machine has already an r_t so add to the list or update values
    else:
        # Itterating over the Machine List to check if the Machine that send an message is already in the list.
        # if: true -> Updating Values, false -> Insert to the end of the list
        while i < len(__machines) and isUpdated == False:

            # true -> Updating Values
            if machine["MACHINE_ID"] == __machines[i]["MACHINE_ID"]:
                
                # Updating values
                __machines[i]   = machine
                
                # Set flag
                isUpdated       = True
            i += 1

        # false -> Insert to the end of the list
        if isUpdated == False:

            # Insert at the end if the list
            __machines.insert(len(__machines), machine)
            
            # Prints machine that is added to the list
            print("Machine with ID: " + machine["MACHINE_ID"] + " dont exist so add to List")
  
def set_job(JOB_ID, field, value):
    """Updates an exist Entry in the DB (Airtable).

    Parameters
    ----------
    JOB_ID : any
        ID of the exist job in db
    field : any
        cell that is going to be updated
    value : any
        value that will be the updated value 

    Returns
    -------
    none
    
    """

    # Field that is goig to be settd in db
    fields      = {str(field): value}
    
    # Set updated field to the db to update it
    Airtable(__AIRTABLE_BASE_KEY, __AIRTABLE_TABLE_NAME, __AIRTABLE_API_KEY).update_by_field("JOB_ID", JOB_ID, fields)

def write_machine_info_in_csv_file(machine, path):
    """This method just used to generate Trainings csv file.
    It will write the Machine values in an csv file except when an Machine is at MAINTANCE
    and except the remain_time of the machine.  
    This method just called when __record_machine_data == True

    Parameters
    ----------
    machine : any
        machine from which the values are to be written into the csv file
    path : any
        path to the csv file

    Returns
    -------
    none
    
    """

    # Except when an machine is at MAINTANCE write values in csv file
    if machine["status"] == "RUNNABLE" or machine["status"] == "BROKEN" or machine["status"] == "WORKING":
       
        # Fieldnames
        fnames = ['MACHINE_ID', 'working_time', 'remain_time', 'wear', 'alignment', 'temperatur','status']
        
        # If file already exist. Add entry at the end of the file
        if os.path.isfile(path) :
            ml_file = open(path, 'a') 
            with ml_file: 
                writer = csv.DictWriter(ml_file, fieldnames=fnames)
                writer.writerow({   'MACHINE_ID'    : machine["MACHINE_ID"],    
                                    'working_time'  : machine["working_time"],
                                    'wear'          : machine["wear"],
                                    'alignment'     : machine["alignment"],
                                    'temperatur'    : machine["temperatur"],
                                    'status'        : machine["status"]})
        
        # Else file dont exist. Create an new file
        else:
            ml_file = open(path, 'w')
            with ml_file:
                writer = csv.DictWriter(ml_file, fieldnames=fnames) 
                writer.writeheader() 
                writer.writerow({   'MACHINE_ID'    : machine["MACHINE_ID"],
                                    'working_time'  : machine["working_time"],
                                    'wear'          : machine["wear"],
                                    'alignment'     : machine["alignment"],
                                    'temperatur'    : machine["temperatur"],
                                    'status'        : machine["status"]})  

def all_jobs_is_done():
    """This method will just check if all Jobs have been done.
    Parameters
    ----------
    Returns
    -------
    bool :
        True : If all jobs have been done
        Flase: If any job exist that is unfinished
    
    """

    # Get all Jobs
    all_jobs = Airtable(__AIRTABLE_BASE_KEY, __AIRTABLE_TABLE_NAME, __AIRTABLE_API_KEY).get_all()
    
    # List of unfinished jobs
    jobs = list()
    i = 0

    # Go over all jobs and push the unfinished jobs to the list
    while i < len(all_jobs):
        k  = 0
        already_taken = False

        while k < len(__machines):
            if __machines[k]["Job"]["JOB_ID"] == all_jobs[i]["fields"]["JOB_ID"]:
                already_taken = True
            k += 1
        
        if not (already_taken or all_jobs[i]["fields"]["status"] == "finished" or all_jobs[i]["fields"]["remaining_job_time"] <= 0):
            jobs.insert(len(jobs), all_jobs[i])

        i += 1

    print("Unfinished Jobs: " + str(len(jobs)))

    return len(jobs) <= 0

def send_data_to_cloud():
    """This Method will upload the data to the an Container in the cloud.
    It will be an csv file of the machine data and will be named with the 
    actual time and date. For this the __CONNECTION_STRING_TO_AZURE_STORAGE
    and __CONTAINER_NAME need to be setted correct.

    Parameters
    ----------
    Returns
    -------
    none
    
    """
    # datetime object containing current date and time
    now = datetime.now()

    # dd/mm/YY H:M:S as Name
    dt_string = now.strftime("%d_%m_%Y_%H_%M_%S")
    file_name = dt_string+".csv"

    # Create the BlobServiceClient object which will be used to get a container client
    blob_service_client = BlobServiceClient.from_connection_string(__CONNECTION_STRING_TO_AZURE_STORAGE)

    # Create a blob client using the local file name as the name for the blob
    blob_client = blob_service_client.get_blob_client(container=__CONTAINER_NAME, blob=file_name)

    # Upload to Cloud Storage
    with open(__path_to_ml_file_without_r_t, "rb") as data:
        blob_client.upload_blob(data)

def check_if_data_can_uploaded():
    """ This method will check if all Jobs have been done. Then
    it will call the method send_data_to_cloud() once until new jobs added
    to the db.

    Parameters
    ----------
    Returns
    -------
    none
    
    """   
    global __uploaded

    # Only if all Machines are on RUNNABLE upload the File to the Cloud 
    i = 0
    all_machines_is_runnable = True
    while i < len(__machines):
        if __machines[i]["status"] != "RUNNABLE":
            all_machines_is_runnable = False
        i += 1    

    # If all Jobs have been done then send the csv file (with machine data) to the Cloud 
    if all_machines_is_runnable and __record_machine_data and all_jobs_is_done() and __uploaded == False:
        send_data_to_cloud()
        __uploaded = True
    elif all_jobs_is_done() == False:
        __uploaded = False

# -------------------------------- Need to be Initialized -------------------------------- #

# Create an client, connect to the Mqtt Broker and subscribe to the topics.
client              = mqtt.Client()
client.on_connect   = on_connect
client.on_message   = on_message
client.connect("localhost", 1883, 60)
client.subscribe("machines/#")
client.subscribe("finished/#")
client.loop_start()

# Set the right flags from the Env variables
if __prediction == "False":
    __prediction = False
else:
    __prediction = True

if __record_machine_data == "False":
    __record_machine_data = False
else:
    __record_machine_data = True

# Download an existing ml model from the cloud and initialize __ki with it. __prediction must be true.
if __prediction:

    # Create the BlobServiceClient object which will be used to get a container client
    blob_service_client = BlobServiceClient.from_connection_string(__CONNECTION_STRING_TO_AZURE_STORAGE)

    # Get the existing container
    container_client = blob_service_client.get_container_client(__CONTAINER_NAME)

    # Get the existing Blob
    blob_client = blob_service_client.get_blob_client(container=__CONTAINER_NAME, blob=__path_to_ml_file)

    # Download file to the __path_to_ml_file
    with open(__path_to_ml_file, "wb") as download_file:
        download_file.write(blob_client.download_blob().readall())

    # Fit KI with an downloaded model
    __ki = joblib.load(__path_to_ml_file)

# -------------------------------- Main Loop -------------------------------- #

while True:

    if len(__machines) > 0:

        # Check states of the machines
        i = 0
        while i < len(__machines):

            # Print important machine information
            print(str("ID: " + __machines[i]["MACHINE_ID"]) + ", status: " + str(__machines[i]["status"]) + ", w: " + str(__machines[i]["wear"]) + ", t: " + str(__machines[i]["temperatur"]) +
            ", a: " + str(__machines[i]["alignment"]) + ", w_t: " + str(__machines[i]["working_time"]) + " r_t: " + str(__machines[i]["remain_time"]) +
            ", r_r_t: " + str(__machines[i]["remaining_repair_time"]) + ", Job: " + str(__machines[i]["Job"]["JOB_ID"])  + ", remaining_job_time: " + str(__machines[i]["Job"]["remaining_job_time"]))
                
            if __machines[i]["status"] == "RUNNABLE":
                
                # Find an job for the machine
                deploy_job(i)

            elif __machines[i]["status"] == "WORKING":
                
                if __prediction:
                    
                    # Predict an r_t
                    remain_time = int(__ki.predict([[__machines[i]["working_time"], __machines[i]["wear"], __machines[i]["alignment"], __machines[i]["temperatur"]]]))

                    # In some cases the ki return an negative r_t but for the programm logic its not allowed. So when its return negative make it 0. 
                    if remain_time < 0:
                        remain_time = 0

                    # Publish the r_t to the machine
                    client.publish("remain_time/" + __machines[i]["MACHINE_ID"] + "/", json.dumps({"remain_time": remain_time})) 

                # If the machine have done the job set the job in db to finished and publish to the machine that it can be again RUNNABLE.
                # At the end fit the KI with this values.
                if __machines[i]["Job"]["remaining_job_time"] <= 0:
                    
                    # Set Job in DB
                    set_job(__machines[i]["Job"]["JOB_ID"], "status", "finished")
                    set_job(__machines[i]["Job"]["JOB_ID"], "remaining_job_time", 0)
                    
                    # Publish to the machine
                    client.publish("finished_job/" + __machines[i]["MACHINE_ID"] + "/", json.dumps(__machines[i]["Job"]))

                    # Only when an riskly job have been taken and its sucessfully have be done then it will be written in the csv file.
                    # fit_ki_with_machine_data(i ,__path_to_ml_file)

            elif __machines[i]["status"] == "BROKEN":
                
                # Fit KI
                # fit_ki_with_machine_data(i, __path_to_ml_file)

                # Set Job in Airtable 
                if __machines[i]["Job"]["remaining_job_time"] > 0:
                    set_job(__machines[i]["Job"]["JOB_ID"],"status", "unfinished")
                else:
                    set_job(__machines[i]["Job"]["JOB_ID"],"status", "finished")
                
                # Set remaining_job_time
                set_job(__machines[i]["Job"]["JOB_ID"],"remaining_job_time", int(__machines[i]["Job"]["remaining_job_time"]))
                
                # Set an Constant repairtime
                data = {"remaining_repair_time": __REPAIR_TIME}
                
                # Check if Totaldamage is present. If true set an huge repairtime 
                if random.randint(0,100) < 80:
                    data = {"remaining_repair_time": __TOTAL_DAMAGE_REPAIR_TIME}    
                
                # Publish it to the machine
                client.publish("remaining_repair_time/"+__machines[i]["MACHINE_ID"] + "/", json.dumps(data))
                
                # Set status on MAINTANCE
                __machines[i]["status"] = "MAINTANCE" 

            i += 1

        # When all jobs have been done send data to the cloud
        check_if_data_can_uploaded()
    
    else:
        print("No Machines are registered to the Edge-Device")
    

    time.sleep(1)