#!/usr/bin/env python3
# Runs ON VM-1. Launches VM-2 (the Flask app) using the service credentials.
import time
import googleapiclient.discovery
from google.oauth2 import service_account

PROJECT = open("/srv/project.txt").read().strip()
INSTANCE = "flask-vm-2"
MACHINE_TYPE = "e2-medium"
IMAGE = "base-image-flask-vm"  # image made in part 2 (already has the app)
ZONES = ["us-west1-a", "us-west1-b", "us-west1-c",
         "us-central1-a", "us-central1-b", "us-east1-b"]

credentials = service_account.Credentials.from_service_account_file(
    "/srv/service-credentials.json",
    scopes=["https://www.googleapis.com/auth/cloud-platform"])
compute = googleapiclient.discovery.build("compute", "v1", credentials=credentials)
startup_script = open("/srv/vm2-startup-script.sh").read()


def wait(op, zone):
    while True:
        r = compute.zoneOperations().get(
            project=PROJECT, zone=zone, operation=op["name"]).execute()
        if r["status"] == "DONE":
            if "error" in r:
                raise Exception(r["error"])
            return
        time.sleep(1)


for zone in ZONES:
    config = {
        "name": INSTANCE,
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
        "metadata": {"items": [{"key": "startup-script", "value": startup_script}]},
    }
    try:
        op = compute.instances().insert(project=PROJECT, zone=zone, body=config).execute()
        wait(op, zone)
        inst = compute.instances().get(project=PROJECT, zone=zone, instance=INSTANCE).execute()
        ip = inst["networkInterfaces"][0]["accessConfigs"][0].get("natIP")
        print(f"Created {INSTANCE} in {zone}: http://{ip}:5000", flush=True)
        break
    except Exception as e:
        print(f"{zone} failed: {str(e)[:100]}", flush=True)
else:
    raise SystemExit("No zone had capacity for VM-2")
