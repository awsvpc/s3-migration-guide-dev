"""
A script to sync S3 data fast to a local folder or EBS store.
The script calls aws s3 sync in parallel for subfolders.
In addition to parallel sync calls, also increase the concurrent
request for each sync call using an ~/.aws/config file
[default]
s3 =
  max_concurrent_requests = 20
  max_queue_size = 10000
"""
import random
import subprocess
from multiprocessing import Pool


bucket = "mybucket"  # Bucket name
folders = []  # List of S3 keys to sync
nr_of_processes = 20

# In this case we want to download the data in random order
random.seed(42)
random.shuffle(mgrs)


def worker(folder):
    print(f"Doing {folder}")
    subprocess.run(["aws", "s3", "sync", "--only-show-errors", "--profile", "default", f"s3://{bucket}/{folder}/", f"/localdir/{folder}/"])
    print(f"Done {folder}")


if __name__ == '__main__':
    with Pool(nr_of_processes) as p:
        p.map(worker, folders)
