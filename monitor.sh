#!/bin/bash
sudo airmon-ng start wlx00173f847fbf
sudo python probemon.py -i mon1 -f -s -r -l -t u
