import json
import boto3
import os
import csv

def get_session(env_name):
   return boto3.session()
def list_s3_objects(env_name,bucket_name,prefix):
    session = get_session(env_name)
    s3 = session.resource('s3', verify=False)
    response = s3.Bucket(bucket_name).objects.filter(Prefix = prefix)
    return [object.key for object in response]
    
def s3_file_copy(env_name,source,target):
    get_session(env_name).resource('s3',verify=False).Object(target['Bucket'],target['Key']).copy_from(CopySource='{}/{}'.format(source['Bucket'],source['Key']))
    if isCopy:
        get_session(env_name).resource('s3').Object(source['Bucket'],source['Key']).delete()

def file_copy(prefix_list):
    print(prefix_list)
    for prefix in prefix_list:
        file_list = list_s3_objects(env,srce_bkt,prefix)
        print(file_list)
        for file in file_list:
            print(file)
            # file = file.replace(' ')
            s3_file_copy(env,{'Bucket':srce_bkt,'Key':file},{'Bucket':trgt_bkt,'Key':'{}'.format(file)})

###############################################Audit functions#######################################################    

###############################################Start of Config######################################################    
isCopy = False
env = 'prd'
prefix_list = ['live/2024']

###############################################End of Config########################################################    
file_copy(prefix_list)
# file_list = sorted(list_s3_objects(env,srce_bkt,'fullseed'), key=lambda x: x.size, reverse=False)
# get_audit(file_list)

# file_list = list_s3_objects('prd','xxxxxxxxxx','live/2022')
# for file in file_list:
#     print(file)

def list_s3_objects(env_name,bucket_name,prefix):
    session = get_session(env_name)
    s3 = session.resource('s3')
    # response = s3.Bucket(bucket_name).objects.all
    for object in s3.Bucket(bucket_name).objects.filter(Prefix = prefix):
    # for object.key in [object for object in response]:
        # print(object.key)
        print(object.key)
        s3.Object(bucket_name, object.key).delete()

    return 
  
  def upload_a_file(file_name):
    try:
    response = s3_client.upload_file(file_name, bucket, object_name)
except Exception as e:
    print(e)

    
    def file_size(size):
    if size/1024.0 < 1024:
        return '{:.2f}'.format(size/1024.0)+'KB'
    size = size/1024.0
    if size/1024.0 < 1024:
        return '{:.2f}'.format(size/1024.0)+'MB'
    size = size/1024.0
    if size/1024.0 < 1024:
        return '{:.2f}'.format(size/1024.0)+'GB' 
        
def get_audit(file_list):
    data_file = open('oneoff_prd_stats.csv', 'w', newline='')
    csv_writer = csv.writer(data_file)
    header = ['File Name','File Keys','Last Modified']
    csv_writer.writerow(header)
    for file in file_list:    
        csv_writer.writerow([file.key,file_size(file.size),file.last_modified])
    data_file.close()
