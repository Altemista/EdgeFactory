import pandas as pd
import numpy
import seaborn
import matplotlib.pyplot as plt
import matplotlib as mpl
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier as rfc
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
from sklearn.svm import SVC as svc
from sklearn.linear_model import LogisticRegression
from sklearn import datasets

def create_csv_file_with_remain_time(data_set, path, file_name):
    list_size = len(data_set)
    end_index = 0
    start_index = 0
    index_is_set = False
    working_time = 0

    #Looping from the beginn of the csv file to the end to set r_t
    while(end_index < list_size):

        #set the start range
        if(not index_is_set):
            start_index = end_index
            index_is_set = True

        #if broken the end range have been found and the r_t can be setted beginning from the start_index
        if (data_set['status'].iloc[end_index] == "BROKEN"):
            working_time = data_set['working_time'].iloc[end_index]
            while(start_index <= end_index):
                    data_set['remain_time'].iloc[start_index] = working_time - data_set['working_time'].iloc[start_index]
                    start_index += 1

        end_index += 1

    while(start_index < list_size):
        data_set = data_set.drop(start_index)
        start_index += 1

    #Write to given filename
    data_set.to_csv(str(path)+str(file_name), index = False, header = True)

#Inputs
csv_file_path = "~/machine_reports.csv" #input("Path to Machine Report file: ")
result_csv_file_path = "~/" #input("Path to result csv directory: ")
amount_of_machines = 3 #int(input("Amount of Machines: "))

df = pd.read_csv(csv_file_path)

i = 0
while (i < amount_of_machines):
    create_csv_file_with_remain_time(df.loc[df['MACHINE_ID'] == i], result_csv_file_path, "machine_" + str(i) + ".csv")
    print("Created at"+ result_csv_file_path + "machine_" + str(i) + ".csv")
    i += 1

#print(df['status'].iloc[0])