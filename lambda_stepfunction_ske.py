import boto3


def create_snapshots(context):
    """
    It will be used to create RDS snaphots.
    
    Input args:   
    context: [obj] Use it to check remaining lambda execution time.
    
    Documentation
    https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/rds.html#RDS.Client.create_db_snapshot
    """
    
    # ADD SNAPSHOTS CREATION CODE HERE
    pass
    
  
def copy_snapshots_to_other_region(context):
    """
    It will be used to migrate the snapshots to another region.
    Input args:
    context: [obj] Use it to check remaining lambda execution time.
    
    Documentation
    https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/rds.html#RDS.Client.copy_db_snapshot
    """
    
    # ADD SNAPHOST MIGRATION CODE HERE
    pass


def lambda_handler(event, context):
    """
    Lambda Handler
    """
    create_snapshots(context)
    copy_snapshots_to_other_region(context)

    # ADD CODE HERE FOR LAMBDA STATE MANGEMENT 


    # event object can be used for state management. Currently, adding MigrationCompleted field in event object, it will be used by step function's "Choice State condition check" to decide what to do next. 
    
    # the MigrationCompleted variable will be used to decided if we want to restart the lambda or just end the process
    if status == "Done":
        event["MigrationCompleted"] = True
    else:
        event["MigrationCompleted"] = False

  
    return event
