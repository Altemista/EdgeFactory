from airtable import Airtable
import os
import random
import time

# Set Env Variables
AIRTABLE_BASE_KEY   = os.environ["AIRTABLE_BASE_KEY"]
AIRTABLE_API_KEY    = os.environ["AIRTABLE_API_KEY"]
AIRTABLE_TABLE_NAME = os.environ["AIRTABLE_TABLE_NAME"]

i = 0
# Loop
while i < 10:
    
    # Get Unfinished Jobs
    if len(Airtable(AIRTABLE_BASE_KEY, AIRTABLE_TABLE_NAME, AIRTABLE_API_KEY).search('status','unfinished')) < 10:
        
        # Generate random job type
        job_type = random.randint(0,2)
        
        if job_type == 0:
            job_type = "hard"
        elif job_type == 1:
            job_type = "normal"
        elif job_type == 2:
            job_type = "soft"
        
        job_time = random.randint(5,30)

        #Insert Job into Airtable
        Airtable(AIRTABLE_BASE_KEY, AIRTABLE_TABLE_NAME, AIRTABLE_API_KEY).insert({"job_time": job_time, "remaining_job_time": job_time , "quantity": random.randint(1,14), "type": job_type,"status": "unfinished"})
        print("Insert new Job: "+str(i))
        i += 1

    else:
        print("Unfinished Job exist")
        time.sleep(5)
    
    