#!/bin/bash
cd $(dirname $0)
sudo rm -f venv/bin/python
sudo cp /usr/bin/python ./venv/bin/python 
sudo setcap cap_net_raw+ep ./venv/bin/python
