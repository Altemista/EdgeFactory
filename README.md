# Edge Factory
Practical part of the thesis "patterns in the area of edge computing".

# Description
The aim of the present practical part of the bachelor thesis is to apply patterns for edge computing in a virtual industrial area. With this architecture, the processing of production orders is to be designed as efficiently as possible using AI (“artificial intelligence”). The Factory will process an order list using an AI implementation and with the machines that are in the virtual factory while the time is being measured. After several runs and analyzes, this implementation is assessed. This showed that the application of edge patterns in the industrial area is possible and, on the one hand, through the implementation of an AI, order processing is accelerated. On the other hand, the machines are preventively repaired before total damage occurs, which saves the factory from expensive repair costs.

# Installation

### Operating Systems
This guide is written for Linux based Operating Systems.

### Programs/Tools and Subscriptions/Keys
#### Programs/tools
In the follow all programms/tools are listed and linked with the official installation instruction for starting the environment.
- [Docker](https://docs.docker.com/engine/install/ubuntu/)
  - Make sure [docker-compose](https://docs.docker.com/compose/install/) is installed.
- [Python 3.6](https://docs.python-guide.org/starting/install3/linux/) (to run environment locally)

#### Subscriptions/Keys
In the follow all subscriptions are listed and linked with the official site for subscribing. This subscriptions and keys are required for starting the environment.

- [Airtable](https://airtable.com/signup) (Free account is sufficient)
  - Go to Bases -> add a new Workspace -> add a Base -> click on the Base -> on the left upper corner edit the table and give it an name
    - Save the **Tablename**!
    - Tablecolumns -> follow this https://airtable.com/shrFHxawucr9cYMX0/tblyxze6vAWHKUm2l?blocks=hide
    - Columntype -> every column in the upper link have an character at his left that represents his type.
    - This types and names need to be setted or the enviroment wont work!
  - Click on account
    - Copy **api key** an save it!
    - Click on the "Airtable API" link in the description above the api key -> click on your base -> copy the **base key** beginning with "app.." -> save it!
- [Azure](https://azure.microsoft.com/de-de/) (paid subscription is sufficient)
  - [Storage account](https://docs.microsoft.com/en-us/azure/storage/common/storage-account-create?tabs=azure-portal) need to be created 
    - Open Keys -> Save **connection string**!
    - Open your storage account -> click container -> Create the new container by clicking ‘+ Container’ then choosing a Name and Access type. (Save the **container name**!)

### Usage
 
0. Download the repository and open an terminal in it.


1. Upload the KI-model to the **storage/container/yourcontainername** that is in the Repository over the browser.


2. Paste the saved **keys**, **tablename** and **ki-model-name (repository)** in the **"docker-compose-template.yml"** and rename it to **"docker-compose.yml"**


3. Go to the pythonscript EdgeFactory/helper_scripts/**generate_random_jobs.py**
    - Replace the **key** and **tablename** with your **keys** and **tablename** or set it over **env**.
    - **run** it with python3.6 over the terminal
    - This will **add random jobs** to your table


4. After Creating an table with jobs and paste the keys into the compose file, the environment **can be started**.
    - go to the folder where the compose file is and run over terminal: ```docker-compose up```
    - this will download and start the containers.
    - after this it will start the environment and the simulation will do the jobs.


5. When the joblist is done it will upload an **csv file** to the storage container in the cloud.
    - you can find the file over **storage/container/yourcontainername**
    - this file u can use to **train** an new model and upload to the container. But it must be the **same name** as in the compose-file.
      - to train an new model only **scikit-learn models** are supported!
    - after generate an new model to use u must **start** the compose-file again with the **right ki-model** name.


6. To stop the environment and stop the containers run over terminal: ```docker-compose down```
