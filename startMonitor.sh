#!/bin/bash
read -p '2.4 or 5 ghz? ' response
if [ "$response" == '2.4' ]; then
id='wlx00173f847fbf'
else
id='wlx0020a6f69098'
fi

cd /home/jaw99/python/probemon
while [ true ]; do
mon=`airmon-ng start "$id" | grep 'enabled on'`
mon="${mon:(-2)}"
mon="$(echo $mon | head -c 1)"

if [ "$mon" == '' ]; then
echo 'Failed to start montior. Trying again'
else
echo "Started ${response}ghz adapter on mon${mon}."
python probemon.py -i mon$mon -f -s -r -l -t u
echo
echo 'Restarting monitor'
fi
done
