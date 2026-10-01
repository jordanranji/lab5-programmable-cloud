#!/bin/bash
cd /opt/app/flask-tutorial
export FLASK_APP=flaskr
nohup flask run -h 0.0.0.0 &
