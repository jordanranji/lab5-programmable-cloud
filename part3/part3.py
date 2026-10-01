#!/usr/bin/env python3
# Runs on your laptop. Creates VM-1, which then creates VM-2 (Flask).
import time
import googleapiclient.discovery
from google.oauth2 import service_account

PROJECT = "reference-glass-506723-v7"
VM1_NAME = "vm1-launcher"
MACHINE_TYPE = "e2-small"
ZONES = ["us-west1-a", "us-west1-b", "us-west1-c",
         "us-central1-a", "us-central1-b", "us-east1-b"]

credentials = service_account.Credentials.from_service_account_file(
    "service-credentials.json",
    scopes=["https://www.googleapis.com/auth/cloud-platform"])
compute = googleapiclient.discovery.build("compute", "v1", credentials=credentials)

# Startup script for VM-1: pull everything out of metadata, then run the launcher.
VM1_STARTUP = """#!/bin/bash
MD=http://metadata/computeMetadata/v1/instance/attributes
mkdir -p /srv
cd /srv
curl $MD/vm2-startup-script -H "Metadata-Flavor: Google" > vm2-startup-script.sh
curl $MD/service-credentials -H "Metadata-Flavor: Google" > service-credentials.json
curl $MD/vm1-launch-vm2-code -H "Metadata-Flavor: Google" > vm1-launch-vm2-code.py
curl $MD/project -H "Metadata-Flavor: Google" > project.txt
export GOOGLE_CLOUD_PROJECT=$(cat project.txt)

apt-get update
apt-get install -y python3-googleapi python3-google-auth python3-google-auth-httplib2
python3 ./vm1-launch-vm2-code.py > /srv/launch.log 2>&1
"""


def read(path):
    with open(path) as f:
        return f.read()


def wait(op, zone):
    while True:
        r = compute.zoneOperations().get(
            project=PROJECT, zone=zone, operation=op["name"]).execute()
        if r["status"] == "DONE":
            if "error" in r:
                raise Exception(r["error"])
            return
        time.sleep(1)


def make_vm1():
    items = [
        {"key": "startup-script", "value": VM1_STARTUP},
        {"key": "vm2-startup-script", "value": read("vm2-startup-script.sh")},
        {"key": "vm1-launch-vm2-code", "value": read("vm1-launch-vm2-code.py")},
        {"key": "service-credentials", "value": read("service-credentials.json")},
        {"key": "project", "value": PROJECT},
    ]
    for zone in ZONES:
        config = {
            "name": VM1_NAME,
            "machineType": f"zones/{zone}/machineTypes/{MACHINE_TYPE}",
            "disks": [{
                "boot": True,
                "autoDelete": True,
                "initializeParams": {
                    "sourceImage": "projects/debian-cloud/global/images/family/debian-12"},
            }],
            "networkInterfaces": [{
                "network": "global/networks/default",
                "accessConfigs": [{"type": "ONE_TO_ONE_NAT", "name": "External NAT"}],
            }],
            "metadata": {"items": items},
        }
        try:
            op = compute.instances().insert(project=PROJECT, zone=zone, body=config).execute()
            wait(op, zone)
            print(f"Created {VM1_NAME} in {zone}")
            return
        except Exception as e:
            print(f"{zone} failed: {str(e)[:100]}")
    raise SystemExit("No zone had capacity for VM-1")


if __name__ == "__main__":
    make_vm1()
