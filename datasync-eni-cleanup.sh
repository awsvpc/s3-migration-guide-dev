
#!/bin/bash
RED='\033[0;31m'
NC='\033[0m'

# Update the AWS CLI commands to use a specific profile if not default

# get ENIs with an Available status that contain task- in the description  
DSAVAILENI=(`aws ec2 describe-network-interfaces --profile default | jq -r '.NetworkInterfaces[] | select(.Description | contains("task-")) | select(.Status=="available") | .NetworkInterfaceId'`)
for e in "${DSAVAILENI[@]}"
  do
  # Gets DataSync task IDs from available DS ENIs 
  TASK=$(aws ec2 describe-network-interfaces --profile default | jq -r '.NetworkInterfaces[] | select(.NetworkInterfaceId=="'$e'") | select(.Status="available") | {Description: .Description}' | grep -Eo '(task-.[0-9a-zA-Z]*)') 

  # Checks if the task ID exists
  TASKARN=$(aws datasync list-tasks --profile default | jq -r --arg task $TASK '.Tasks[] | select(.TaskArn| contains($task) ) | .TaskArn')
  if [[ -n "$TASKARN" ]]
    then
    echo "ENI" $e" with an Available status is associated with Task ID:" $TASK
    else
    echo -e "${RED}ENI" $e" with an Available status is no longer associated with Task ID:" $TASK ${NC}
    
    # ENI delete dry run
    #aws ec2 delete-network-interface --profile default --network-interface-id $e --dry-run
  fi
done
