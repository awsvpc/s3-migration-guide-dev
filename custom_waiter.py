from botocore.waiter import WaiterModel


waiter_config = {
    "version": 2,
    "waiters": {
        "DBClusterAvailable": {
        "delay": 30,
        "operation": "DescribeDBClusters",
        "maxAttempts": 60,
        "acceptors": [
            {
            "expected": "available",
            "matcher": "pathAll",
            "state": "success",
            "argument": "DBClusters[].Status"
            },
            {
            "expected": "deleted",
            "matcher": "pathAny",
            "state": "failure",
            "argument": "DBClusters[].Status"
            },
            {
            "expected": "deleting",
            "matcher": "pathAny",
            "state": "failure",
            "argument": "DBClusters[].Status"
            },
            {
            "expected": "failed",
            "matcher": "pathAny",
            "state": "failure",
            "argument": "DBClusters[].Status"
            },
            {
            "expected": "incompatible-restore",
            "matcher": "pathAny",
            "state": "failure",
            "argument": "DBClusters[].Status"
            },
            {
            "expected": "incompatible-parameters",
            "matcher": "pathAny",
            "state": "failure",
            "argument": "DBClusters[].Status"
            }
        ]
        },
        "DBClusterDeleted": {
        "delay": 30,
        "operation": "DescribeDBClusters",
        "maxAttempts": 60,
        "acceptors": [
            {
            "expected": "true",
            "matcher": "path",
            "state": "success",
            "argument": "length(DBClusters) == `0`"
            },
            {
            "expected": "DBClusterNotFoundFault", 
            "matcher": "error",
            "state": "success"
            },
            {
            "expected": "creating",
            "matcher": "pathAny",
            "state": "failure",
            "argument": "DBClusters[].Status"
            },
            {
            "expected": "modifying",
            "matcher": "pathAny",
            "state": "failure",
            "argument": "DBClusters[].Status"
            },
            {
            "expected": "rebooting",
            "matcher": "pathAny",
            "state": "failure",
            "argument": "DBClusters[].Status"
            },
            {
            "expected": "resetting-master-credentials",
            "matcher": "pathAny",
            "state": "failure",
            "argument": "DBClusters[].Status"
            }
        ]
    }
    }
} 


waiter_model = WaiterModel(waiter_config=waiter_config)
