#!/usr/bin/env python3
import time
import googleapiclient.discovery

PROJECT = "reference-glass-506723-v7"
ZONE = "us-west1-c"
INSTANCE = "flask-vm"
MACHINE_TYPE = "e2-medium"
SNAPSHOT = f"base-snapshot-{INSTANCE}"
IMAGE = f"base-image-{INSTANCE}"

# The image already contains the app, but startup scripts live in instance
# metadata (not on the disk), so clones need this to launch Flask on boot.
START_FLASK = """#!/bin/bash
cd /opt/app/flask-tutorial
export FLASK_APP=flaskr
nohup flask run -h 0.0.0.0 &
"""

compute = googleapiclient.discovery.build("compute", "v1")


def wait(op, zonal):
    while True:
        if zonal:
            r = compute.zoneOperations().get(
                project=PROJECT, zone=ZONE, operation=op["name"]).execute()
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
    wait(op, zonal=True)
    print(f"Created snapshot {SNAPSHOT}")


def make_image():
    op = compute.images().insert(project=PROJECT, body={
        "name": IMAGE,
        "sourceSnapshot": f"projects/{PROJECT}/global/snapshots/{SNAPSHOT}",
    }).execute()
    wait(op, zonal=False)
    print(f"Created image {IMAGE}")


def make_clone(name):
    config = {
        "name": name,
        "machineType": f"zones/{ZONE}/machineTypes/{MACHINE_TYPE}",
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
    start = time.time()
    op = compute.instances().insert(project=PROJECT, zone=ZONE, body=config).execute()
    wait(op, zonal=True)
    return time.time() - start


if __name__ == "__main__":
    #make_snapshot()
    #make_image()
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
