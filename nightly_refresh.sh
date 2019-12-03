#!/bin/bash
log () {
    echo [`date`] "$1" >> '/home/attendance/Attendance_data/logs/refreshlog.log'
}

#Generate history cache
log 'Creating history cache'
python3 /home/attendance/Attendance/cache_history.py

#Cycle server log
log 'Cycling server log'
cd '/home/attendance/Attendance_data/logs'
cp 'serverlog.log' ./serverlogs/"`date`".log
echo '' > 'serverlog.log'

#Create backup
sizeLimit='28672' #in megabytes (1 gigabyte = 1024 megabytes); currently set at 28 gigabytes
targetPath='/backup-usb'

cd '/home/attendance/'

#Create zip
log 'Creating zip file'
zip -r backup.zip Attendance_data > /dev/null

#Get size of data and calculate target size
du_output=`du -sb ./backup.zip`
du_array=($du_output)
dataSize=${du_array[0]}
targetSize=$(expr $sizeLimit \* 1048576 - $dataSize)

#Find current size
du_output=`du -sb "$targetPath"`
du_array=($du_output)
size=${du_array[0]}

while [ "$size" -gt "$targetSize" ]; do
    #Delete oldest backup
    filename=`ls -1r "$targetPath" | tail -n 1`
    #Check if folder empty
    if [ "$filename" == '' ]; then
        log 'Cannot create backup - capacity too small'
        exit 1
    fi

    log "Deleting backup '$filename'"
    rm -r "$targetPath"/"$filename"

    #Get new size
    du_output=`du -sb "$targetPath"`
    du_array=($du_output)
    size=${du_array[0]}
done

log 'Copying data'
currentTime=`date '+%s - %m-%d-%Y'`
cp -r --no-preserve=mode ./backup.zip "$targetPath"/"$currentTime".zip
du -sh "$targetPath"

log 'Deleting zip file'
rm ./backup.zip

#Reboot once a week
if [ `date +%u` == 7 ]; then
    log 'Rebooting'
    reboot
fi