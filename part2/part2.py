#!/usr/bin/env python3
import time
import googleapiclient.discovery
 
PROJECT = "reference-glass-506723-v7"
ZONE = "us-west1-c"  # zone of the original flask-vm (and its disk)
INSTANCE = "flask-vm"
MACHINE_TYPE = "e2-medium"
SNAPSHOT = f"base-snapshot-{INSTANCE}"
IMAGE = f"base-image-{INSTANCE}"
 
# Snapshots and images are global, so clones can go in any zone. If one zone
# is out of capacity, we fall through to the next.
CLONE_ZONES = [
    "us-west1-a",
    "us-west1-b",
    "us-central1-a",
    "us-central1-b",
    "us-east1-b",
]
 
# The image already contains the app, but startup scripts live in instance
# metadata (not on the disk), so clones need this to launch Flask on boot.
START_FLASK = """#!/bin/bash
cd /opt/app/flask-tutorial
export FLASK_APP=flaskr
nohup flask run -h 0.0.0.0 &
"""
 
compute = googleapiclient.discovery.build("compute", "v1")
 
 
def wait(op, zone=None):
    """Wait for an operation. Pass zone for zonal ops, omit for global ones."""
    while True:
        if zone:
            r = compute.zoneOperations().get(
                project=PROJECT, zone=zone, operation=op["name"]).execute()
        else:
            r = compute.globalOperations().get(
                project=PROJECT, operation=op["name"]).execute()
        if r["status"] == "DONE":
            if "error" in r:
                raise Exception(r["error"])
            return
        time.sleep(1)
 
 
def make_snapshot():
    op = compute.disks().createSnapshot(
        project=PROJECT, zone=ZONE, disk=INSTANCE,
        body={"name": SNAPSHOT}).execute()
    wait(op, zone=ZONE)
    print(f"Created snapshot {SNAPSHOT}")
 
 
def make_image():
    op = compute.images().insert(project=PROJECT, body={
        "name": IMAGE,
        "sourceSnapshot": f"projects/{PROJECT}/global/snapshots/{SNAPSHOT}",
    }).execute()
    wait(op)
    print(f"Created image {IMAGE}")
 
 
def make_clone(name):
    for zone in CLONE_ZONES:
        config = {
            "name": name,
            "machineType": f"zones/{zone}/machineTypes/{MACHINE_TYPE}",
            "disks": [{
                "boot": True,
                "autoDelete": True,
                "initializeParams": {
                    "sourceImage": f"projects/{PROJECT}/global/images/{IMAGE}"},
            }],
            "networkInterfaces": [{
                "network": "global/networks/default",
                "accessConfigs": [{"type": "ONE_TO_ONE_NAT", "name": "External NAT"}],
            }],
            "tags": {"items": ["allow-5000"]},
            "metadata": {"items": [{"key": "startup-script", "value": START_FLASK}]},
        }
        start = time.time()  # reset each attempt so failed zones don't inflate the time
        try:
            op = compute.instances().insert(
                project=PROJECT, zone=zone, body=config).execute()
            wait(op, zone=zone)
            print(f"{name} created in {zone}")
            return time.time() - start
        except Exception as e:
            print(f"{zone} failed ({str(e)[:80]}...), trying next zone")
    raise RuntimeError(f"No zone had capacity for {name}")
 
 
if __name__ == "__main__":
    # make_snapshot()
    # make_image()
    times = []
    for i in range(1, 4):
        name = f"clone-{i}"
        t = make_clone(name)
        times.append((name, t))
        print(f"{name}: {t:.2f} seconds")
 
    with open("TIMING.md", "w") as f:
        f.write("# Instance creation times\n\n")
        for name, t in times:
            f.write(f"- {name}: {t:.2f} seconds\n")
