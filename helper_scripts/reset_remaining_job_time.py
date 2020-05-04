from airtable import Airtable
import os
import random
import time

# Set Env Variables
AIRTABLE_BASE_KEY   = os.environ["AIRTABLE_BASE_KEY"]
AIRTABLE_API_KEY    = os.environ["AIRTABLE_API_KEY"]

list_of_jobs = Airtable(AIRTABLE_BASE_KEY, 'Job', AIRTABLE_API_KEY).search("status", "processing")
i = 0

# Update where status = processing
while i < len(list_of_jobs):
    
    fields      = {"remaining_job_time": list_of_jobs[i]["fields"]["job_time"], "status": "unfinished"}
    Airtable(AIRTABLE_BASE_KEY, 'Job', AIRTABLE_API_KEY).update_by_field("JOB_ID", list_of_jobs[i]["fields"]["JOB_ID"] ,fields)
    
    i += 1


list_of_jobs = Airtable(AIRTABLE_BASE_KEY, 'Job', AIRTABLE_API_KEY).search('remaining_job_time',0)
i = 0

# Update where remaining_job_time = 0
while i < len(list_of_jobs):
    
    fields      = {"remaining_job_time": list_of_jobs[i]["fields"]["job_time"], "status": "unfinished"}
    Airtable(AIRTABLE_BASE_KEY, 'Job', AIRTABLE_API_KEY).update_by_field("JOB_ID", list_of_jobs[i]["fields"]["JOB_ID"] ,fields)
    
    i += 1

