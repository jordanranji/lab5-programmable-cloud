#!/usr/bin/env python3
# Adapted from Google Cloud's python-docs-samples compute/api/create_instance.py
import time
import googleapiclient.discovery
from googleapiclient.errors import HttpError

PROJECT = "reference-glass-506723-v7"
ZONE = "us-west1-a"
NAME = "flask-vm"
MACHINE_TYPE = "e2-micro"
TAG = "allow-5000"

STARTUP_SCRIPT = """#!/bin/bash
apt-get update
apt-get install -y python3 python3-pip git
mkdir -p /opt/app && cd /opt/app
git clone https://github.com/cu-csci-4253-datacenter/flask-tutorial
cd flask-tutorial
python3 setup.py install
pip3 install -e .
export FLASK_APP=flaskr
flask init-db
nohup flask run -h 0.0.0.0 &
"""

compute = googleapiclient.discovery.build("compute", "v1")


def wait_for_zone_op(op):
    while True:
        result = compute.zoneOperations().get(
            project=PROJECT, zone=ZONE, operation=op["name"]).execute()
        if result["status"] == "DONE":
            if "error" in result:
                raise Exception(result["error"])
            return result
        time.sleep(2)


def wait_for_global_op(op):
    while True:
        result = compute.globalOperations().get(
            project=PROJECT, operation=op["name"]).execute()
        if result["status"] == "DONE":
            if "error" in result:
                raise Exception(result["error"])
            return result
        time.sleep(2)


def ensure_firewall():
    try:
        compute.firewalls().get(project=PROJECT, firewall="allow-5000").execute()
        print("Firewall rule allow-5000 already exists.")
    except HttpError as e:
        if e.resp.status != 404:
            raise
        body = {
            "name": "allow-5000",
            "network": "global/networks/default",
            "direction": "INGRESS",
            "allowed": [{"IPProtocol": "tcp", "ports": ["5000"]}],
            "sourceRanges": ["0.0.0.0/0"],
            "targetTags": [TAG],
        }
        op = compute.firewalls().insert(project=PROJECT, body=body).execute()
        wait_for_global_op(op)
        print("Created firewall rule allow-5000.")


def create_instance():
    image = compute.images().getFromFamily(
        project="ubuntu-os-cloud", family="ubuntu-2204-lts").execute()
    config = {
        "name": NAME,
        "machineType": f"zones/{ZONE}/machineTypes/{MACHINE_TYPE}",
        "disks": [{
            "boot": True,
            "autoDelete": True,
            "initializeParams": {"sourceImage": image["selfLink"]},
        }],
        "networkInterfaces": [{
            "network": "global/networks/default",
            "accessConfigs": [{"type": "ONE_TO_ONE_NAT", "name": "External NAT"}],
        }],
        "metadata": {"items": [{"key": "startup-script", "value": STARTUP_SCRIPT}]},
    }
    op = compute.instances().insert(project=PROJECT, zone=ZONE, body=config).execute()
    wait_for_zone_op(op)
    print(f"Created instance {NAME}.")


def set_tags():
    inst = compute.instances().get(project=PROJECT, zone=ZONE, instance=NAME).execute()
    body = {"items": [TAG], "fingerprint": inst["tags"]["fingerprint"]}
    op = compute.instances().setTags(
        project=PROJECT, zone=ZONE, instance=NAME, body=body).execute()
    wait_for_zone_op(op)
    print(f"Applied tag {TAG}.")


def get_external_ip():
    inst = compute.instances().get(project=PROJECT, zone=ZONE, instance=NAME).execute()
    return inst["networkInterfaces"][0]["accessConfigs"][0]["natIP"]


if __name__ == "__main__":
    ensure_firewall()
    create_instance()
    set_tags()
    ip = get_external_ip()
    print("\nThe Flask application is available at:")
    print(f"http://{ip}:5000")
    print("(The startup script can take 1-3 minutes to finish, so wait before loading.)")
