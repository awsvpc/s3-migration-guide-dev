
def sync_to_s3(source_directory, s3_bucket, s3_prefix=""):
    """
    Synchronize a local directory with an S3 bucket using AWS CLI's 'aws s3 sync' command.
    Args:
        source_directory (str): The local directory to sync.
        s3_bucket (str): The S3 bucket to sync to.
        s3_prefix (str, optional): The S3 prefix (path) within the bucket. Default is an empty string.
    """
    # Construct the AWS S3 URI
    s3_uri = f"s3://{s3_bucket}/{s3_prefix}"

    # Formulate the 'aws s3 sync' command
    command = ["aws", "s3", "sync", source_directory, s3_uri]

    try:
        # Run the command using subprocess
        subprocess.run(command, check=True)
        print(f"Synced '{source_directory}' to '{s3_uri}' successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error syncing to S3: {e}")
    except Exception as ex:
        print(f"An unexpected error occurred: {ex}")

if __name__ == "__main__":
    # Modify these values with your specific source directory, S3 bucket, and prefix
    source_dir = "/path/to/local/directory"
    s3_bucket = "your-s3-bucket"
    s3_prefix = "optional/s3/prefix"

    sync_to_s3(source_dir, s3_bucket, s3_prefix)
